#!/usr/bin/env python3
"""
make_giai_phap_2.py - Giải pháp 2: DSP Studio Processor & Video Render
- Áp dụng chuỗi hiệu ứng âm thanh chuyên nghiệp (Broadcast Vocal Chain):
  Highpass 80Hz + Vocal Presence EQ (3.2kHz +3.5dB) + Mud Cut (280Hz -1.5dB)
  + Dynamic Compressor (Thresh -18dB, Ratio 3.5, Attack 15ms, Release 120ms, Makeup +4dB)
  + Brickwall Limiter (-0.5dB).
- Xuất file âm thanh: tests/giai_phap_2_dsp_compressed.wav
- Render video hoàn chỉnh: output/wuby_demo_giai_phap_2_dsp.mp4
"""
import os
import sys
import subprocess
from pathlib import Path
import soundfile as sf
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
TESTS_DIR = BASE_DIR / "tests"
OUTPUT_DIR = BASE_DIR / "wuby_package" / "output"
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"

in_wav = TESTS_DIR / "giai_phap_1_ref_tuning.wav"
if not in_wav.exists():
    in_wav = OUTPUT_DIR / "wuby_demo_result_voice.wav"

out_wav = TESTS_DIR / "giai_phap_2_dsp_compressed.wav"

print(f"--- [GIẢI PHÁP 2] DSP Studio Vocal Processing ---")
print(f"Input audio: {in_wav}")

# FFmpeg filter complex cho studio vocal processing:
# 1. highpass=f=80
# 2. equalizer=f=3200:t=q:w=1.2:g=3.5 (Presence boost)
# 3. equalizer=f=280:t=q:w=1.0:g=-1.5 (Mud cut)
# 4. acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=4.0dB (Dynamic leveling)
# 5. alimiter=limit=-0.5dB (True peak limiter)
dsp_filter = (
    "highpass=f=80,"
    "equalizer=f=3200:t=q:w=1.2:g=3.5,"
    "equalizer=f=280:t=q:w=1.0:g=-1.5,"
    "acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=4.0dB,"
    "alimiter=limit=-0.5dB"
)

cmd_audio = [
    "ffmpeg", "-y",
    "-i", str(in_wav),
    "-af", dsp_filter,
    "-ar", "24000",
    str(out_wav)
]

print("Đang xử lý DSP âm thanh...")
res = subprocess.run(cmd_audio, capture_output=True, text=True)
if res.returncode != 0:
    print(f"FFmpeg error: {res.stderr}")
    sys.exit(1)

print(f"✅ Đã tạo audio DSP: {out_wav}")

# Phân tích RMS sau khi nén DSP
data, sr = sf.read(str(out_wav))
step = int(0.25 * sr)
print("\n--- ĐO ĐẠC NĂNG LƯỢNG SAU KHI QUA BỘ DSP COMPRESSOR ---")
for i in range(0, len(data), step):
    seg = data[i:i+step]
    rms = np.sqrt(np.mean(seg**2))
    t = i / sr
    db = 20 * np.log10(max(rms, 1e-6))
    print(f"t={t:.2f}s - {t+len(seg)/sr:.2f}s : RMS = {rms:.4f} ({db:.1f} dBFS)")

# Render video thành phẩm ghép audio DSP vào video mẫu
out_video = OUTPUT_DIR / "wuby_demo_giai_phap_2_dsp.mp4"
base_video = OUTPUT_DIR / "wuby_demo_result.mp4"
if not base_video.exists():
    base_video = SAMPLE_DIR / "input_video.mp4"

print(f"\n--- RENDER VIDEO THÀNH PHẨM GIẢI PHÁP 2: {out_video.name} ---")
# Lấy video stream từ base_video (đã có in-place sub & OCR xóa chữ Trung) và thay track audio bằng DSP audio
# Đồng thời mix nhẹ nhạc nền 30% nếu có
cmd_video = [
    "ffmpeg", "-y",
    "-i", str(base_video),
    "-i", str(out_wav),
    "-c:v", "copy",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-shortest",
    str(out_video)
]

res_v = subprocess.run(cmd_video, capture_output=True, text=True)
if res_v.returncode == 0:
    print(f"✅ Đã render video hoàn chỉnh: {out_video} ({out_video.stat().st_size / 1024 / 1024:.2f} MB)")
else:
    print(f"FFmpeg video error: {res_v.stderr}")
