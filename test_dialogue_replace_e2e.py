"""End-to-End Test cho Dialogue Replacement (audio-separator GPU)
1. Tách vocal & nhạc nền từ video
2. Kiểm tra cache hit
3. Lồng nhạc nền + voice mới, loại bỏ 100% vocal gốc
4. Kiểm tra luật không fallback về audio gốc khi có lỗi
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dialogue_replace import (
    prepare_dialogue_replacement,
    final_mix_hard_replace,
    apply_final_audio,
    _get_ffmpeg_exe,
    DEFAULT_MODEL,
    AUDIO_SEP_MODEL_DIR,
    AUDIO_SEP_PYTHON,
)


def create_sample_video(output_mp4: Path, duration_sec: int = 4) -> Path:
    """Tạo video test 4 giây kèm audio test."""
    ffmpeg = _get_ffmpeg_exe()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_sec}:size=640x360:rate=24",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_sec}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_mp4)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_mp4


def main():
    print("=" * 60)
    print("BẮT ĐẦU KIỂM THỬ TÍNH NĂNG DIALOGUE REPLACEMENT (GPU)")
    print("=" * 60)

    work_dir = BASE_DIR / "workspace" / "test_dialogue_replace"
    work_dir.mkdir(parents=True, exist_ok=True)

    test_video = work_dir / "test_input_video.mp4"
    test_voice = BASE_DIR / "handoff" / "voice_audit_20260919_2320" / "khanh_original.wav"

    print("\n[Bước 1] Chuẩn bị video test...")
    create_sample_video(test_video, duration_sec=4)
    print(f"-> Đã tạo video test: {test_video} ({test_video.stat().st_size} bytes)")
    print(f"-> File voice mới:    {test_voice}")

    cache_dir = work_dir / "cache_stems"
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("\n[Bước 2] Bóc tách Vocal & Nhạc nền qua GPU (audio_sep_worker.py)...")
    t0 = time.time()
    res1 = prepare_dialogue_replacement(
        video_path=test_video,
        cache_root=cache_dir,
        model_filename=DEFAULT_MODEL,
        model_dir=AUDIO_SEP_MODEL_DIR,
        audio_sep_python=AUDIO_SEP_PYTHON,
        require_cuda=True,
    )
    t1 = time.time()
    print(f"-> Tách hoàn tất trong {round(t1 - t0, 2)} giây!")
    print(f"-> Cache hit:     {res1.get('cache_hit')}")
    print(f"-> Instrumental: {res1.get('instrumental')}")
    print(f"-> Vocals:       {res1.get('vocals')}")

    assert res1.get("instrumental") and Path(res1["instrumental"]).exists(), "Thiếu file instrumental!"
    assert res1.get("cache_hit") is False, "Lần đầu không được là cache hit!"

    print("\n[Bước 3] Kiểm tra cơ chế Cache Hit khi render lại...")
    t2 = time.time()
    res2 = prepare_dialogue_replacement(
        video_path=test_video,
        cache_root=cache_dir,
        model_filename=DEFAULT_MODEL,
        model_dir=AUDIO_SEP_MODEL_DIR,
        audio_sep_python=AUDIO_SEP_PYTHON,
        require_cuda=True,
    )
    t3 = time.time()
    print(f"-> Lần 2 hoàn tất trong {round(t3 - t2, 4)} giây!")
    print(f"-> Cache hit:     {res2.get('cache_hit')}")
    assert res2.get("cache_hit") is True, "Lần 2 phải cache hit thành công!"
    assert res2.get("instrumental") == res1.get("instrumental")

    print("\n[Bước 4] Ghép lồng nhạc nền + voice mới (triệt tiêu 100% vocal gốc)...")
    output_video = work_dir / "final_hard_replace.mp4"
    final_mix_hard_replace(
        rendered_video=test_video,
        instrumental_file=res1["instrumental"],
        new_voice_file=test_voice,
        output_video=output_video,
        instrumental_volume=0.8,
    )
    print(f"-> Đã xuất video cuối: {output_video} ({output_video.stat().st_size} bytes)")
    assert output_video.exists() and output_video.stat().st_size > 1000, "Xuất video thất bại!"

    print("\n[Bước 5] Kiểm tra LUẬT: Separator lỗi phải FAIL ngay, không được fallback audio gốc...")
    try:
        apply_final_audio(
            original_video=test_video,
            rendered_video=test_video,
            tts_voice_file=test_voice,
            final_output=work_dir / "should_fail.mp4",
            channel_config={
                "dialogue_replace": {
                    "enabled": True,
                    "hard_replace": True,
                    "model_filename": "non_existent_model_12345.onnx",
                }
            }
        )
        raise AssertionError("LỖI: Hệ thống không được phép thành công khi model sai!")
    except RuntimeError as exc:
        print(f"-> Đã chặn đúng luật! Ngoại lệ ném ra chuẩn xác:\n   {exc}")

    print("\n" + "=" * 60)
    print("TẤT CẢ 5 BƯỚC TEST ĐỀU THÀNH CÔNG VƯỢT TRỘI!")
    print("=" * 60)


if __name__ == "__main__":
    main()
