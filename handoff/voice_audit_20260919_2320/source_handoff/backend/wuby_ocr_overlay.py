"""OCR, scene-aware text tracking, erasing and in-place ASS overlay.

Compared with the first prototype, this version does not collapse all OCR hits
into one ever-growing static rectangle.  Each logical text item is a track with
per-time keyframes and is hard-bounded by its scene.  That makes moving text and
scene transitions safe enough for batch processing across many videos.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

import cv2
import numpy as np

try:
    from .scene_detector import detect_scene_ranges, scene_for_time
except (ImportError, ValueError):
    from scene_detector import detect_scene_ranges, scene_for_time

_OCR_READER = None


def get_ocr_reader(use_gpu: Optional[bool] = None):
    global _OCR_READER
    if _OCR_READER is None:
        import easyocr
        import torch

        if use_gpu is None:
            use_gpu = torch.cuda.is_available()
        device_str = "GPU (CUDA)" if use_gpu else "CPU"
        print(f"[WubyOCR] Khởi tạo EasyOCR ({device_str}) ['ch_sim', 'en']...")
        _OCR_READER = easyocr.Reader(["ch_sim", "en"], gpu=use_gpu)
    return _OCR_READER


def has_chinese_char(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def classify_ocr_text(text: str) -> str:
    """Classify OCR text so each channel can choose what it wants to remove."""
    t = (text or "").strip()
    if not t:
        return "unknown"
    has_cn = has_chinese_char(t)
    has_latin = bool(re.search(r"[A-Za-z]", t))
    has_digit = bool(re.search(r"\d", t))
    if has_cn and (has_latin or has_digit):
        return "mixed_chinese"
    if has_cn:
        return "chinese"
    if has_latin:
        # Common meme/effect strings should be separable from meaningful Latin captions.
        compact = re.sub(r"[^A-Za-z]", "", t).lower()
        if compact in {"emmm", "emm", "wow", "haha", "hahaha", "hhh", "lol"}:
            return "effect"
        return "latin"
    if has_digit and re.fullmatch(r"[\d\s:.,%+\-/]+", t):
        return "numeric"
    if re.fullmatch(r"[^\w\u4e00-\u9fff]+", t, flags=re.UNICODE):
        return "effect"
    return "unknown"


def _sample_background(frame: np.ndarray, box: Sequence[float], margin: int = 12) -> Tuple[List[int], float]:
    h, w = frame.shape[:2]
    x, y, bw, bh = [int(round(v)) for v in box]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(w, x + max(1, bw)), min(h, y + max(1, bh))
    strips = [
        frame[max(0, y1 - margin):y1, max(0, x1 - 4):min(w, x2 + 4)],
        frame[y2:min(h, y2 + margin), max(0, x1 - 4):min(w, x2 + 4)],
        frame[max(0, y1 - 4):min(h, y2 + 4), max(0, x1 - margin):x1],
        frame[max(0, y1 - 4):min(h, y2 + 4), x2:min(w, x2 + margin)],
    ]
    pts = [s.reshape(-1, 3) for s in strips if s.size]
    if not pts:
        return [255, 255, 255], 0.0
    all_pts = np.concatenate(pts, axis=0).astype(np.float32)
    median = np.median(all_pts, axis=0)
    spread = float(np.mean(np.std(all_pts, axis=0)))
    return median.astype(int).tolist(), spread


def _single_scene(video_path: str) -> List[Dict[str, Any]]:
    cap = cv2.VideoCapture(video_path)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    return [{
        "scene_id": 0,
        "start": 0.0,
        "end": n / fps if fps > 0 else 0.0,
        "start_frame": 0,
        "end_frame": max(0, n - 1),
    }]


def scan_video_text_events(
    video_path: str,
    sample_fps: float = 24.0,
    min_confidence: float = 0.28,
    max_duration: float = 3600.0,
    scene_ranges: Optional[List[Dict[str, Any]]] = None,
    remove_classes: Optional[Sequence[str]] = None,
    max_track_gap_sec: float = 0.65,
    max_center_distance_px: float = 190.0,
    pre_padding_sec: float = 0.08,
    post_padding_factor: float = 0.75,
) -> List[Dict[str, Any]]:
    """OCR a video and turn raw detections into scene-aware moving text tracks."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Không thể mở video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if fps > 0 else 0.0
    cap.release()

    scene_ranges = scene_ranges or detect_scene_ranges(video_path)
    allowed = set(remove_classes or ["chinese", "mixed_chinese"])
    reader = get_ocr_reader()
    step_frames = max(1, int(round(fps / max(sample_fps, 0.1))))
    actual_sample_fps = fps / step_frames
    print(
        f"[WubyOCR] Quét {duration:.2f}s @ {fps:.2f}fps, OCR ~{actual_sample_fps:.2f}fps, "
        f"classes={sorted(allowed)}"
    )

    cap = cv2.VideoCapture(video_path)
    raw: List[Dict[str, Any]] = []
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_idx / fps
        if t > max_duration:
            break
        if frame_idx % step_frames == 0:
            h, w = frame.shape[:2]
            for bbox, text, prob in reader.readtext(frame):
                clean = (text or "").strip()
                cls = classify_ocr_text(clean)
                if cls not in allowed:
                    continue
                # Chinese characters in stylized cartoon fonts often have low prob score in EasyOCR.
                # If Chinese characters are explicitly present, allow prob >= 0.0
                if not has_chinese_char(clean) and prob < min_confidence:
                    continue
                # Lọc bỏ các mảnh nhiễu vụn 1 ký tự với độ tin cậy thấp
                if len(clean) <= 1 and prob < 0.70:
                    continue
                xs = [int(round(p[0])) for p in bbox]
                ys = [int(round(p[1])) for p in bbox]
                x1, y1 = max(0, min(xs)), max(0, min(ys))
                x2, y2 = min(w, max(xs)), min(h, max(ys))
                if x2 <= x1 or y2 <= y1:
                    continue
                # Lọc nhiễu ở nửa dưới khung hình (y > 0.68 * H) trong video hoạt hình
                if y1 > 0.68 * h and (len(clean) < 4 or prob < 0.85):
                    continue
                box = [x1, y1, x2 - x1, y2 - y1]
                bg, spread = _sample_background(frame, box)
                scene = scene_for_time(scene_ranges, t)
                raw.append({
                    "time": t,
                    "frame_idx": frame_idx,
                    "scene_id": int(scene["scene_id"]),
                    "box": box,
                    "text": clean,
                    "text_class": cls,
                    "prob": float(prob),
                    "bg_bgr": bg,
                    "bg_spread": spread,
                })
        frame_idx += 1
    cap.release()

    print(f"[WubyOCR] Raw detections: {len(raw)}")
    tracks = build_text_tracks(
        raw,
        scene_ranges=scene_ranges,
        fps=fps,
        sample_fps=actual_sample_fps,
        max_track_gap_sec=max_track_gap_sec,
        max_center_distance_px=max_center_distance_px,
        pre_padding_sec=pre_padding_sec,
        post_padding_factor=post_padding_factor,
    )
    print(f"[WubyOCR] Text tracks: {len(tracks)}")
    for tr in tracks:
        print(
            f"  track#{tr['track_id']} scene={tr['scene_id']} {tr['start']:.3f}->{tr['end']:.3f}s "
            f"{tr['motion_type']} '{tr['text']}' kf={len(tr['keyframes'])}"
        )
    return tracks


def _center(box: Sequence[float]) -> Tuple[float, float]:
    return box[0] + box[2] / 2.0, box[1] + box[3] / 2.0


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    x1, y1 = max(ax1, bx1), max(ay1, by1)
    x2, y2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _track_match_cost(track: Dict[str, Any], det: Dict[str, Any], max_dist: float) -> Optional[float]:
    last = track["keyframes"][-1]
    if track["scene_id"] != det["scene_id"]:
        return None
    last_txt = last.get("text", "")
    det_txt = det.get("text", "")
    sim = _text_similarity(last_txt, det_txt)
    # Phân tách câu thoại: Nếu nội dung chữ thay đổi rõ rệt (sim < 0.35 với cả 2 đều >= 2 ký tự)
    # thì đây là câu thoại mới xuất hiện cùng vị trí, không gộp chung vào 1 track!
    if len(last_txt) >= 2 and len(det_txt) >= 2 and sim < 0.35:
        return None
    cx1, cy1 = _center(last["box"])
    cx2, cy2 = _center(det["box"])
    dist = math.hypot(cx2 - cx1, cy2 - cy1)
    size_scale = max(last["box"][2], last["box"][3], det["box"][2], det["box"][3], 1.0)
    dynamic_limit = max(max_dist, size_scale * 2.6)
    if dist > dynamic_limit:
        return None
    overlap = _iou(last["box"], det["box"])
    class_penalty = 0.0 if track.get("text_class") == det.get("text_class") else 0.25
    return (dist / dynamic_limit) - 0.70 * overlap - 0.30 * sim + class_penalty


def _finalize_track(
    track: Dict[str, Any],
    scene_ranges: List[Dict[str, Any]],
    fps: float,
    sample_fps: float,
    pre_padding_sec: float,
    post_padding_factor: float,
) -> Dict[str, Any]:
    kfs = sorted(track["keyframes"], key=lambda k: k["time"])
    track["keyframes"] = kfs
    scene = next((s for s in scene_ranges if s["scene_id"] == track["scene_id"]), scene_ranges[-1])
    frame_sec = 1.0 / max(fps, 1.0)
    sample_sec = 1.0 / max(sample_fps, 0.1)
    post_pad = max(frame_sec, min(0.20, sample_sec * post_padding_factor))
    start = max(float(scene["start"]), float(kfs[0]["time"]) - pre_padding_sec)
    # Intervals are half-open: include the last scene frame, never the next.
    scene_safe_end = max(start, float(scene["end"]))
    end = min(scene_safe_end, float(kfs[-1]["time"]) + post_pad)
    if end <= start:
        end = min(float(scene["end"]), start + frame_sec)
    track["start"] = start
    track["end"] = end
    track["scene_start"] = float(scene["start"])
    track["scene_end"] = float(scene["end"])

    xs = [k["box"][0] for k in kfs]
    ys = [k["box"][1] for k in kfs]
    x2s = [k["box"][0] + k["box"][2] for k in kfs]
    y2s = [k["box"][1] + k["box"][3] for k in kfs]
    track["box"] = [min(xs), min(ys), max(x2s) - min(xs), max(y2s) - min(ys)]

    centers = np.array([_center(k["box"]) for k in kfs], dtype=np.float32)
    widths = np.array([k["box"][2] for k in kfs], dtype=np.float32)
    heights = np.array([k["box"][3] for k in kfs], dtype=np.float32)
    center_span = float(np.linalg.norm(centers.max(axis=0) - centers.min(axis=0))) if len(centers) else 0.0
    avg_dim = float(max(np.mean(widths), np.mean(heights), 1.0))
    size_change = 0.0
    if len(kfs) > 1:
        size_change = max(float(np.ptp(widths) / max(np.mean(widths), 1.0)), float(np.ptp(heights) / max(np.mean(heights), 1.0)))
    if center_span > max(35.0, avg_dim * 0.45):
        motion = "MOVE"
    elif size_change > 0.35:
        motion = "SCALE"
    else:
        motion = "STATIC"
    track["motion_type"] = motion

    # Representative values retained for backwards compatibility.
    track["bg_bgr"] = list(np.median(np.array([k["bg_bgr"] for k in kfs]), axis=0).astype(int))
    track["prob"] = float(np.mean([k["prob"] for k in kfs]))
    track["count"] = len(kfs)
    best = max(kfs, key=lambda k: (len(k.get("text", "")), k.get("prob", 0.0)))
    track["text"] = best.get("text", "")
    return track


def build_text_tracks(
    detections: List[Dict[str, Any]],
    scene_ranges: List[Dict[str, Any]],
    fps: float,
    sample_fps: float,
    max_track_gap_sec: float = 0.65,
    max_center_distance_px: float = 190.0,
    pre_padding_sec: float = 0.08,
    post_padding_factor: float = 0.75,
) -> List[Dict[str, Any]]:
    """Multi-object association: one detection per track per sampled frame."""
    if not detections:
        return []
    detections = sorted(detections, key=lambda d: (d["frame_idx"], d["box"][1], d["box"][0]))
    frame_groups: Dict[int, List[Dict[str, Any]]] = {}
    for d in detections:
        frame_groups.setdefault(int(d["frame_idx"]), []).append(d)

    active: List[Dict[str, Any]] = []
    completed: List[Dict[str, Any]] = []
    next_id = 1

    for frame_idx in sorted(frame_groups):
        current = frame_groups[frame_idx]
        now = float(current[0]["time"])

        still_active = []
        for tr in active:
            if now - tr["keyframes"][-1]["time"] > max_track_gap_sec or tr["scene_id"] != current[0]["scene_id"]:
                completed.append(tr)
            else:
                still_active.append(tr)
        active = still_active

        candidates = []
        for ti, tr in enumerate(active):
            dt = now - tr["keyframes"][-1]["time"]
            if dt < -1e-6 or dt > max_track_gap_sec:
                continue
            for di, det in enumerate(current):
                cost = _track_match_cost(tr, det, max_center_distance_px)
                if cost is not None:
                    candidates.append((cost, ti, di))
        candidates.sort(key=lambda x: x[0])

        used_tracks, used_dets = set(), set()
        for cost, ti, di in candidates:
            if ti in used_tracks or di in used_dets:
                continue
            # A permissive but finite gate. Negative is excellent, ~1 means at distance limit.
            if cost > 1.05:
                continue
            det = current[di]
            tr = active[ti]
            tr["keyframes"].append({
                "time": det["time"],
                "frame_idx": det["frame_idx"],
                "box": det["box"],
                "text": det["text"],
                "prob": det["prob"],
                "bg_bgr": det["bg_bgr"],
                "bg_spread": det.get("bg_spread", 0.0),
            })
            if len(det.get("text", "")) > len(tr.get("text", "")):
                tr["text"] = det["text"]
            used_tracks.add(ti)
            used_dets.add(di)

        # A new caption occupying an unmatched track's box replaces it.
        # Retire the old track now: otherwise OCR A/B/A jitter can resurrect A
        # and span B's entire lifetime, producing two simultaneous overlays.
        replaced = set()
        for ti, tr in enumerate(active):
            if ti in used_tracks:
                continue
            if any(_iou(tr["keyframes"][-1]["box"], det["box"]) >= 0.25
                   for di, det in enumerate(current) if di not in used_dets):
                tr["replacement_time"] = now
                completed.append(tr)
                replaced.add(ti)
        active = [tr for ti, tr in enumerate(active) if ti not in replaced]

        for di, det in enumerate(current):
            if di in used_dets:
                continue
            active.append({
                "track_id": next_id,
                "scene_id": int(det["scene_id"]),
                "text": det["text"],
                "text_class": det.get("text_class", "unknown"),
                "keyframes": [{
                    "time": det["time"],
                    "frame_idx": det["frame_idx"],
                    "box": det["box"],
                    "text": det["text"],
                    "prob": det["prob"],
                    "bg_bgr": det["bg_bgr"],
                    "bg_spread": det.get("bg_spread", 0.0),
                }],
            })
            next_id += 1

    completed.extend(active)
    finalized = [
        _finalize_track(t, scene_ranges, fps, sample_fps, pre_padding_sec, post_padding_factor)
        for t in completed
    ]
    # Padding must not make sequential captions share the same screen area.
    # Preserve genuinely simultaneous detections (e.g. separate text lines).
    for old in finalized:
        if "replacement_time" in old:
            old["end"] = min(old["end"], old["replacement_time"])
        for new in finalized:
            if old is new or old["scene_id"] != new["scene_id"]:
                continue
            last, first = old["keyframes"][-1], new["keyframes"][0]
            if last["time"] < first["time"] and _iou(last["box"], first["box"]) >= 0.25:
                if new["start"] < old["end"]:
                    # Handoff on the first observed new frame, not pre-padding.
                    boundary = float(first["time"])
                    old["end"] = min(old["end"], boundary)
                    new["start"] = max(new["start"], old["end"])
    return sorted(finalized, key=lambda t: (t["start"], t["track_id"]))


def cluster_detections(detections: List[Dict[str, Any]], max_gap_sec: float = 1.5) -> List[Dict[str, Any]]:
    """Backward-compatible wrapper using the new tracker.

    Older callers may provide detections without scene metadata. This wrapper
    creates one scene and infers FPS/sample rate from detection timestamps.
    """
    if not detections:
        return []
    dets = [dict(d) for d in detections]
    for d in dets:
        d.setdefault("scene_id", 0)
        d.setdefault("text_class", classify_ocr_text(d.get("text", "")))
        d.setdefault("prob", 1.0)
        d.setdefault("bg_bgr", [255, 255, 255])
        d.setdefault("frame_idx", int(round(d.get("time", 0.0) * 24.0)))
    max_t = max(float(d.get("time", 0.0)) for d in dets) + max_gap_sec
    times = sorted({float(d.get("time", 0.0)) for d in dets})
    gaps = [b - a for a, b in zip(times[:-1], times[1:]) if b > a]
    sample_fps = 1.0 / np.median(gaps) if gaps else 4.0
    scene_ranges = [{"scene_id": 0, "start": 0.0, "end": max_t + 1.0}]
    return build_text_tracks(
        dets, scene_ranges, fps=24.0, sample_fps=float(sample_fps),
        max_track_gap_sec=max_gap_sec, max_center_distance_px=190.0,
    )


def _parse_srt(srt_path: str) -> List[Dict[str, Any]]:
    content = Path(srt_path).read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)\s*\n(.*?)(?=\n\n|\Z)", re.DOTALL)

    def parse_tc(tc: str) -> float:
        h, m, s = tc.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    out = []
    for m in pattern.finditer(content):
        st, et, text = m.groups()
        out.append({"start": parse_tc(st), "end": parse_tc(et), "text": text.replace("\n", " ").strip()})
    return out


def match_ocr_events_with_subtitles(
    ocr_events: List[Dict[str, Any]],
    segments: Optional[List[Any]] = None,
    srt_path: Optional[str] = None,
    movie_title: Optional[str] = None,
    vid_h: int = 1920,
) -> List[Dict[str, Any]]:
    sub_items: List[Dict[str, Any]] = []
    if segments:
        for seg in segments:
            text = getattr(seg, "text", "")
            if text and text.strip():
                sub_items.append({"start": float(seg.start), "end": float(seg.end), "text": text.strip(), "used": False})
    elif srt_path and os.path.exists(srt_path):
        parsed = _parse_srt(srt_path)
        for s in parsed:
            s["used"] = False
        sub_items = parsed

    # 1. Phân loại Top Banner (tiêu đề/chủ đề trên đầu) và Dialogue (thoại nhân vật)
    for ev in ocr_events:
        box = ev.get("box", [0, 0, 100, 50])
        cy = box[1] + box[3] / 2.0
        dur = ev["end"] - ev["start"]
        is_top_banner = (cy < 0.28 * vid_h) and (dur >= 2.5 or ev.get("is_banner", False))
        ev["is_banner"] = is_top_banner

        if is_top_banner:
            # Banner trên đầu là Tiêu đề/Chủ đề video, TUYỆT ĐỐI KHÔNG gán thoại nhân vật
            title_text = (movie_title or "").strip().upper()
            if not title_text or has_chinese_char(title_text):
                try:
                    from sub_processor import SubtitleTranslator, SubtitleSegment
                    tr = SubtitleTranslator()
                    raw_text = ev.get("text", "").strip()
                    res = tr.translate_segments([SubtitleSegment(0.0, 1.0, raw_text)])
                    if res and res[0].text:
                        title_text = res[0].text.strip().upper()
                except Exception:
                    pass
            ev["vi_text"] = title_text or ev.get("text", "").strip().upper()
            continue

        # Nếu track nằm ngoài khu vực thoại (ở đáy khung hình cy > 0.68 * vid_h), KHÔNG gán thoại
        if cy > 0.68 * vid_h:
            ev["vi_text"] = ""
            continue

        # 2. Dialogue tracks: Khớp 1-to-1 theo overlap thời gian chính xác nhất
        best_idx = -1
        best_overlap = -1.0
        for idx, sub in enumerate(sub_items):
            overlap = min(ev["end"], sub["end"]) - max(ev["start"], sub["start"])
            if overlap > 0.05 and overlap > best_overlap:
                best_overlap = overlap
                best_idx = idx

        if best_idx >= 0:
            ev["vi_text"] = sub_items[best_idx]["text"]
            sub_items[best_idx]["used"] = True
        else:
            # Nếu không tìm thấy overlap trực tiếp, tìm sub gần nhất chưa dùng
            ev_mid = (ev["start"] + ev["end"]) / 2.0
            candidates = [
                (idx, s, abs((s["start"] + s["end"]) / 2.0 - ev_mid))
                for idx, s in enumerate(sub_items)
                if not s.get("used", False)
            ]
            if candidates:
                closest_idx, closest_sub, dist = min(candidates, key=lambda x: x[2])
                if dist < 1.5:
                    ev["vi_text"] = closest_sub["text"]
                    closest_sub["used"] = True
                else:
                    ev["vi_text"] = ""
            else:
                ev["vi_text"] = ""

    # A translated cue can follow sequential fragments, not simultaneous
    # OCR regions. Prefer sustained tracks over split lines / brief noise.
    assigned = sorted(
        [ev for ev in ocr_events if ev.get("vi_text") and not ev.get("is_banner")],
        key=lambda ev: (len(ev.get("keyframes", [])), ev["end"] - ev["start"]),
        reverse=True,
    )
    owners = []
    for ev in assigned:
        if any(ev["vi_text"] == owner["vi_text"] and
               min(ev["end"], owner["end"]) > max(ev["start"], owner["start"])
               for owner in owners):
            ev["vi_text"] = ""
        else:
            owners.append(ev)
    return ocr_events


def interpolate_track_state(ev: Dict[str, Any], t: float) -> Tuple[List[float], List[int]]:
    kfs = ev.get("keyframes") or []
    if not kfs:
        return list(ev["box"]), list(ev.get("bg_bgr", [255, 255, 255]))
    if t <= kfs[0]["time"]:
        return list(kfs[0]["box"]), list(kfs[0]["bg_bgr"])
    if t >= kfs[-1]["time"]:
        return list(kfs[-1]["box"]), list(kfs[-1]["bg_bgr"])
    for a, b in zip(kfs[:-1], kfs[1:]):
        if a["time"] <= t <= b["time"]:
            span = max(1e-6, b["time"] - a["time"])
            alpha = (t - a["time"]) / span
            box = [(1 - alpha) * x + alpha * y for x, y in zip(a["box"], b["box"])]
            bg = [int(round((1 - alpha) * x + alpha * y)) for x, y in zip(a["bg_bgr"], b["bg_bgr"])]
            return box, bg
    return list(kfs[-1]["box"]), list(kfs[-1]["bg_bgr"])


def _feather_mask(h: int, w: int, rect: Tuple[int, int, int, int], feather_px: int) -> np.ndarray:
    x1, y1, x2, y2 = rect
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.rectangle(mask, (x1, y1), (x2, y2), 1.0, -1)
    k = max(1, int(feather_px))
    if k % 2 == 0:
        k += 1
    if k >= 3:
        mask = cv2.GaussianBlur(mask, (k, k), 0)
    return mask


def clean_video_ocr_backgrounds(
    input_video: str,
    output_video: str,
    ocr_events: List[Dict[str, Any]],
    padding: int = 12,
    method: str = "fill",
    feather_px: int = 17,
    live_background_sampling: bool = True,
) -> str:
    """Erase tracked text frame-by-frame using the interpolated moving box.

    `fill` is the safe/default mode for flat cartoon backgrounds. `inpaint` is
    available for textured areas, but it is intentionally opt-in because a full
    rectangle inpaint can damage character details.
    """
    if not ocr_events:
        print("[WubyOCR] Không có track cần xóa; dùng video gốc.")
        return input_video

    cap = cv2.VideoCapture(input_video)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1080)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1920)
    out_dir = Path(output_video).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_cleaned = str(out_dir / f"cleaned_{Path(output_video).name}")
    writer = cv2.VideoWriter(temp_cleaned, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Không mở được VideoWriter: {temp_cleaned}")

    frame_idx = 0
    events = sorted(ocr_events, key=lambda e: e["start"])
    print(f"[WubyOCR] Xóa chữ theo {len(events)} track, method={method}...")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_idx / fps
        active = [ev for ev in events if ev["start"] <= t < ev["end"]]
        for ev in active:
            box, tracked_bg = interpolate_track_state(ev, t)
            bx, by, bw, bh = [int(round(v)) for v in box]
            x1 = max(0, bx - padding)
            y1 = max(0, by - padding)
            x2 = min(w - 1, bx + max(1, bw) + padding)
            y2 = min(h - 1, by + max(1, bh) + padding)
            if x2 <= x1 or y2 <= y1:
                continue

            if method.lower() == "inpaint":
                mask8 = np.zeros((h, w), dtype=np.uint8)
                cv2.rectangle(mask8, (x1, y1), (x2, y2), 255, -1)
                frame = cv2.inpaint(frame, mask8, 3, cv2.INPAINT_TELEA)
                continue

            bg = tracked_bg
            if live_background_sampling:
                live_bg, _ = _sample_background(frame, [bx, by, bw, bh], margin=max(8, padding))
                bg = live_bg
            mask = _feather_mask(h, w, (x1, y1, x2, y2), feather_px)
            frame_f = frame.astype(np.float32)
            patch = np.empty_like(frame_f)
            patch[:, :] = np.array(bg, dtype=np.float32)
            m3 = mask[:, :, None]
            frame = (patch * m3 + frame_f * (1.0 - m3)).clip(0, 255).astype(np.uint8)

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    temp_with_audio = str(out_dir / f"audio_{Path(output_video).name}")
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", temp_cleaned, "-i", input_video,
        "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v:0", "-map", "1:a:0?", temp_with_audio,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        if os.path.exists(temp_with_audio) and os.path.getsize(temp_with_audio) > 1000:
            try:
                os.remove(temp_cleaned)
            except OSError:
                pass
            temp_cleaned = temp_with_audio
    except Exception as exc:
        print(f"[WubyOCR] Cảnh báo mux audio: {exc}")
    print(f"[WubyOCR] Video nền sạch: {temp_cleaned}")
    return temp_cleaned


def _sec_to_ass(s: float) -> str:
    s = max(0.0, float(s))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def _escape_ass(text: str) -> str:
    return (text or "").replace("{", "（").replace("}", "）")


def _format_vi_text(text: str, bw: float, vid_w: int) -> str:
    text = _escape_ass(text.strip())
    if len(text) > 18 and " " in text and bw < vid_w * 0.6:
        words = text.split()
        mid = len(words) // 2
        return " ".join(words[:mid]) + r"\N" + " ".join(words[mid:])
    return text


def _title_interval(
    title_config: Dict[str, Any],
    scene_ranges: Optional[List[Dict[str, Any]]],
    video_duration: Optional[float],
) -> Tuple[float, float]:
    start = float(title_config.get("start_sec", 0.0))
    mode = str(title_config.get("mode", "intro_scene")).lower()
    if mode == "full_video":
        end = float(video_duration or 35999.0)
    elif mode == "fixed":
        end = start + float(title_config.get("duration_sec", 3.0))
    else:  # intro_scene
        if scene_ranges:
            first = scene_ranges[0]
            end = float(first["end"]) - float(title_config.get("end_padding_before_scene_cut_sec", 0.08))
        else:
            end = start + float(title_config.get("duration_sec", 3.0))
    return start, max(start + 0.04, end)


def build_wuby_ass_subtitles(
    out_ass_path: Path,
    vid_w: int,
    vid_h: int,
    ocr_events: List[Dict[str, Any]],
    movie_title: Optional[str] = None,
    title_config: Optional[Dict[str, Any]] = None,
    scene_ranges: Optional[List[Dict[str, Any]]] = None,
    video_duration: Optional[float] = None,
    follow_motion: bool = True,
    min_font_size: int = 34,
    max_font_size: int = 56,
) -> Path:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {vid_w}
PlayResY: {vid_h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TitleCard,Arial,52,&H0000E6FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,8,30,30,45,1
Style: WubyWhiteText,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,5,10,10,10,1
Style: WubyBlackText,Arial,48,&H00000000,&H000000FF,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: List[str] = []
    tc = title_config or {"enabled": True, "mode": "intro_scene"}
    if movie_title and movie_title.strip() and tc.get("enabled", True):
        ts, te = _title_interval(tc, scene_ranges, video_duration)
        fad_in = int(tc.get("fade_in_ms", 100))
        fad_out = int(tc.get("fade_out_ms", 120))
        t_text = _escape_ass(movie_title.strip().upper())
        lines.append(
            f"Dialogue: 1,{_sec_to_ass(ts)},{_sec_to_ass(te)},TitleCard,,0,0,0,,"
            f"{{\\q2\\b1\\fad({fad_in},{fad_out})}}{t_text}{{\\b0}}"
        )

    for ev in ocr_events:
        vi = (ev.get("vi_text") or "").strip()
        if not vi:
            continue
        is_banner = bool(ev.get("is_banner", False))
        bg = ev.get("bg_bgr", [255, 255, 255])
        b, g, r = bg
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        style = "TitleCard" if is_banner else ("WubyBlackText" if brightness > 160 else "WubyWhiteText")
        union_box = ev.get("box", [0, 0, vid_w * 0.5, 80])
        est_fs = max(min_font_size, min(max_font_size, int(round(union_box[3] * 0.55))))
        if is_banner:
            est_fs = max(est_fs, 46)
        text = _format_vi_text(vi, union_box[2], vid_w)
        kfs = ev.get("keyframes") or []

        # Chỉ áp dụng hiệu ứng \move nếu vật thể thực sự di chuyển đáng kể (> 35px)
        centers = np.array([_center(k["box"]) for k in kfs], dtype=np.float32) if len(kfs) >= 2 else []
        center_span = float(np.linalg.norm(centers.max(axis=0) - centers.min(axis=0))) if len(centers) else 0.0
        is_real_movement = follow_motion and len(kfs) >= 2 and ev.get("motion_type") == "MOVE" and center_span > 35.0

        if is_real_movement:
            points: List[Tuple[float, List[float]]] = [(ev["start"], interpolate_track_state(ev, ev["start"])[0])]
            points.extend((float(k["time"]), list(k["box"])) for k in kfs if ev["start"] < k["time"] < ev["end"])
            points.append((ev["end"], interpolate_track_state(ev, ev["end"])[0]))
            dedup = []
            for p in points:
                if not dedup or p[0] - dedup[-1][0] > 0.01:
                    dedup.append(p)
            for (ta, ba), (tb, bb) in zip(dedup[:-1], dedup[1:]):
                if tb <= ta:
                    continue
                cxa, cya = _center(ba)
                cxb, cyb = _center(bb)
                tag = f"{{\\move({int(cxa)},{int(cya)},{int(cxb)},{int(cyb)})\\fs{est_fs}\\b1}}"
                lines.append(
                    f"Dialogue: 2,{_sec_to_ass(ta)},{_sec_to_ass(tb)},{style},,0,0,0,,{tag}{text}{{\\b0}}"
                )
        else:
            box, _ = interpolate_track_state(ev, (ev["start"] + ev["end"]) / 2.0)
            cx, cy = _center(box)
            lines.append(
                f"Dialogue: 2,{_sec_to_ass(ev['start'])},{_sec_to_ass(ev['end'])},{style},,0,0,0,,"
                f"{{\\pos({int(cx)},{int(cy)})\\fs{est_fs}\\b1}}{text}{{\\b0}}"
            )

    out_ass_path = Path(out_ass_path)
    out_ass_path.parent.mkdir(parents=True, exist_ok=True)
    out_ass_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"[WubyOCR] ASS: {out_ass_path}")
    return out_ass_path


def run_track_qc(
    tracks: List[Dict[str, Any]],
    vid_w: int,
    vid_h: int,
    max_mask_ratio: float = 0.35,
    max_track_duration_sec: float = 12.0,
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    frame_area = max(1.0, float(vid_w * vid_h))
    for ev in tracks:
        if ev["end"] > ev.get("scene_end", ev["end"]) + 1e-6:
            warnings.append({"track_id": ev["track_id"], "type": "scene_overflow", "detail": "Track vượt scene_end"})
        duration = ev["end"] - ev["start"]
        if duration > max_track_duration_sec:
            warnings.append({"track_id": ev["track_id"], "type": "long_track", "detail": round(duration, 3)})
        bx, by, bw, bh = ev["box"]
        ratio = (bw * bh) / frame_area
        if ratio > max_mask_ratio:
            warnings.append({"track_id": ev["track_id"], "type": "large_union_box", "detail": round(ratio, 4)})
        for k in ev.get("keyframes", []):
            x, y, w, h = k["box"]
            if x < 0 or y < 0 or x + w > vid_w + 2 or y + h > vid_h + 2:
                warnings.append({"track_id": ev["track_id"], "type": "box_outside_frame", "detail": k["box"]})
                break
    return warnings
