#!/usr/bin/env python3
"""
make_giai_phap_3_hd.py - Giải pháp 3: High-Definition Cross-Lingual Voice Clone (32-step ODE Flow Matching)
- Sử dụng 32 bước ODE tích phân (gấp đôi mặc định) để giải quyết triệt để phonetic mismatch giữa tiếng Trung và tiếng Việt.
- Tái tạo chi tiết formant dải cao và âm tiết rõ ràng.
"""
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
TESTS_DIR = BASE_DIR / "tests"
TESTS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"

ref_tuned = SAMPLE_DIR / "character_tuned.ref.wav"
out_wav = TESTS_DIR / "giai_phap_3_multilingual_clone.wav"

print("--- [GIẢI PHÁP 3] High-Definition 32-Step Flow Matching Voice Clone ---")
from omnivoice import OmniVoice

device = "cuda:0" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model = OmniVoice.from_pretrained(
    "kjanh/KhanhTTS-OmniVoice",
    device_map=device,
    dtype=dtype,
    load_asr=False
)

prompt = model.create_voice_clone_prompt(
    ref_audio=str(ref_tuned),
    ref_text="你不理你的人看你",
    preprocess_prompt=True
)

# Chạy cả 2 câu với 32 steps để tái tạo độ nét cực cao
text_full = "Gửi cho người không để ý đến bạn xem. Em bận thì cứ bận đi."
print(f"Đang sinh giọng với 32-step ODE: '{text_full}'...")
t0 = time.time()
res = model.generate(
    text=text_full,
    language="Vietnamese",
    voice_clone_prompt=prompt,
    num_step=32
)
t1 = time.time()
print(f"Hoàn thành trong {t1 - t0:.2f}s!")

audio = res[0] if isinstance(res, (list, tuple)) else res
audio = np.asarray(audio, dtype=np.float32).reshape(-1)
sr = 24000

# Normalize
peak = np.max(np.abs(audio))
if peak > 0.95:
    audio = audio * (0.95 / peak)

sf.write(str(out_wav), audio, sr, subtype="PCM_16")
print(f"✅ Đã lưu file Giải pháp 3: {out_wav} ({len(audio)/sr:.2f}s)")
