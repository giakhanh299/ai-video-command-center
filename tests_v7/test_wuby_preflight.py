from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import wuby_preflight


def _make_video(path: Path, width=180, height=320, fps=12, frames=24):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    assert writer.isOpened()
    for i in range(frames):
        img = np.full((height, width, 3), 40 + (i % 5) * 8, dtype=np.uint8)
        x = (i * 5) % max(1, width - 35)
        cv2.rectangle(img, (x, 120), (x + 30, 155), (230, 230, 230), -1)
        writer.write(img)
    writer.release()


def test_analyze_frame_geometry_preserves_portrait_source(tmp_path):
    video = tmp_path / "portrait.mp4"
    _make_video(video)
    result = wuby_preflight.analyze_frame_geometry(str(video), sample_frames=12)
    assert result["width"] == 180
    assert result["height"] == 320
    assert result["orientation"] == "portrait"
    assert result["preserve_source_fps"] is True
    assert result["preserve_source_resolution"] is True
    assert result["suggested_ocr_fps"] >= 8


def test_summarize_ocr_coverage():
    targets = [
        {"start": 0.0, "end": 1.0, "text": "a"},
        {"start": 1.1, "end": 2.0, "text": "b"},
    ]
    events = [
        {"start": 0.0, "end": 1.0, "box": [20, 120, 100, 30], "vi_text": "a", "is_banner": False, "motion_type": "STATIC"},
        {"start": 1.1, "end": 2.0, "box": [25, 122, 100, 30], "vi_text": "b", "is_banner": False, "motion_type": "MOVE"},
    ]
    out = wuby_preflight.summarize_ocr(events, targets, 180, 320)
    assert out["segment_coverage"] == 1.0
    assert out["moving_track_count"] == 1
    assert out["dialogue_track_count"] == 2


def test_voice_island_smoothing():
    assignments = [
        {"start": 0.0, "end": 1.0, "profile": "a"},
        {"start": 1.0, "end": 1.8, "profile": "b"},
        {"start": 1.8, "end": 3.0, "profile": "a"},
    ]
    changed = wuby_preflight._smooth_voice_islands(assignments, max_island_sec=1.0)
    assert changed == 1
    assert assignments[1]["profile"] == "a"
    assert assignments[1]["method"] == "wuby_island_smoothing"
