from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("FFMPEG_NOT_FOUND")
    return exe


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


def _extract_mono_f32(video_path: str, sr: int, out_raw: Path) -> None:
    cmd = [_ffmpeg(), "-y", "-v", "error", "-i", str(video_path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", str(out_raw)]
    subprocess.run(cmd, check=True)


def _autocorr_f0(frame: np.ndarray, sr: int, fmin: float, fmax: float) -> tuple[float | None, float]:
    x = frame.astype(np.float64, copy=False)
    x = x - np.mean(x)
    rms = float(np.sqrt(np.mean(x * x) + 1e-12))
    if rms < 0.004:
        return None, rms
    x *= np.hanning(len(x))
    corr = np.correlate(x, x, mode="full")[len(x) - 1 :]
    if corr[0] <= 1e-10:
        return None, rms
    lo = max(1, int(sr / fmax))
    hi = min(len(corr) - 1, int(sr / fmin))
    if hi <= lo:
        return None, rms
    region = corr[lo : hi + 1]
    lag = lo + int(np.argmax(region))
    confidence = float(corr[lag] / (corr[0] + 1e-12))
    if confidence < 0.28:
        return None, rms
    return float(sr / lag), rms


def estimate_source_pitch(
    video_path: str,
    segments: Iterable[Any] | None = None,
    *,
    sample_rate: int = 16000,
    fmin_hz: float = 70.0,
    fmax_hz: float = 420.0,
    max_analysis_sec: float = 75.0,
) -> dict[str, Any]:
    """Estimate median F0 from original speech windows. It measures pitch, not speaker identity."""
    with tempfile.TemporaryDirectory(prefix="pitch_match_") as td:
        raw = Path(td) / "source.f32"
        _extract_mono_f32(video_path, sample_rate, raw)
        audio = np.fromfile(raw, dtype=np.float32)

        intervals: list[tuple[float, float]] = []
        if segments:
            for seg in segments:
                t = _seg_times(seg)
                if t:
                    intervals.append(t)
        if not intervals:
            total = len(audio) / sample_rate
            intervals = [(0.0, min(total, max_analysis_sec))]

        frame_len = max(320, int(0.040 * sample_rate))
        hop = max(160, int(0.020 * sample_rate))
        f0s: list[float] = []
        qualities: list[float] = []
        analyzed = 0.0
        for st, en in intervals:
            if analyzed >= max_analysis_sec:
                break
            dur = min(en - st, max_analysis_sec - analyzed)
            if dur <= 0:
                continue
            a = max(0, int(st * sample_rate))
            b = min(len(audio), int((st + dur) * sample_rate))
            if b - a < frame_len:
                continue
            analyzed += dur
            for pos in range(a, b - frame_len + 1, hop):
                f0, rms = _autocorr_f0(np.asarray(audio[pos : pos + frame_len]), sample_rate, fmin_hz, fmax_hz)
                if f0 is not None:
                    f0s.append(f0)
                    qualities.append(rms)

        if len(f0s) < 12:
            raise RuntimeError(f"PITCH_NOT_ENOUGH_VOICED_FRAMES:{len(f0s)}")

        arr = np.asarray(f0s, dtype=np.float64)
        # Robustly trim out octave errors and music outliers.
        q1, q3 = np.percentile(arr, [20, 80])
        trimmed = arr[(arr >= q1) & (arr <= q3)]
        if len(trimmed) < 8:
            trimmed = arr
        median = float(np.median(trimmed))
        return {
            "median_f0_hz": round(median, 2),
            "p20_hz": round(float(np.percentile(arr, 20)), 2),
            "p80_hz": round(float(np.percentile(arr, 80)), 2),
            "voiced_frames": int(len(arr)),
            "analysis_seconds": round(float(analyzed), 2),
            "method": "autocorrelation_f0_median",
        }


def select_voice_by_pitch(video_path: str, voice_bank: list[dict[str, Any]], segments=None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or {}
    pitch = estimate_source_pitch(
        video_path,
        segments,
        sample_rate=int(cfg.get("sample_rate", 16000)),
        fmin_hz=float(cfg.get("f0_min_hz", 70.0)),
        fmax_hz=float(cfg.get("f0_max_hz", 420.0)),
        max_analysis_sec=float(cfg.get("max_analysis_sec", 75.0)),
    )
    src = float(pitch["median_f0_hz"])
    candidates: list[dict[str, Any]] = []
    for item in voice_bank or []:
        if not isinstance(item, dict) or item.get("enabled", True) is False:
            continue
        try:
            ref = float(item["reference_hz"])
            if ref <= 0:
                continue
            profile = str(item["profile"])
        except Exception:
            continue
        cents = abs(1200.0 * math.log2(src / ref))
        candidates.append({**item, "distance_cents": round(cents, 2), "distance_hz": round(abs(src - ref), 2), "profile": profile})
    if not candidates:
        raise RuntimeError("PITCH_VOICE_BANK_EMPTY")
    candidates.sort(key=lambda x: x["distance_cents"])
    chosen = candidates[0]
    result = {"source": pitch, "selected": chosen, "top3": candidates[:3]}
    report_path = cfg.get("report_path")
    if report_path:
        Path(report_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
