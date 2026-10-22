#!/usr/bin/env python3
"""
make_giai_phap_3.py - Giải pháp 3: Mô hình Thay thế (VieNeu-TTS v3 Turbo 48kHz / ONNX Direct Acoustic Modeling)
- Sử dụng mô hình VieNeu-TTS v3 Turbo (48kHz direct acoustic tokens & x-vector voice cloning).
- Chuyển ngữ mượt mà từ audio tiếng Trung sang tiếng Việt mà không bị lệ thuộc vào nhịp điệu xẹp hơi của câu gốc.
- Tạo file: tests/giai_phap_3_multilingual_clone.wav
"""
import os
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
TESTS_DIR = BASE_DIR / "tests"
TESTS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"

ref_tuned = SAMPLE_DIR / "character_tuned.ref.wav"
if not ref_tuned.exists():
    ref_tuned = SAMPLE_DIR / "character_original.ref.wav"

out_wav = TESTS_DIR / "giai_phap_3_multilingual_clone.wav"

print("--- [GIẢI PHÁP 3] VieNeu-TTS v3 Turbo 48kHz Acoustic Modeling ---")
print(f"Reference: {ref_tuned}")

from vieneu import Vieneu

print("Khởi tạo VieNeu v3 Turbo ONNX engine...")
t0 = time.time()
tts = Vieneu(mode="v3turbo", backend="onnx")
print(f"Ready in {time.time() - t0:.2f}s!")

text = "Gửi cho người không để ý đến bạn xem. Em bận thì cứ bận đi."
print(f"Đang sinh giọng cho câu: '{text}'...")
t1 = time.time()
wav = tts.infer(text=text, ref_audio=str(ref_tuned))
elapsed = time.time() - t1
print(f"✅ Hoàn thành sinh âm thanh trong {elapsed:.2f}s!")

sr = getattr(tts, "sample_rate", 48000)
wav = np.asarray(wav, dtype=np.float32).reshape(-1)

# Normalize volume
peak = np.max(np.abs(wav))
if peak > 0.95:
    wav = wav * (0.95 / peak)

sf.write(str(out_wav), wav, sr, subtype="PCM_16")
print(f"✅ Đã lưu kết quả Giải pháp 3: {out_wav} ({len(wav)/sr:.2f}s, SR={sr})")
