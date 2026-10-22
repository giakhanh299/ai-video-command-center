from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from backend import movie_voice_matcher, sub_processor

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "backend" / "channels_config.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Whisper + F0 voice-bank test for Cấu hình 2 Clone Phim")
    ap.add_argument("input", help="Video/audio source to analyse")
    ap.add_argument("--model", default=None, help="Optional faster-whisper model override, e.g. medium or large-v3")
    ap.add_argument("--out", default=None, help="JSON report path")
    args = ap.parse_args()

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Input not found: {src}")

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    movie_cfg = cfg["presets"]["cauhinh2"]["movie_voice_match"]
    report_path = Path(args.out).resolve() if args.out else src.with_suffix(".movie_voice_test.json")

    with tempfile.TemporaryDirectory(prefix="movie_clone_whisper_") as td:
        wav = Path(td) / "source_16k.wav"
        sub_processor.extract_audio_for_transcription(str(src), str(wav))
        transcriber = sub_processor.WhisperTranscriber(args.model)
        segments = transcriber.transcribe(str(wav))
        if not segments:
            raise SystemExit("Whisper did not find speech segments.")

    report = movie_voice_matcher.match_whisper_segments(
        str(src), segments, segments,
        config_data=cfg,
        cfg=movie_cfg,
        report_path=str(report_path),
    )

    print("\n=== WHISPER → F0 → VOICE MATCH ===")
    for row in report["source_segments"]:
        f0 = row.get("source_f0") or {}
        hz = f0.get("median_f0_hz")
        top = row.get("top3") or []
        top_txt = ", ".join(f"{x['profile']} {x['reference_hz']}Hz" for x in top)
        print(
            f"{row['index']:03d}  {row['start']:7.2f}-{row['end']:7.2f}s  "
            f"F0={hz if hz is not None else 'N/A'}  -> {row['profile']}  | {row['text']}"
        )
        if top_txt:
            print(f"      top3: {top_txt}")

    stats = report.get("stats") or {}
    print(f"\nF0 coverage: {float(stats.get('f0_coverage', 0))*100:.1f}%")
    print(f"Voices used: {', '.join(stats.get('unique_voices') or [])}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
