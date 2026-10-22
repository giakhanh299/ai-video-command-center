from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

try:
    from .scene_detector import detect_scene_ranges
    from . import wuby_ocr_overlay, movie_voice_matcher
except ImportError:
    from scene_detector import detect_scene_ranges
    import wuby_ocr_overlay
    import movie_voice_matcher


def _seg_times(seg: Any) -> tuple[float, float] | None:
    try:
        if isinstance(seg, dict):
            st, en = float(seg.get("start", 0)), float(seg.get("end", 0))
        else:
            st, en = float(getattr(seg, "start")), float(getattr(seg, "end"))
        if en > st >= 0:
            return st, en
    except Exception:
        pass
    return None


def _sample_positions(frame_count: int, count: int) -> list[int]:
    if frame_count <= 0:
        return []
    count = max(1, min(int(count), frame_count))
    if count == 1:
        return [0]
    return sorted(set(int(round(x)) for x in np.linspace(0, frame_count - 1, count)))


def analyze_frame_geometry(video_path: str, sample_frames: int = 48) -> dict[str, Any]:
    """Measure source geometry and visual dynamics before any destructive processing.

    The measurements are intentionally lightweight and deterministic. They are used to
    choose an OCR cadence, protect the original aspect ratio/FPS and avoid applying the
    portrait hybrid frame to landscape sources.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"WUBY_PREFLIGHT_VIDEO_OPEN_FAILED:{video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 else 0.0
    positions = _sample_positions(frame_count, sample_frames)

    brightness: list[float] = []
    contrast: list[float] = []
    sharpness: list[float] = []
    motion: list[float] = []
    row_lumas: list[np.ndarray] = []
    prev_small: np.ndarray | None = None

    for pos in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        h, w = frame.shape[:2]
        analysis_w = min(360, max(96, w))
        analysis_h = max(1, int(round(h * analysis_w / max(1, w))))
        small = cv2.resize(frame, (analysis_w, analysis_h), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        brightness.append(float(np.mean(gray)))
        contrast.append(float(np.std(gray)))
        sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        row_lumas.append(np.mean(gray, axis=1))
        if prev_small is not None and prev_small.shape == gray.shape:
            motion.append(float(np.mean(cv2.absdiff(gray, prev_small))))
        prev_small = gray
    cap.release()

    if width <= 0 or height <= 0:
        raise RuntimeError("WUBY_PREFLIGHT_INVALID_GEOMETRY")

    aspect = width / float(height)
    if aspect < 0.82:
        orientation = "portrait"
    elif aspect > 1.18:
        orientation = "landscape"
    else:
        orientation = "square"

    top_bar = bottom_bar = 0
    if row_lumas:
        stack = np.stack(row_lumas, axis=0)
        med_rows = np.median(stack, axis=0)
        # Treat only truly dark, persistent rows as letterbox bars.
        dark = med_rows < 18.0
        for v in dark:
            if not v:
                break
            top_bar += 1
        for v in dark[::-1]:
            if not v:
                break
            bottom_bar += 1
        scale = height / float(len(med_rows))
        top_bar = int(round(top_bar * scale))
        bottom_bar = int(round(bottom_bar * scale))

    motion_mean = float(np.mean(motion)) if motion else 0.0
    motion_p90 = float(np.percentile(motion, 90)) if motion else 0.0
    # Higher motion / more cuts -> denser OCR sampling. Cap at 24fps so OCR stays practical.
    if motion_p90 >= 28 or motion_mean >= 18:
        suggested_ocr_fps = min(24.0, max(12.0, fps))
        motion_class = "high"
    elif motion_p90 >= 16 or motion_mean >= 9:
        suggested_ocr_fps = min(18.0, max(10.0, fps))
        motion_class = "medium"
    else:
        suggested_ocr_fps = min(12.0, max(8.0, fps))
        motion_class = "low"

    return {
        "width": width,
        "height": height,
        "fps": round(fps, 6),
        "frame_count": frame_count,
        "duration_sec": round(duration, 3),
        "aspect_ratio": round(aspect, 5),
        "orientation": orientation,
        "sampled_frames": len(brightness),
        "brightness_mean": round(float(np.mean(brightness)), 3) if brightness else None,
        "brightness_p10": round(float(np.percentile(brightness, 10)), 3) if brightness else None,
        "brightness_p90": round(float(np.percentile(brightness, 90)), 3) if brightness else None,
        "contrast_mean": round(float(np.mean(contrast)), 3) if contrast else None,
        "sharpness_median": round(float(np.median(sharpness)), 3) if sharpness else None,
        "motion_mean": round(motion_mean, 3),
        "motion_p90": round(motion_p90, 3),
        "motion_class": motion_class,
        "letterbox_top_px": top_bar,
        "letterbox_bottom_px": bottom_bar,
        "suggested_ocr_fps": round(float(suggested_ocr_fps), 3),
        "preserve_source_fps": True,
        "preserve_source_resolution": True,
    }


def _event_overlap(ev: dict[str, Any], seg: Any) -> float:
    t = _seg_times(seg)
    if not t:
        return 0.0
    st, en = t
    return max(0.0, min(float(ev.get("end", 0)), en) - max(float(ev.get("start", 0)), st))


def summarize_ocr(events: list[dict[str, Any]], target_segments: Iterable[Any], width: int, height: int) -> dict[str, Any]:
    targets = list(target_segments or [])
    valid = [ev for ev in events if ev.get("box")]
    dialogue = [ev for ev in valid if not ev.get("is_banner")]
    banners = [ev for ev in valid if ev.get("is_banner")]
    moving = [ev for ev in valid if ev.get("motion_type") == "MOVE"]

    covered_count = 0
    covered_duration = 0.0
    target_duration = 0.0
    for seg in targets:
        t = _seg_times(seg)
        if not t:
            continue
        st, en = t
        target_duration += max(0.0, en - st)
        overlaps = [_event_overlap(ev, seg) for ev in dialogue if (ev.get("vi_text") or "").strip()]
        best = max(overlaps) if overlaps else 0.0
        if best > 0.05:
            covered_count += 1
            covered_duration += min(en - st, best)

    boxes = [ev["box"] for ev in dialogue]
    if boxes:
        center_ys = [float(y) + float(h) / 2.0 for _, y, _, h in boxes]
        heights = [float(h) for _, _, _, h in boxes]
        widths = [float(w) for _, _, w, _ in boxes]
        median_center_y_ratio = float(np.median(center_ys)) / max(1.0, float(height))
        median_box_height_ratio = float(np.median(heights)) / max(1.0, float(height))
        median_box_width_ratio = float(np.median(widths)) / max(1.0, float(width))
    else:
        median_center_y_ratio = None
        median_box_height_ratio = None
        median_box_width_ratio = None

    return {
        "track_count": len(valid),
        "dialogue_track_count": len(dialogue),
        "banner_track_count": len(banners),
        "moving_track_count": len(moving),
        "moving_track_ratio": round(len(moving) / max(1, len(valid)), 4),
        "matched_dialogue_count": sum(1 for ev in dialogue if (ev.get("vi_text") or "").strip()),
        "target_segment_count": len(targets),
        "segment_coverage": round(covered_count / max(1, len(targets)), 4),
        "duration_coverage": round(covered_duration / max(1e-6, target_duration), 4) if target_duration else 0.0,
        "median_dialogue_center_y_ratio": round(median_center_y_ratio, 4) if median_center_y_ratio is not None else None,
        "median_dialogue_box_height_ratio": round(median_box_height_ratio, 4) if median_box_height_ratio is not None else None,
        "median_dialogue_box_width_ratio": round(median_box_width_ratio, 4) if median_box_width_ratio is not None else None,
    }


def _smooth_voice_islands(assignments: list[dict[str, Any]], max_island_sec: float = 1.5) -> int:
    """Remove one-segment pitch islands caused by intonation rather than a real speaker change."""
    changed = 0
    if len(assignments) < 3:
        return changed
    for i in range(1, len(assignments) - 1):
        prev_a, cur, next_a = assignments[i - 1], assignments[i], assignments[i + 1]
        prev_p, cur_p, next_p = prev_a.get("profile"), cur.get("profile"), next_a.get("profile")
        if not prev_p or not cur_p or prev_p != next_p or cur_p == prev_p:
            continue
        dur = max(0.0, float(cur.get("end", 0)) - float(cur.get("start", 0)))
        if dur <= max_island_sec:
            cur["profile"] = prev_p
            cur["method"] = "wuby_island_smoothing"
            changed += 1
    return changed


def _voice_summary(report: dict[str, Any]) -> dict[str, Any]:
    assignments = report.get("target_assignments") or []
    unique = sorted({str(a.get("profile")) for a in assignments if a.get("profile")})
    margins: list[float] = []
    top_dist: list[float] = []
    for a in report.get("source_segments") or []:
        top3 = a.get("top3") or []
        if top3:
            try:
                top_dist.append(float(top3[0].get("distance_cents", 0)))
            except Exception:
                pass
        if len(top3) >= 2:
            try:
                margins.append(float(top3[1].get("distance_cents", 0)) - float(top3[0].get("distance_cents", 0)))
            except Exception:
                pass
    stats = report.get("stats") or {}
    light_asd = stats.get("light_asd") if isinstance(stats.get("light_asd"), dict) else {}
    return {
        "unique_voices": unique,
        "unique_voice_count": len(unique),
        "f0_coverage": float(stats.get("f0_coverage", 0.0)),
        "character_count": int(stats.get("character_count") or stats.get("speaker_cluster_count") or 0),
        "identity_backend": stats.get("identity_backend"),
        "identity_ambiguous_count": int(stats.get("identity_ambiguous_count") or 0),
        "light_asd_status": light_asd.get("status"),
        "light_asd_verified": int(light_asd.get("verified") or 0),
        "light_asd_overrides": int(light_asd.get("overrides") or 0),
        "identity_uses_f0": bool(stats.get("identity_uses_f0", False)),
        "median_best_distance_cents": round(float(np.median(top_dist)), 2) if top_dist else None,
        "median_top1_margin_cents": round(float(np.median(margins)), 2) if margins else None,
    }


def analyze_wuby_preflight(
    *,
    video_path: str,
    source_segments: Iterable[Any],
    target_segments: Iterable[Any],
    srt_path: str | None,
    movie_title: str | None,
    config_data: dict[str, Any],
    cfg: dict[str, Any] | None = None,
    report_path: str | None = None,
) -> dict[str, Any]:
    cfg = cfg or {}
    target_segments = list(target_segments or [])
    source_segments = list(source_segments or [])

    visual_cfg = cfg.get("visual") if isinstance(cfg.get("visual"), dict) else {}
    visual = analyze_frame_geometry(video_path, sample_frames=int(visual_cfg.get("sample_frames", 48)))

    scene_cfg = cfg.get("scene_detection") if isinstance(cfg.get("scene_detection"), dict) else {}
    scenes = detect_scene_ranges(
        video_path,
        diff_threshold=float(scene_cfg.get("diff_threshold", 28.0)),
        min_scene_sec=float(scene_cfg.get("min_scene_sec", 0.35)),
        analysis_width=int(scene_cfg.get("analysis_width", 160)),
    )

    ocr_cfg = cfg.get("ocr") if isinstance(cfg.get("ocr"), dict) else {}
    requested_ocr_fps = float(ocr_cfg.get("sample_fps", visual["suggested_ocr_fps"]))
    if bool(ocr_cfg.get("adaptive_by_motion", True)):
        # Never undersample below what the measured motion needs.
        ocr_fps = max(float(visual["suggested_ocr_fps"]), requested_ocr_fps)
    else:
        ocr_fps = requested_ocr_fps
    ocr_fps = min(24.0, max(4.0, ocr_fps))

    events = wuby_ocr_overlay.scan_video_text_events(
        video_path,
        sample_fps=ocr_fps,
        min_confidence=float(ocr_cfg.get("min_confidence", 0.28)),
        max_duration=float(ocr_cfg.get("max_duration", 3600.0)),
        scene_ranges=scenes,
        remove_classes=ocr_cfg.get("remove_classes") or ["chinese", "mixed_chinese"],
        max_track_gap_sec=float(ocr_cfg.get("max_track_gap_sec", 0.65)),
        max_center_distance_px=float(ocr_cfg.get("max_center_distance_px", 190.0)),
        pre_padding_sec=float(ocr_cfg.get("pre_padding_sec", 0.08)),
        post_padding_factor=float(ocr_cfg.get("post_padding_factor", 0.75)),
    )
    events = wuby_ocr_overlay.filter_semantic_ocr_events(events)
    events = wuby_ocr_overlay.match_ocr_events_with_subtitles(
        events,
        segments=target_segments,
        srt_path=srt_path,
        movie_title=movie_title,
        vid_h=int(visual["height"]),
        vid_w=int(visual["width"]),
    )
    ocr_summary = summarize_ocr(events, target_segments, int(visual["width"]), int(visual["height"]))

    qc_cfg = cfg.get("qc") if isinstance(cfg.get("qc"), dict) else {}
    track_warnings = wuby_ocr_overlay.run_track_qc(
        events,
        int(visual["width"]),
        int(visual["height"]),
        max_mask_ratio=float(qc_cfg.get("max_mask_ratio", 0.35)),
        max_track_duration_sec=float(qc_cfg.get("max_track_duration_sec", 12.0)),
    )

    voice_cfg = cfg.get("voice_match") if isinstance(cfg.get("voice_match"), dict) else {}
    voice_report: dict[str, Any] | None = None
    voice_summary: dict[str, Any] = {
        "unique_voices": [],
        "unique_voice_count": 0,
        "f0_coverage": 0.0,
        "character_count": 0,
        "identity_backend": None,
        "identity_ambiguous_count": 0,
        "light_asd_status": None,
        "light_asd_verified": 0,
        "light_asd_overrides": 0,
        "identity_uses_f0": False,
        "median_best_distance_cents": None,
        "median_top1_margin_cents": None,
    }
    if source_segments and target_segments and voice_cfg.get("enabled", True):
        voice_report = movie_voice_matcher.match_whisper_segments(
            video_path=video_path,
            source_segments=source_segments,
            target_segments=target_segments,
            config_data=config_data,
            cfg=voice_cfg,
        )
        smoothed = _smooth_voice_islands(
            voice_report.get("target_assignments") or [],
            max_island_sec=float(voice_cfg.get("island_smoothing_max_sec", 1.5)),
        )
        voice_report.setdefault("stats", {})["wuby_smoothed_islands"] = smoothed
        voice_report.setdefault("stats", {})["unique_voices"] = sorted({
            str(a.get("profile")) for a in (voice_report.get("target_assignments") or []) if a.get("profile")
        })
        voice_summary = _voice_summary(voice_report)

    warnings: list[dict[str, Any]] = list(track_warnings)
    min_coverage = float(qc_cfg.get("min_ocr_segment_coverage", 0.65))
    if target_segments and ocr_summary["segment_coverage"] < min_coverage:
        warnings.append({
            "type": "low_ocr_subtitle_coverage",
            "detail": ocr_summary["segment_coverage"],
            "threshold": min_coverage,
        })
    min_f0_coverage = float(qc_cfg.get("min_f0_coverage", 0.55))
    if source_segments and voice_cfg.get("enabled", True) and voice_summary["f0_coverage"] < min_f0_coverage:
        warnings.append({
            "type": "low_f0_coverage",
            "detail": round(voice_summary["f0_coverage"], 4),
            "threshold": min_f0_coverage,
        })

    hybrid_ok = visual["orientation"] in {"portrait", "square"}
    render_plan = {
        "preserve_source_resolution": True,
        "preserve_source_fps": True,
        "orientation": visual["orientation"],
        "hybrid_frame_allowed": hybrid_ok,
        "ocr_sample_fps": round(float(ocr_fps), 3),
        "reuse_preflight_ocr_events": True,
        "follow_text_motion": True,
        "voice_mode": "character_id_locked_multivoice" if voice_report else "configured_voice_fallback",
        "needs_review": bool(warnings),
        "warning_count": len(warnings),
    }

    report = {
        "version": 1,
        "pipeline": "wuby_preflight_visual_audio",
        "video": str(video_path),
        "visual": visual,
        "scenes": {"count": len(scenes), "ranges": scenes},
        "ocr": {"sample_fps": round(float(ocr_fps), 3), "summary": ocr_summary, "events": events},
        "voice": {"summary": voice_summary, "match": voice_report},
        "qc": {"warnings": warnings, "pass": not bool(warnings)},
        "render_plan": render_plan,
    }

    if report_path:
        p = Path(report_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        def _json_default(obj):
            if isinstance(obj, (np.integer, np.int32, np.int64)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return report
