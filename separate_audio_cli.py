"""CLI & Module Tach Vocal / Nhac Nen bang audio-separator GPU
Su dung moi truong: D:\\0.1_FACE_BOOK\\Lay video tiktok\\MOI_TRUONG\\audio_sep_env\\Scripts\\python.exe
Model ONNX MDX-Net: D:\\0.1_FACE_BOOK\\Lay video tiktok\\MODELS\\audio_separator\\UVR-MDX-NET-Inst_HQ_3.onnx
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from audio_separator_runner import separate_audio, DEFAULT_MODEL, AUDIO_SEP_MODELS_DIR


def extract_audio_from_video(video_path: Path, temp_wav: Path) -> Path:
    """Extract stereo 44.1kHz WAV from video container."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")
    cmd = [
        ffmpeg, "-y", "-v", "error",
        "-i", str(video_path),
        "-vn", "-ac", "2", "-ar", "44100",
        "-c:a", "pcm_s16le",
        str(temp_wav)
    ]
    subprocess.run(cmd, check=True)
    return temp_wav


def run_separation(
    media_path: str | Path,
    output_dir: str | Path | None = None,
    model_name: str = DEFAULT_MODEL,
) -> dict[str, str]:
    """Tach vocal va nhac nen tu file audio hoac video."""
    src = Path(media_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Khong tim thay file: {src}")

    target_dir = Path(output_dir).resolve() if output_dir else src.parent / f"{src.stem}_separated"
    target_dir.mkdir(parents=True, exist_ok=True)

    video_exts = {".mp4", ".mkv", ".mov", ".avi", ".flv", ".webm", ".m4v", ".ts"}
    temp_wav: Path | None = None

    try:
        input_audio = src
        if src.suffix.lower() in video_exts:
            print(f"[1/2] Dang trich xuat audio tu video: {src.name}...")
            temp_wav = target_dir / f"extracted_{src.stem}.wav"
            extract_audio_from_video(src, temp_wav)
            input_audio = temp_wav

        print(f"[2/2] Dang tach Vocal / Nhac nen bang GPU ({model_name})...")
        res = separate_audio(
            audio_path=input_audio,
            output_dir=target_dir,
            model_name=model_name,
        )

        print("\n==================================================")
        print("  TACH VOCAL & NHAC NEN HOAN TAT!")
        print("==================================================")
        print(f"• Model:        {res.get('model')}")
        print(f"• Nhac nen:     {res.get('instrumental')}")
        print(f"• Vocal/Thoai:  {res.get('vocals')}")
        print(f"• Thu muc luu:  {target_dir}")
        print("==================================================\n")
        return res
    finally:
        if temp_wav and temp_wav.exists():
            try:
                temp_wav.unlink()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Tach vocal/nhac nen truc tiep bang audio-separator GPU")
    parser.add_argument("input", nargs="?", help="Duong dan toi file audio hoac video")
    parser.add_argument("-i", "--input-file", dest="input_alt", help="Duong dan toi file audio/video")
    parser.add_argument("-o", "--output-dir", default=None, help="Thu muc xuat ket qua (mac dinh: canh file goc)")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Ten model (mac dinh: {DEFAULT_MODEL})")

    args = parser.parse_args()
    input_path = args.input or args.input_alt

    if not input_path:
        print("Vui long truyen duong dan file audio/video!")
        print("Vi du: python separate_audio_cli.py my_video.mp4")
        sys.exit(1)

    run_separation(
        media_path=input_path,
        output_dir=args.output_dir,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
