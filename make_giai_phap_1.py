#!/usr/bin/env python3
"""
make_giai_phap_1.py - Giải pháp 1: Tinh chỉnh Reference Audio (Reference Tuning)
- Cắt bỏ đoạn đuôi tụt năng lượng của reference gốc.
- Chuẩn hóa RMS về -18 dBFS đều đặn.
- Clone giọng 2 câu thoại tiếng Việt qua KhanhTTS-OmniVoice với Reference đã tinh chỉnh.
"""
import os
import sys
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"
TESTS_DIR = BASE_DIR / "tests"
TESTS_DIR.mkdir(parents=True, exist_ok=True)

ref_orig = SAMPLE_DIR / "character_original.ref.wav"
ref_tuned = SAMPLE_DIR / "character_tuned.ref.wav"

print("--- [GIẢI PHÁP 1] Tinh chỉnh Reference Audio ---")
# 1. Đọc audio gốc
data, sr = sf.read(str(ref_orig), dtype="float32")
if data.ndim > 1:
    data = data.mean(axis=1)

# Đoạn ổn định, năng lượng cao nhất là từ 0.0s đến 3.2s (loại bỏ đuôi xẹp hơi 3.2s - 5.0s)
tuned_data = data[int(0.05 * sr) : int(3.25 * sr)].copy()

# Chuẩn hóa RMS về -18 dBFS (target_rms ~ 0.126)
curr_rms = np.sqrt(np.mean(tuned_data**2) + 1e-12)
target_rms = 0.16  # ~ -16 dBFS khỏe khoắn
tuned_data = tuned_data * (target_rms / max(curr_rms, 1e-6))
# Clip bảo vệ peak
peak = np.max(np.abs(tuned_data))
if peak > 0.95:
    tuned_data = tuned_data * (0.95 / peak)

sf.write(str(ref_tuned), tuned_data, sr, subtype="PCM_16")
print(f"Đã tạo reference tuned: {ref_tuned} (Duration: {len(tuned_data)/sr:.2f}s, RMS: {np.sqrt(np.mean(tuned_data**2)):.4f})")

# 2. Sinh audio với OmniVoice
from omnivoice import OmniVoice

device = "cuda:0" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if torch.cuda.is_available() else torch.float32

print(f"Loading OmniVoice on {device}...")
model = OmniVoice.from_pretrained(
    "kjanh/KhanhTTS-OmniVoice",
    device_map=device,
    dtype=dtype,
    load_asr=False
)

print("Tạo Voice Clone Prompt từ Reference đã tinh chỉnh...")
prompt = model.create_voice_clone_prompt(
    ref_audio=str(ref_tuned),
    ref_text="你不理你的人看你",
    preprocess_prompt=True
)

cues = [
    ("Gửi cho người không để ý đến bạn xem", 1.76),
    ("Em bận thì cứ bận đi", 1.92)
]

generated_audios = []
for idx, (text, dur) in enumerate(cues, 1):
    print(f"Đang sinh câu {idx}: '{text}'...")
    res = model.generate(
        text=text,
        language="Vietnamese",
        voice_clone_prompt=prompt,
        num_step=16
    )
    wav = res[0] if isinstance(res, (list, tuple)) else res
    wav = np.asarray(wav, dtype=np.float32).reshape(-1)
    
    # Trim silence at start and end
    thresh = 0.015 * np.max(np.abs(wav))
    non_sil = np.where(np.abs(wav) > thresh)[0]
    if len(non_sil) > 0:
        start_idx = max(0, non_sil[0] - int(0.05 * sr))
        end_idx = min(len(wav), non_sil[-1] + int(0.08 * sr))
        wav = wav[start_idx:end_idx]
    
    # Fit slot gently if needed without hard cutting
    target_len = int(dur * sr)
    if len(wav) > target_len:
        # Nhẹ nhàng nén tempo thay vì cắt đuôi!
        import librosa
        rate = len(wav) / target_len
        if 0.95 <= rate <= 1.35:
            wav = librosa.effects.time_stretch(wav, rate=rate)
    
    generated_audios.append(wav)

# Ghép master với timing chuẩn như SRT
total_sec = 3.68
master = np.zeros(int(total_sec * sr), dtype=np.float32)

# Cue 1: start at 0.0s
c1 = generated_audios[0]
end1 = min(len(master), len(c1))
master[:end1] += c1[:end1]

# Cue 2: start at 1.76s
c2 = generated_audios[1]
start2 = int(1.76 * sr)
end2 = min(len(master), start2 + len(c2))
master[start2:end2] += c2[:end2 - start2]

# Normalize master
peak = np.max(np.abs(master))
if peak > 0.95:
    master = master * (0.95 / peak)

out_wav = TESTS_DIR / "giai_phap_1_ref_tuning.wav"
sf.write(str(out_wav), master, sr, subtype="PCM_16")
print(f"✅ Hoàn thành Giải pháp 1: {out_wav} (Duration: {len(master)/sr:.2f}s)")
