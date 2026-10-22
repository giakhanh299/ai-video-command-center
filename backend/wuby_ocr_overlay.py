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


def is_laughter_or_filler(text: str) -> bool:
    """Detect pure laughter or sound effect tokens produced by Whisper."""
    clean = (text or "").strip().lower()
    if not clean:
        return True
    clean_no_punct = re.sub(r"[^\w\s]", "", clean).strip()
    words = clean_no_punct.split()
    if not words:
        return True
    laughter_tokens = {
        "ha", "haha", "hahaha", "hahahaha", "hic", "hi", "hihi", "hihihi",
        "he", "hehe", "hehehe", "ho", "hoho", "hohoho", "hu", "huhu", "huhuhu",
        "cuoi"
    }
    all_laughter = all(
        w in laughter_tokens or
        bool(re.fullmatch(r"^(?:ha+|he+|hi+|ho+|hu+|hic+|haha+|hehe+|hihi+|hoho+|huhu+)+$", w, re.IGNORECASE))
        for w in words
    )
    return all_laughter


def classify_ocr_text(text: str) -> str:
    """Classify OCR text so each channel can choose what it wants to remove."""
    t = (text or "").strip()
    if not t:
        return "unknown"

    # Nhận diện các hiệu ứng onomatopoeia / meme (như emmm, wow, haha)
    # Ngay cả khi EasyOCR đọc nhầm chữ 'm' uốn lượn thành 皿, 血, 凹, 四
    clean_eff = re.sub(r"[\s@'\".,:;/\\()\-+!0-9IrRhH]", "", t).lower()
    if clean_eff in {"emmm", "emm", "wow", "haha", "hahaha", "hhh", "lol", "皿", "血", "四", "凹"} or (
        re.fullmatch(r"[emwnu皿血凹四]+", clean_eff) and len(clean_eff) >= 2
    ):
        return "effect"

    has_cn = has_chinese_char(t)
    has_latin = bool(re.search(r"[A-Za-z]", t))
    has_digit = bool(re.search(r"\d", t))
    if has_cn and (has_latin or has_digit):
        return "mixed_chinese"
    if has_cn:
        return "chinese"
    if has_latin:
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
                xs = [int(round(p[0])) for p in bbox]
                ys = [int(round(p[1])) for p in bbox]
                x1, y1 = max(0, min(xs)), max(0, min(ys))
                x2, y2 = min(w, max(xs)), min(h, max(ys))
                if x2 <= x1 or y2 <= y1:
                    continue
                bw = x2 - x1
                bh = y2 - y1

                # Phân biệt chữ hoạt hình/nghệ thuật (viền dày, màu nổi) với nét mặt/tiểu tiết:
                # EasyOCR thường hạ điểm rất thấp (prob < 0.10) đối với chữ hoạt hình màu vàng, viền đen dày.
                is_chinese = has_chinese_char(clean)
                if is_chinese:
                    if len(clean) >= 2 and (bw >= 100 or bh >= 25 or len(clean) >= 3):
                        pass  # Giữ lại chắc chắn chữ hoạt hình / phụ đề / chữ vàng
                    elif prob < 0.20:
                        continue
                    if len(clean) <= 1 and (prob < 0.25 or bw < 25 or bh < 25):
                        continue
                else:
                    if prob < min_confidence:
                        continue
                    if len(clean) <= 1 and prob < 0.70:
                        continue
                # V7: bottom captions are real text, not automatically noise.
                # The previous y>0.68 filter discarded short/medium-confidence captions.
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


def filter_semantic_ocr_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop unstable one-frame OCR fragments before translation or inpainting.

    At 24 fps, animated outlines and facial details can look like isolated Han
    characters. A readable caption must contain at least two Han characters and
    survive several samples. Rejected detections are never erased.
    """
    kept: List[Dict[str, Any]] = []
    rejected = 0
    for original in events:
        ev = dict(original)
        text = (ev.get("text") or "").strip()
        han_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        count = int(ev.get("count") or len(ev.get("keyframes") or []))
        duration = max(0.0, float(ev.get("end", 0.0)) - float(ev.get("start", 0.0)))
        stable = count >= 4 or (count >= 2 and duration >= 0.25)
        if han_count >= 2 and stable:
            # The tracker may end on one final, much clearer OCR sample. Adopt
            # it only when confidence jumps dramatically, so normal sequential
            # captions are not merged into each other.
            clearer = []
            for candidate in events:
                if candidate is original or candidate.get("scene_id") != ev.get("scene_id"):
                    continue
                c_text = (candidate.get("text") or "").strip()
                if len(re.findall(r"[\u4e00-\u9fff]", c_text)) < 2:
                    continue
                boundary_gap = min(
                    abs(float(candidate.get("start", 0.0)) - float(ev.get("end", 0.0))),
                    abs(float(ev.get("start", 0.0)) - float(candidate.get("end", 0.0))),
                )
                if boundary_gap <= 0.13 and _iou(ev.get("box", [0, 0, 0, 0]), candidate.get("box", [0, 0, 0, 0])) >= 0.5:
                    clearer.append(candidate)
            if clearer:
                best = max(clearer, key=lambda item: float(item.get("prob", 0.0)))
                old_prob = float(ev.get("prob", 0.0))
                best_prob = float(best.get("prob", 0.0))
                if best_prob >= max(0.002, old_prob * 20.0):
                    ev["ocr_text_before_refine"] = text
                    ev["text"] = (best.get("text") or text).strip()
                    print(f"[WubyOCR] Refine track#{ev.get('track_id')}: '{text}' -> '{ev['text']}'")
            kept.append(ev)
        else:
            rejected += 1
    if rejected:
        print(f"[WubyOCR] Lọc {rejected} track OCR không ổn định; giữ {len(kept)} track có nghĩa.")
    return kept


def extend_ocr_event_holds(
    events: List[Dict[str, Any]], hold_sec: float = 0.30
) -> List[Dict[str, Any]]:
    """Expand an OCR replacement window equally before and after its track.

    ``hold_sec=0.30`` means start 0.15s earlier and end 0.15s later. The
    expansion never crosses a scene boundary or another caption in the same
    screen region.
    """
    hold_sec = max(0.0, float(hold_sec))
    side_sec = hold_sec / 2.0
    ordered = sorted(events, key=lambda ev: (float(ev.get("start", 0.0)), int(ev.get("track_id", 0))))
    original_windows = {
        id(ev): (float(ev.get("start", 0.0)), float(ev.get("end", 0.0)))
        for ev in ordered
    }
    for ev in ordered:
        old_start, old_end = original_windows[id(ev)]
        scene_start = float(ev.get("scene_start", max(0.0, old_start - side_sec)))
        scene_end = float(ev.get("scene_end", old_end + side_sec))
        new_start = max(scene_start, old_start - side_sec)
        new_end = min(scene_end, old_end + side_sec)
        for other in ordered:
            if other is ev or other.get("scene_id") != ev.get("scene_id"):
                continue
            if _iou(ev.get("box", [0, 0, 0, 0]), other.get("box", [0, 0, 0, 0])) < 0.25:
                continue
            other_start, other_end = original_windows[id(other)]
            if other_end <= old_start + 1e-6:
                new_start = max(new_start, (other_end + old_start) / 2.0)
            if other_start >= old_end - 1e-6:
                new_end = min(new_end, (old_end + other_start) / 2.0)
        ev["start"] = min(old_start, new_start)
        ev["end"] = max(old_end, new_end)
        ev["lead_extension_sec"] = round(old_start - ev["start"], 3)
        ev["tail_extension_sec"] = round(ev["end"] - old_end, 3)
        ev["hold_extension_sec"] = round(
            ev["lead_extension_sec"] + ev["tail_extension_sec"], 3
        )
    return ordered


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
    # Phân tách câu thoại/ký tự: Nếu nội dung chữ thay đổi rõ rệt và không phải mở rộng chuỗi
    # (ví dụ: '你' -> '你忙' là mở rộng hợp lệ, nhưng '忙' -> '吧' là 2 ký tự hoàn toàn khác nhau)
    if sim < 0.35 and last_txt != det_txt:
        is_sub = (last_txt in det_txt) or (det_txt in last_txt)
        if not is_sub:
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
    vid_w: int = 1080,
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

    # Lọc bỏ các segment là ảo giác (hallucination/nhạc nền) HOẶC tiếng cười thuần túy
    try:
        from sub_processor import is_whisper_hallucination
    except Exception:
        def is_whisper_hallucination(t, **kw): return False

    filtered_subs: List[Dict[str, Any]] = []
    for s in sub_items:
        txt = s.get("text", "")
        dur = float(s.get("end", 0)) - float(s.get("start", 0))
        if txt and not is_whisper_hallucination(txt, duration=dur) and not is_laughter_or_filler(txt):
            filtered_subs.append(s)
    sub_items = filtered_subs

    def _watermark_key(text: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]+", "", (text or "").lstrip("@").strip(), flags=re.UNICODE)

    watermark_keys = {
        _watermark_key(ev.get("text", ""))
        for ev in ocr_events
        if (ev.get("text") or "").strip().startswith("@") and len(_watermark_key(ev.get("text", ""))) >= 3
    }

    # 1. Phân loại Top Banner (tiêu đề/chủ đề trên đầu), watermark và Dialogue.
    banner_events_to_translate: List[Dict[str, Any]] = []
    for ev in ocr_events:
        box = ev.get("box", [0, 0, 100, 50])
        cy = box[1] + box[3] / 2.0
        dur = ev["end"] - ev["start"]
        raw_text = (ev.get("text") or "").strip()
        wm_key = _watermark_key(raw_text)
        is_watermark = raw_text.startswith("@") or any(
            len(wm_key) >= 3 and (wm_key == key or wm_key in key or key in wm_key)
            for key in watermark_keys
        )
        ev["is_watermark"] = bool(is_watermark)
        if is_watermark:
            ev["vi_text"] = ""
            ev["source"] = "ignored_watermark"
            ev["is_banner"] = False
            continue

        wide_top_banner = float(box[2]) >= max(320.0, 0.55 * float(vid_w))
        is_top_banner = (cy < 0.28 * vid_h) and (
            dur >= 2.0 or wide_top_banner or ev.get("is_banner", False)
        )
        ev["is_banner"] = is_top_banner

        if is_top_banner:
            if has_chinese_char(raw_text):
                banner_events_to_translate.append(ev)
            else:
                title_text = (movie_title or raw_text).strip().upper()
                ev["vi_text"] = title_text
                ev["source"] = "banner_title"
            continue

        # 2. Dialogue tracks: Khớp 1-to-1 theo overlap thời gian chính xác nhất
        best_idx = -1
        best_overlap = -1.0
        for idx, sub in enumerate(sub_items):
            if sub.get("used", False):
                # A single subtitle may legitimately span two OCR fragments that
                # hand off sequentially in the same screen region. It must never
                # be reused for simultaneous regions (the duplicate-caption bug).
                prev_end = sub.get("_last_owner_end")
                prev_box = sub.get("_last_owner_box")
                sequential_handoff = (
                    prev_end is not None
                    and float(ev["start"]) >= float(prev_end) - 0.05
                    and prev_box is not None
                    and _iou(prev_box, box) >= 0.25
                )
                if not sequential_handoff:
                    continue
            overlap = min(ev["end"], sub["end"]) - max(ev["start"], sub["start"])
            if overlap > 0.05 and overlap > best_overlap:
                best_overlap = overlap
                best_idx = idx

        if best_idx >= 0:
            ev["vi_text"] = sub_items[best_idx]["text"]
            ev["source"] = "whisper_dialogue"
            sub_items[best_idx]["used"] = True
            sub_items[best_idx]["_last_owner_end"] = float(ev["end"])
            sub_items[best_idx]["_last_owner_box"] = list(box)
        else:
            # Nếu không tìm thấy overlap trực tiếp, tìm sub gần nhất chưa dùng trong phạm vi hợp lý
            ev_mid = (ev["start"] + ev["end"]) / 2.0
            candidates = [
                (idx, s, abs((s["start"] + s["end"]) / 2.0 - ev_mid))
                for idx, s in enumerate(sub_items)
                if not s.get("used", False)
            ]
            if candidates:
                closest_idx, closest_sub, dist = min(candidates, key=lambda x: x[2])
                if dist < 1.0 and (closest_sub["start"] - 0.5 <= ev_mid <= closest_sub["end"] + 0.5):
                    ev["vi_text"] = closest_sub["text"]
                    ev["source"] = "whisper_dialogue_proximity"
                    closest_sub["used"] = True
                else:
                    ev["vi_text"] = ""
            else:
                ev["vi_text"] = ""

    # Dịch độc lập cho Banner trên đầu có chữ Trung
    if banner_events_to_translate:
        try:
            from sub_processor import SubtitleTranslator, SubtitleSegment
            tr = SubtitleTranslator()
            segs = [SubtitleSegment(0.0, 1.0, ev.get("text", "").strip()) for ev in banner_events_to_translate]
            translated = tr.translate_segments(segs)
            for ev, trans in zip(banner_events_to_translate, translated):
                t_val = (trans.text or "").strip().upper()
                if not t_val or has_chinese_char(t_val):
                    t_val = (movie_title or ev.get("text", "")).strip().upper()
                ev["vi_text"] = t_val
                ev["source"] = "ocr_banner_translation"
        except Exception as b_err:
            print(f"[WubyOCR] Lỗi dịch banner: {b_err}")
            for ev in banner_events_to_translate:
                ev["vi_text"] = (movie_title or ev.get("text", "")).strip().upper()
                ev["source"] = "ocr_banner_fallback"

    # 3. Dịch độc lập cho TẤT CẢ các track chữ Trung mang nghĩa không có lời thoại Whisper tương ứng
    unassigned_chinese = [
        ev for ev in ocr_events
        if not ev.get("is_banner")
        and not ev.get("is_watermark")
        and not (ev.get("vi_text") or "").strip()
        and (has_chinese_char(ev.get("text", "")) or ev.get("text_class") in ("chinese", "mixed_chinese"))
    ]
    if unassigned_chinese:
        print(f"[WubyOCR] Phát hiện {len(unassigned_chinese)} track chữ Trung trên hình chưa có thoại, đang dịch độc lập...")
        try:
            from sub_processor import SubtitleTranslator, SubtitleSegment
            tr = SubtitleTranslator()
            segs = [SubtitleSegment(float(ev.get("start", 0.0)), float(ev.get("end", 1.0)), ev.get("text", "").strip()) for ev in unassigned_chinese]
            translated = tr.translate_segments(segs)
            for ev, trans in zip(unassigned_chinese, translated):
                res_txt = (trans.text or "").strip()
                if res_txt and not has_chinese_char(res_txt):
                    ev["vi_text"] = res_txt
                    ev["source"] = "ocr_translation"
                else:
                    ev["vi_text"] = ""
                    ev["source"] = "untranslated"
        except Exception as ocr_trans_err:
            print(f"[WubyOCR] Cảnh báo dịch chữ Trung trên hình thất bại: {ocr_trans_err}")
            for ev in unassigned_chinese:
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
    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        return str(input_video)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    out_dir = Path(output_video).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_cleaned = str(out_dir / f"clean_{Path(output_video).name}")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(temp_cleaned, fourcc, fps, (w, h))

    active_events = [
        ev for ev in ocr_events
        if ev.get("box") and (
            bool((ev.get("vi_text") or "").strip() and not has_chinese_char(ev.get("vi_text", "")))
            or ev.get("is_watermark")
        )
    ]
    vert_boxes = []
    try:
        from .video_merger import detect_vertical_left_watermark
        vert_boxes = detect_vertical_left_watermark(str(input_video)) or []
    except Exception:
        try:
            from video_merger import detect_vertical_left_watermark
            vert_boxes = detect_vertical_left_watermark(str(input_video)) or []
        except Exception:
            pass

    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        t = frame_idx / fps

        for v_box in vert_boxes:
            vx, vy, vw, vh = v_box['x'], v_box['y'], v_box['w'], v_box['h']
            mask_v = np.zeros((h, w), dtype=np.uint8)
            cv2.rectangle(mask_v, (vx, vy), (vx + vw, vy + vh), 255, -1)
            frame = cv2.inpaint(frame, mask_v, 3, cv2.INPAINT_TELEA)

        matching = [ev for ev in active_events if ev["start"] <= t <= ev["end"]]
        for ev in matching:
            box, bg = interpolate_track_state(ev, t)
            bx, by, bw, bh = box
            pad_x = int(bw * 0.04) + 3
            pad_y = int(bh * 0.06) + 3
            x1 = max(0, int(bx - pad_x))
            y1 = max(0, int(by - pad_y))
            x2 = min(w, int(bx + bw + pad_x))
            y2 = min(h, int(by + bh + pad_y))
            if x2 <= x1 or y2 <= y1:
                continue

            # Đo độ biến thiên (spread) của màu nền xung quanh bounding box
            roi = frame[y1:y2, x1:x2]
            spread = float(np.std(roi)) if roi.size > 0 else 0.0

            # Nếu nền không đồng nhất (ảnh chụp người, cảnh phức tạp, spread > 22.0)
            # -> Dùng Inpainting Telea để màu hòa trộn tự nhiên vào viền xung quanh, không để lại khối chữ nhật
            if spread > 22.0:
                mask8 = np.zeros((h, w), dtype=np.uint8)
                cv2.rectangle(mask8, (x1, y1), (x2, y2), 255, -1)
                frame = cv2.inpaint(frame, mask8, 3, cv2.INPAINT_TELEA)
                continue

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


def resolve_dialogue_collisions(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep distinct on-screen labels; arbitrate competing OCR tracks in one box."""
    def conflicts(a, b):
        ab = a.get("box", [0, 0, 0, 0])
        bb = b.get("box", [0, 0, 0, 0])
        return _iou(ab, bb) >= 0.25

    def priority(ev):
        source = ev.get("source", "")
        return (source == "whisper_dialogue", source.startswith("whisper_dialogue"),
                float(ev["end"]) - float(ev["start"]), len(ev.get("keyframes") or []))

    accepted = []
    for ev in sorted(events, key=priority, reverse=True):
        intervals = [(float(ev["start"]), float(ev["end"]))]
        for other in accepted:
            if not conflicts(ev, other):
                continue
            remaining = []
            for start, end in intervals:
                left, right = float(other["start"]), float(other["end"])
                if right <= start or left >= end:
                    remaining.append((start, end))
                else:
                    if left > start:
                        remaining.append((start, left))
                    if right < end:
                        remaining.append((right, end))
            intervals = remaining
        for start, end in intervals:
            if end - start >= 0.05:
                accepted.append({**ev, "start": start, "end": end})
    return sorted(accepted, key=lambda ev: (ev["start"], ev["end"]))


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
    tc = title_config or {"enabled": True, "mode": "intro_scene"}
    tc_fs = int(tc.get("font_size", 52))
    tc_mv = int(tc.get("margin_v", 45))

    has_global_title = bool(movie_title and movie_title.strip() and tc.get("enabled", True))
    t_text = ""
    if has_global_title:
        t_clean = _escape_ass(movie_title.strip().upper())
        if len(t_clean) > 20 and " " in t_clean and r"\N" not in t_clean:
            words = t_clean.split()
            mid = len(words) // 2
            t_text = " ".join(words[:mid]) + r"\N" + " ".join(words[mid:])
            tc_fs = min(tc_fs, 54)
        else:
            t_text = t_clean
            if len(t_clean) > 24:
                tc_fs = min(tc_fs, 52)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {vid_w}
PlayResY: {vid_h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TitleCard,Arial,{tc_fs},&H0000E6FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,8,30,30,{tc_mv},1
Style: WubyWhiteText,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,5,10,10,10,1
Style: WubyBlackText,Arial,48,&H00000000,&H000000FF,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: List[str] = []
    if has_global_title:
        ts, te = _title_interval(tc, scene_ranges, video_duration)
        fad_in = int(tc.get("fade_in_ms", 100))
        fad_out = int(tc.get("fade_out_ms", 120))
        lines.append(
            f"Dialogue: 1,{_sec_to_ass(ts)},{_sec_to_ass(te)},TitleCard,,0,0,0,,"
            f"{{\\q2\\b1\\fad({fad_in},{fad_out})}}{t_text}{{\\b0}}"
        )

    try:
        from sub_processor import is_whisper_hallucination
    except Exception:
        def is_whisper_hallucination(t, **kw): return False

    def _norm_txt(s: str) -> str:
        return re.sub(r'[\s\\N\-_:,\.!?]+', '', s or "").upper()

    # Lọc bỏ các track rác, ảo giác (nhạc, tiếng cười, boilerplate)
    valid_events = []
    for ev in ocr_events:
        vi = (ev.get("vi_text") or "").strip()
        dur = float(ev.get("end", 0.0)) - float(ev.get("start", 0.0))
        if not vi or is_whisper_hallucination(vi, duration=dur) or is_laughter_or_filler(vi):
            continue
        valid_events.append(ev)

    banner_events = [ev for ev in valid_events if ev.get("is_banner")]
    dialogue_events = [ev for ev in valid_events if not ev.get("is_banner")]

    # Nếu đã có TitleCard toàn cục ở Layer 1, chỉ loại bỏ các banner trùng hoàn toàn nội dung tiêu đề toàn cục
    if has_global_title:
        norm_global = _norm_txt(movie_title)
        banner_events = [bev for bev in banner_events if _norm_txt(bev.get("vi_text", "")) != norm_global]

    # Hợp nhất các banner cùng tên hoặc liền kề thời gian (tránh 4 dòng TitleCard giật nháy đè lên nhau)
    consolidated_banners: List[Dict[str, Any]] = []
    for bev in banner_events:
        vi = bev.get("vi_text", "").strip()
        nvi = _norm_txt(vi)
        matched = False
        for cb in consolidated_banners:
            ncb = _norm_txt(cb.get("vi_text", ""))
            if nvi == ncb or (len(nvi) >= 4 and len(ncb) >= 4 and (nvi in ncb or ncb in nvi)):
                if bev["start"] <= cb["end"] + 2.0 and cb["start"] <= bev["end"] + 2.0:
                    cb["start"] = min(cb["start"], bev["start"])
                    cb["end"] = max(cb["end"], bev["end"])
                    if len(vi) > len(cb.get("vi_text", "")):
                        cb["vi_text"] = vi
                    matched = True
                    break
        if not matched:
            consolidated_banners.append(dict(bev))

    final_banners: List[Dict[str, Any]] = []
    for cb in consolidated_banners:
        if not any(min(cb["end"], fb["end"]) > max(cb["start"], fb["start"]) for fb in final_banners):
            final_banners.append(cb)

    # Hợp nhất các bong bóng thoại của nhân vật có cùng nội dung thoại và giao thoa thời gian (< 0.35s)
    consolidated_dialogues: List[Dict[str, Any]] = []
    for dev in dialogue_events:
        vi = dev.get("vi_text", "").strip()
        nvi = _norm_txt(vi)
        matched = False
        for cd in consolidated_dialogues:
            ncd = _norm_txt(cd.get("vi_text", ""))
            if nvi == ncd and _iou(dev.get("box", [0, 0, 0, 0]), cd.get("box", [0, 0, 0, 0])) >= 0.25:
                if dev["start"] <= cd["end"] + 0.35 and cd["start"] <= dev["end"] + 0.35:
                    cd["start"] = min(cd["start"], dev["start"])
                    cd["end"] = max(cd["end"], dev["end"])
                    matched = True
                    break
        if not matched:
            consolidated_dialogues.append(dict(dev))

    final_events = final_banners + resolve_dialogue_collisions(consolidated_dialogues)

    for ev in final_events:
        vi = (ev.get("vi_text") or "").strip()
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

        # Chỉ áp dụng hiệu ứng \move nếu vật thể thực sự di chuyển đáng kể (> 50px)
        centers = np.array([_center(k["box"]) for k in kfs], dtype=np.float32) if len(kfs) >= 2 else []
        center_span = float(np.linalg.norm(centers.max(axis=0) - centers.min(axis=0))) if len(centers) else 0.0
        is_real_movement = follow_motion and len(kfs) >= 2 and ev.get("motion_type") == "MOVE" and center_span > 50.0

        if is_real_movement:
            ba = interpolate_track_state(ev, ev["start"])[0]
            bb = interpolate_track_state(ev, ev["end"])[0]
            cxa, cya = _center(ba)
            cxb, cyb = _center(bb)
            tag = f"{{\\move({int(cxa)},{int(cya)},{int(cxb)},{int(cyb)})\\fs{est_fs}\\b1}}"
            lines.append(
                f"Dialogue: 2,{_sec_to_ass(ev['start'])},{_sec_to_ass(ev['end'])},{style},,0,0,0,,{tag}{text}{{\\b0}}"
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
