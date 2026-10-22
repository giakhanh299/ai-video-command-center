#!/usr/bin/env python3
"""
make_reversed_multivoice.py - Đảo ngược Voice theo yêu cầu:
- Giọng trước (Cue 1: "Gửi cho người không để ý đến bạn xem"): BIỂU LỘ CẢM XÚC (Clone giọng hoạt hình Wuby)
- Giọng sau (Cue 2: "Em bận thì cứ bận đi"): DẪN CHUYỆN (Giọng Nam MC dẫn & Nữ MC dẫn)
- Mix timeline chính xác với SRT, áp dụng DSP Vocal Chain, render video thành phẩm và gửi Telegram.
"""
import os
import sys
import time
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
import librosa
import edge_tts
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
TESTS_DIR = BASE_DIR / "tests"
OUTPUT_DIR = BASE_DIR / "wuby_package" / "output"
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"
TESTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Sinh Giọng Trước: Biểu lộ cảm xúc (Nhân vật hoạt hình Wuby clone)
print("--- [BƯỚC 1] Sinh Giọng Trước: Biểu lộ cảm xúc (Anime Wuby Clone) ---")
from omnivoice import OmniVoice

device = "cuda:0" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model = OmniVoice.from_pretrained(
    "kjanh/KhanhTTS-OmniVoice",
    device_map=device,
    dtype=dtype,
    load_asr=False
)

prompt_emotion = model.create_voice_clone_prompt(
    ref_audio=str(SAMPLE_DIR / "character_tuned.ref.wav"),
    ref_text="你不理你的人看你",
    preprocess_prompt=True
)

# Để model phát âm chuẩn xác từng chữ tiếng Việt và dạt dào cảm xúc:
# Ta đưa vào câu biểu cảm: "Hãy gửi cho người không để ý đến bạn xem!" rồi tỉa nhẹ đầu nếu cần
text_cue1 = "Hãy gửi cho người không để ý đến bạn xem!"
print(f"Đang sinh giọng trước (biểu cảm): '{text_cue1}'...")
res1 = model.generate(
    text=text_cue1,
    language="Vietnamese",
    voice_clone_prompt=prompt_emotion,
    num_step=20
)
wav1 = np.asarray(res1[0] if isinstance(res1, (list, tuple)) else res1, dtype=np.float32).reshape(-1)
sr = 24000

# Cắt bỏ phần lặng đầu/đuôi
thresh1 = 0.02 * np.max(np.abs(wav1))
non_sil1 = np.where(np.abs(wav1) > thresh1)[0]
if len(non_sil1) > 0:
    wav1 = wav1[non_sil1[0] : non_sil1[-1] + int(0.05 * sr)]

# Co giãn tempo để vừa khít slot 1.76s của Cue 1
dur1_target = 1.76
rate1 = (len(wav1) / sr) / dur1_target
if rate1 > 1.05:
    wav1 = librosa.effects.time_stretch(wav1, rate=min(rate1, 1.35))
if len(wav1) > int(dur1_target * sr):
    wav1 = wav1[: int(dur1_target * sr)]

print(f"✅ Giọng trước hoàn thành: {len(wav1)/sr:.2f}s")

# 2. Sinh Giọng Sau: Giọng DẪN (Narrator Voice)
print("\n--- [BƯỚC 2] Sinh Giọng Sau: Giọng Dẫn (Narrator Voice) ---")
text_cue2 = "Em bận thì cứ bận đi."

# Bản A: Nam Dẫn (Nam MC thời sự/truyền hình đĩnh đạc vi-VN-NamMinhNeural)
async def gen_edge_voice(text, voice_name, out_file):
    communicate = edge_tts.Communicate(text, voice_name, rate="+5%")
    await communicate.save(out_file)

asyncio.run(gen_edge_voice(text_cue2, "vi-VN-NamMinhNeural", str(TESTS_DIR / "cue2_nam_dan_edge.mp3")))
# Convert to 24kHz wav
subprocess.run([
    "ffmpeg", "-y", "-i", str(TESTS_DIR / "cue2_nam_dan_edge.mp3"),
    "-ar", "24000", "-ac", "1", str(TESTS_DIR / "cue2_nam_dan.wav")
], capture_output=True)

wav2_nam, _ = sf.read(str(TESTS_DIR / "cue2_nam_dan.wav"), dtype="float32")
thresh2 = 0.02 * np.max(np.abs(wav2_nam))
non_sil2 = np.where(np.abs(wav2_nam) > thresh2)[0]
if len(non_sil2) > 0:
    wav2_nam = wav2_nam[non_sil2[0] : non_sil2[-1] + int(0.05 * sr)]

# Co giãn tempo vừa khít slot 1.92s
dur2_target = 1.92
rate2 = (len(wav2_nam) / sr) / dur2_target
if rate2 > 1.05:
    wav2_nam = librosa.effects.time_stretch(wav2_nam, rate=min(rate2, 1.30))
if len(wav2_nam) > int(dur2_target * sr):
    wav2_nam = wav2_nam[: int(dur2_target * sr)]

print(f"✅ Giọng sau (Nam dẫn) hoàn thành: {len(wav2_nam)/sr:.2f}s")

# Bản B: Nữ Dẫn (Nữ MC truyền cảm vi-VN-HoaiMyNeural)
asyncio.run(gen_edge_voice(text_cue2, "vi-VN-HoaiMyNeural", str(TESTS_DIR / "cue2_nu_dan_edge.mp3")))
subprocess.run([
    "ffmpeg", "-y", "-i", str(TESTS_DIR / "cue2_nu_dan_edge.mp3"),
    "-ar", "24000", "-ac", "1", str(TESTS_DIR / "cue2_nu_dan.wav")
], capture_output=True)

wav2_nu, _ = sf.read(str(TESTS_DIR / "cue2_nu_dan.wav"), dtype="float32")
non_sil_nu = np.where(np.abs(wav2_nu) > 0.02 * np.max(np.abs(wav2_nu)))[0]
if len(non_sil_nu) > 0:
    wav2_nu = wav2_nu[non_sil_nu[0] : non_sil_nu[-1] + int(0.05 * sr)]
rate2_nu = (len(wav2_nu) / sr) / dur2_target
if rate2_nu > 1.05:
    wav2_nu = librosa.effects.time_stretch(wav2_nu, rate=min(rate2_nu, 1.30))
if len(wav2_nu) > int(dur2_target * sr):
    wav2_nu = wav2_nu[: int(dur2_target * sr)]

print(f"✅ Giọng sau (Nữ dẫn) hoàn thành: {len(wav2_nu)/sr:.2f}s")

# 3. Ghép Master Timeline & DSP Audio Chain
print("\n--- [BƯỚC 3] Ghép Timeline & DSP Studio Audio Chain ---")
total_sec = 3.75
total_len = int(total_sec * sr)

def mix_and_dsp(cue1_audio, cue2_audio, raw_out_path, dsp_out_path):
    master = np.zeros(total_len, dtype=np.float32)
    # Cue 1 at 0.0s
    e1 = min(total_len, len(cue1_audio))
    master[:e1] += cue1_audio[:e1]
    # Cue 2 at 1.76s
    s2 = int(1.76 * sr)
    e2 = min(total_len, s2 + len(cue2_audio))
    master[s2:e2] += cue2_audio[: e2 - s2]
    
    # Normalize peak
    p = np.max(np.abs(master))
    if p > 0.95:
        master *= 0.95 / p
    sf.write(str(raw_out_path), master, sr, subtype="PCM_16")
    
    # Run DSP chain
    dsp_filter = (
        "highpass=f=80,"
        "equalizer=f=3200:t=q:w=1.2:g=3.0,"
        "acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=3.5dB,"
        "alimiter=limit=-0.5dB"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_out_path),
        "-af", dsp_filter, "-ar", "24000", str(dsp_out_path)
    ], check=True, capture_output=True)

# Tạo Bản 1: Giọng trước biểu cảm + Giọng sau Nam Dẫn
raw_nam = TESTS_DIR / "raw_reversed_nam_dan.wav"
dsp_nam = TESTS_DIR / "reversed_giong_truoc_camxuc_giong_sau_nam_dan.wav"
mix_and_dsp(wav1, wav2_nam, raw_nam, dsp_nam)
print(f"✅ Đã tạo audio Bản 1 (Nam dẫn): {dsp_nam}")

# Tạo Bản 2: Giọng trước biểu cảm + Giọng sau Nữ Dẫn
raw_nu = TESTS_DIR / "raw_reversed_nu_dan.wav"
dsp_nu = TESTS_DIR / "reversed_giong_truoc_camxuc_giong_sau_nu_dan.wav"
mix_and_dsp(wav1, wav2_nu, raw_nu, dsp_nu)
print(f"✅ Đã tạo audio Bản 2 (Nữ dẫn): {dsp_nu}")

# 4. Render Video Thành Phẩm (Bản 1 Nam Dẫn & Bản 2 Nữ Dẫn)
print("\n--- [BƯỚC 4] Render Video Thành Phẩm Hoàn Chỉnh ---")
base_video = OUTPUT_DIR / "wuby_demo_result.mp4"
if not base_video.exists():
    base_video = SAMPLE_DIR / "input_video.mp4"

out_video_nam = OUTPUT_DIR / "wuby_demo_reversed_voice_nam_dan.mp4"
subprocess.run([
    "ffmpeg", "-y",
    "-i", str(base_video),
    "-i", str(dsp_nam),
    "-c:v", "copy",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-shortest",
    str(out_video_nam)
], check=True, capture_output=True)
print(f"🎬 Đã render video thành phẩm (Nam dẫn): {out_video_nam} ({out_video_nam.stat().st_size / 1024 / 1024:.2f} MB)")

out_video_nu = OUTPUT_DIR / "wuby_demo_reversed_voice_nu_dan.mp4"
subprocess.run([
    "ffmpeg", "-y",
    "-i", str(base_video),
    "-i", str(dsp_nu),
    "-c:v", "copy",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-shortest",
    str(out_video_nu)
], check=True, capture_output=True)
print(f"🎬 Đã render video thành phẩm (Nữ dẫn): {out_video_nu} ({out_video_nu.stat().st_size / 1024 / 1024:.2f} MB)")

print("\n🎉 HOÀN TẤT TẠO CẢ 2 PHIÊN BẢN ĐẢO NGƯỢC VOICE THEO YÊU CẦU!")
