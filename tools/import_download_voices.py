import os
import sys
import glob
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import soundfile as sf
from faster_whisper import WhisperModel

BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path("D:/04_TAI_XUONG/DownLoad")
VOICE_SAMPLES_DIR = BASE_DIR / "voice_samples"
VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Tìm mô hình Whisper Large-v3 trong HF_CACHE
model_path = Path("D:/0.1_FACE_BOOK/DUNG_CHUNG/MODELS/HF_CACHE/hub/models--Systran--faster-whisper-large-v3")
snaps = list((model_path / "snapshots").glob("*"))
load_dir = str(snaps[0]) if snaps else "large-v3"

print(f"Đang nạp Faster-Whisper Large-v3 từ: {load_dir}...")
whisper = WhisperModel(load_dir, device="cuda", compute_type="float16")

# 2. Danh sách file âm thanh mới cần nhập từ D:/04_TAI_XUONG/DownLoad
audio_files = [
    "giongcuakienthuctaichinh.mp3",
    "giongcuakienthuctaichinh.wav",
    "giongnamcuonhut.mp3",
    "giongnammienbaclichsu.mp3",
    "giongnucamxuc.mp3",
    "giongnudiudang.mp3",
    "giongnutretrung.mp3",
    "huyen-clear-confident-narrator.mp3",
]

print("\n" + "=" * 60)
print("TIẾN TRÌNH IMPORT GIỌNG NÓI TỪ D:\\04_TAI_XUONG\\DownLoad VÀO voice_samples")
print("=" * 60)

for filename in audio_files:
    src_audio = DOWNLOAD_DIR / filename
    if not src_audio.exists():
        print(f"Bỏ qua: không tìm thấy {src_audio}")
        continue

    stem = src_audio.stem
    dest_audio = VOICE_SAMPLES_DIR / src_audio.name
    dest_txt = VOICE_SAMPLES_DIR / f"{stem}.txt"
    src_txt = DOWNLOAD_DIR / f"{stem}.txt"

    # Copy audio sang voice_samples
    shutil.copy2(src_audio, dest_audio)
    print(f"\n[+] Đã copy: {src_audio.name} -> voice_samples/")

    # Lấy hoặc bóc transcript text
    text_content = ""
    if src_txt.exists():
        text_content = src_txt.read_text(encoding="utf-8").strip()
        print(f"    (Có sẵn text từ D:\\04_TAI_XUONG\\DownLoad: {len(text_content)} ký tự)")
    else:
        print(f"    Đang nhận diện giọng nói (Whisper Large-v3) để sinh {dest_txt.name}...")
        segments, info = whisper.transcribe(str(src_audio), language="vi")
        text_content = " ".join(s.text.strip() for s in segments).strip()
        # Lưu cả ở D:/04_TAI_XUONG/DownLoad và voice_samples
        src_txt.write_text(text_content, encoding="utf-8")

    dest_txt.write_text(text_content, encoding="utf-8")
    info = sf.info(str(dest_audio))
    print(f"    Thời lượng: {info.duration:.2f}s | Sample rate: {info.samplerate}Hz | Kênh: {info.channels}")
    print(f"    Lời thoại ({len(text_content)} ký tự):\n    \"{text_content}\"")

print("\n" + "=" * 60)
print("HOÀN TẤT NHẬP TẤT CẢ GIỌNG TỪ D:\\04_TAI_XUONG\\DownLoad VÀO voice_samples!")
print("=" * 60)
