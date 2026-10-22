from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from backend import sub_processor, wuby_preflight

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "backend" / "channels_config.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Wuby dry preflight: frame/scene/OCR/Whisper/F0 without final render")
    ap.add_argument("input", help="Video source to analyse")
    ap.add_argument("--model", default=None, help="Optional faster-whisper model override")
    ap.add_argument("--out", default=None, help="JSON report path")
    args = ap.parse_args()

    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Input not found: {src}")

    cfg_data = json.loads(CONFIG.read_text(encoding="utf-8"))
    pre_cfg = cfg_data["workflows"]["wuby"]["settings"]["wuby_preflight"]
    report_path = Path(args.out).resolve() if args.out else src.with_suffix(".wuby_preflight.json")

    with tempfile.TemporaryDirectory(prefix="wuby_preflight_whisper_") as td:
        wav = Path(td) / "source_16k.wav"
        sub_processor.extract_audio_for_transcription(str(src), str(wav))
        transcriber = sub_processor.WhisperTranscriber(args.model)
        segments = transcriber.transcribe(str(wav))

    report = wuby_preflight.analyze_wuby_preflight(
        video_path=str(src),
        source_segments=segments,
        target_segments=segments,  # dry test only; production uses translated Vietnamese cues
        srt_path=None,
        movie_title=src.stem,
        config_data=cfg_data,
        cfg=pre_cfg,
        report_path=str(report_path),
    )

    v = report.get("visual") or {}
    o = (report.get("ocr") or {}).get("summary") or {}
    vs = (report.get("voice") or {}).get("summary") or {}
    rp = report.get("render_plan") or {}
    print("\n=== WUBY PREFLIGHT ===")
    print(f"Frame : {v.get('width')}x{v.get('height')} @ {v.get('fps')}fps | {v.get('orientation')}")
    print(f"Motion: {v.get('motion_class')} | OCR plan: {rp.get('ocr_sample_fps')}fps")
    print(f"Scenes: {(report.get('scenes') or {}).get('count', 0)}")
    print(f"OCR   : {o.get('track_count', 0)} tracks | segment coverage {float(o.get('segment_coverage', 0))*100:.1f}%")
    print(f"Voice : F0 coverage {float(vs.get('f0_coverage', 0))*100:.1f}% | {vs.get('unique_voice_count', 0)} voices")
    print(f"Hybrid frame allowed: {rp.get('hybrid_frame_allowed')}")
    print(f"QC warnings: {rp.get('warning_count', 0)}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
