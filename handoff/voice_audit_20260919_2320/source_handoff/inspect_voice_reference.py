#!/usr/bin/env python3
"""
inspect_voice_reference.py - Voice Reference Audio Quality Inspector.

Inspects voice reference files (*.ref.wav, *.wav, *.mp3) for zero-shot voice cloning.
Evaluates:
- Duration (3 - 10s optimal)
- Sample rate & channels (mono preferred)
- RMS energy & loudness (dBFS)
- Peak amplitude & clipping detection
- Silence % and Estimated Speech Ratio
- Status: GOOD_FOR_CLONING or REFERENCE_AUDIO_BAD
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np
import soundfile as sf

# UTF-8 terminal output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def inspect_audio_file(file_path: str | Path) -> Dict[str, Any]:
    path = Path(file_path).resolve()
    if not path.exists():
        return {
            "path": str(path),
            "status": "REFERENCE_AUDIO_BAD",
            "reason": f"File does not exist: {path}",
        }

    file_size_bytes = path.stat().st_size
    if file_size_bytes < 1024:
        return {
            "path": str(path),
            "file_size": file_size_bytes,
            "status": "REFERENCE_AUDIO_BAD",
            "reason": f"File is corrupt or too small ({file_size_bytes} bytes)",
        }

    try:
        info = sf.info(str(path))
    except Exception as exc:
        return {
            "path": str(path),
            "file_size": file_size_bytes,
            "status": "REFERENCE_AUDIO_BAD",
            "reason": f"Cannot read audio metadata: {exc}",
        }

    try:
        audio, sr = sf.read(str(path), dtype="float32", always_2d=False)
    except Exception as exc:
        return {
            "path": str(path),
            "file_size": file_size_bytes,
            "status": "REFERENCE_AUDIO_BAD",
            "reason": f"Cannot decode audio: {exc}",
        }

    x = np.asarray(audio, dtype=np.float32)
    channels = 1
    if x.ndim > 1:
        channels = x.shape[1]
        x = x.mean(axis=1)

    duration = float(len(x) / max(1, sr))
    peak = float(np.max(np.abs(x))) if len(x) > 0 else 0.0
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12))
    loudness_db = 20.0 * math.log10(max(rms, 1e-9))

    # Clipping detection: samples near full scale (-0.05 dBFS)
    clip_mask = np.abs(x) >= 0.995
    clip_ratio = float(np.mean(clip_mask))
    is_clipping = clip_ratio > 0.002  # > 0.2% clipped

    # Frame-based silence / speech ratio estimation
    # 25ms window, 10ms hop
    frame_len = max(1, int(sr * 0.025))
    hop_len = max(1, int(sr * 0.010))
    n_frames = max(1, (len(x) - frame_len) // hop_len + 1)

    silence_frames = 0
    # Dynamic silence threshold: -42 dBFS or 20 dB below peak
    peak_db = 20.0 * math.log10(max(peak, 1e-9))
    silence_thresh_db = max(-45.0, peak_db - 24.0)

    for i in range(n_frames):
        start = i * hop_len
        end = start + frame_len
        chunk = x[start:end]
        c_rms = np.sqrt(np.mean(np.square(chunk)) + 1e-12)
        c_db = 20.0 * math.log10(max(c_rms, 1e-9))
        if c_db < silence_thresh_db:
            silence_frames += 1

    silence_ratio = float(silence_frames / n_frames)
    speech_ratio = float(max(0.0, 1.0 - silence_ratio))

    # Assessment
    bad_reasons = []
    if duration < 2.5:
        bad_reasons.append(f"Duration too short ({duration:.2f}s < 2.5s)")
    elif duration > 18.0:
        bad_reasons.append(f"Duration too long ({duration:.2f}s > 18.0s)")

    if rms < 0.003 or loudness_db < -48.0:
        bad_reasons.append(f"Audio energy too low / silent (RMS: {rms:.5f}, {loudness_db:.1f} dBFS)")

    if is_clipping:
        bad_reasons.append(f"Severe clipping detected ({clip_ratio * 100:.2f}% samples)")

    if speech_ratio < 0.40:
        bad_reasons.append(f"Insufficient speech ratio ({speech_ratio * 100:.1f}% < 40%)")

    status = "GOOD_FOR_CLONING" if not bad_reasons else "REFERENCE_AUDIO_BAD"

    return {
        "path": str(path),
        "filename": path.name,
        "file_size": file_size_bytes,
        "duration": duration,
        "sample_rate": sr,
        "channels": "mono" if channels == 1 else f"stereo ({channels}ch)",
        "codec": f"{info.format} / {info.subtype}",
        "rms": rms,
        "loudness_db": loudness_db,
        "peak": peak,
        "clipping": is_clipping,
        "clip_ratio": clip_ratio,
        "silence_pct": silence_ratio * 100.0,
        "speech_ratio": speech_ratio,
        "status": status,
        "reasons": bad_reasons,
    }


def print_report(res: Dict[str, Any]) -> None:
    print("=" * 60)
    print(f"Reference:\n{res.get('filename', res.get('path'))}\n")
    if "duration" in res:
        print(f"Path:         {res['path']}")
        print(f"File size:    {res['file_size']:,} bytes")
        print(f"Duration:     {res['duration']:.2f} s")
        print(f"Sample rate:  {res['sample_rate']} Hz")
        print(f"Channels:     {res['channels']}")
        print(f"Codec:        {res['codec']}")
        print(f"RMS / Loud:   {res['rms']:.5f} ({res['loudness_db']:.1f} dBFS)")
        print(f"Peak:         {res['peak']:.4f}")
        print(f"Clipping:     {'true' if res['clipping'] else 'false'}")
        print(f"Silence:      {res['silence_pct']:.1f}%")
        print(f"Speech ratio: {res['speech_ratio']:.2f}")
    else:
        print(f"Reason:       {res.get('reason')}")

    print("-" * 60)
    print(f"STATUS: {res['status']}")
    if res.get("reasons"):
        for r in res["reasons"]:
            print(f"  - WARNING: {r}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect reference audio quality for zero-shot voice cloning")
    parser.add_argument("audio", help="Path to audio file (*.ref.wav, *.wav, *.mp3)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    res = inspect_audio_file(args.audio)
    if args.json:
        import json
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print_report(res)

    return 0 if res["status"] == "GOOD_FOR_CLONING" else 1


if __name__ == "__main__":
    sys.exit(main())
