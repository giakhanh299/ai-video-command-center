"""Configuration helpers for reusable multi-channel video processing."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "scene_detection": {
        "enabled": True,
        "diff_threshold": 28.0,
        "min_scene_sec": 0.35,
    },
    "ocr": {
        "sample_fps": 24.0,
        "min_confidence": 0.28,
        "max_duration": 3600.0,
        "remove_classes": ["chinese", "mixed_chinese"],
        "max_track_gap_sec": 0.65,
        "max_center_distance_px": 190.0,
        "pre_padding_sec": 0.08,
        "post_padding_factor": 0.75,
    },
    "erase": {
        "padding_px": 12,
        "method": "fill",
        "feather_px": 17,
        "live_background_sampling": True,
    },
    "subtitle": {
        "follow_motion": True,
        "max_font_size": 56,
        "min_font_size": 34,
    },
    "title_overlay": {
        "enabled": True,
        "mode": "intro_scene",
        "start_sec": 0.0,
        "duration_sec": 3.0,
        "end_padding_before_scene_cut_sec": 0.08,
        "fade_in_ms": 100,
        "fade_out_ms": 120,
    },
    "cache": {
        "enabled": True,
        "directory": ".cache",
    },
    "debug": {
        "enabled": True,
        "save_track_json": True,
    },
    "qc": {
        "enabled": True,
        "max_mask_ratio": 0.35,
        "max_track_duration_sec": 12.0,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def load_pipeline_config(
    config_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if config_path:
        p = Path(config_path)
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy config: {p}")
        config = _deep_merge(config, json.loads(p.read_text(encoding="utf-8")))
    if overrides:
        config = _deep_merge(config, overrides)
    return config
