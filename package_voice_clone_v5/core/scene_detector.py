"""Scene-boundary detection utilities for the Wuby pipeline.

The detector is intentionally lightweight: it analyses every frame at a small
resolution and detects hard cuts from frame-to-frame luminance change.  The
result is used as a safety boundary: OCR tracks, masks and intro titles are not
allowed to leak into the following scene.
"""
from __future__ import annotations

from typing import Any, Dict, List

import cv2
import numpy as np


def detect_scene_ranges(
    video_path: str,
    diff_threshold: float = 28.0,
    min_scene_sec: float = 0.35,
    analysis_width: int = 160,
) -> List[Dict[str, Any]]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Không thể mở video để dò scene: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 else 0.0
    min_gap_frames = max(1, int(round(min_scene_sec * fps)))

    cuts = [0]
    prev = None
    frame_idx = 0
    last_cut = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        h, w = frame.shape[:2]
        small_h = max(1, int(round(h * analysis_width / max(w, 1))))
        small = cv2.resize(frame, (analysis_width, small_h), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if prev is not None and (frame_idx - last_cut) >= min_gap_frames:
            score = float(np.mean(cv2.absdiff(gray, prev)))
            if score >= diff_threshold:
                cuts.append(frame_idx)
                last_cut = frame_idx
        prev = gray
        frame_idx += 1

    cap.release()

    actual_frames = frame_idx or frame_count
    if actual_frames <= 0:
        return [{"scene_id": 0, "start": 0.0, "end": 0.0, "start_frame": 0, "end_frame": 0}]

    if cuts[-1] != actual_frames:
        cuts.append(actual_frames)

    ranges: List[Dict[str, Any]] = []
    for scene_id, (a, b) in enumerate(zip(cuts[:-1], cuts[1:])):
        ranges.append({
            "scene_id": scene_id,
            "start": a / fps,
            "end": b / fps,
            "start_frame": a,
            "end_frame": max(a, b - 1),
        })

    # Preserve metadata even when container frame count is slightly inaccurate.
    if ranges and duration > ranges[-1]["end"]:
        ranges[-1]["end"] = duration
    return ranges


def scene_for_time(scene_ranges: List[Dict[str, Any]], t: float) -> Dict[str, Any]:
    if not scene_ranges:
        return {"scene_id": 0, "start": 0.0, "end": float("inf")}
    for scene in scene_ranges:
        if scene["start"] <= t < scene["end"]:
            return scene
    return scene_ranges[-1]
