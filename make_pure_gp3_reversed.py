#!/usr/bin/env python3
"""
make_pure_gp3_reversed.py - Tạo bản Giải Pháp 3 Đảo Ngược Thuần Giọng Wuby:
- Sử dụng 100% chất giọng của Giải Pháp 3 (Cross-Lingual Engine)
- Câu 1: Biểu lộ cảm xúc nhân vật (Wuby Emotional Tone)
- Câu 2: Đọc theo lối Dẫn chuyện (Wuby Narrator / Concluding Tone)
- Render video thành phẩm: output/wuby_demo_giai_phap_3_reversed_pure.mp4
- Gửi Audio & Video lên Telegram
"""
import os
import sys
import time
import subprocess
from pathlib import Path
import soundfile as sf
import numpy as np
from dotenv import load_dotenv
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / "backend" / ".env")
token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
chat_id = "-1004439918026"

TESTS_DIR = BASE_DIR / "tests"
OUTPUT_DIR = BASE_DIR / "wuby_package" / "output"

print("--- TẠO BẢN THUẦN VOICE GIẢI PHÁP 3: CÂU TRƯỚC CẢM XÚC - CÂU SAU DẪN ---")

# 1. Lấy Cue 1 (Biểu cảm) từ tmp_c1_fit.wav
c1_path = TESTS_DIR / "tmp_c1_fit.wav"
if not c1_path.exists():
    c1_path = TESTS_DIR / "gp3_sentence1.wav"

w1, sr = sf.read(str(c1_path), dtype="float32")

# 2. Lấy Cue 2 (Giọng Wuby đọc kiểu dẫn / kết luận câu) từ gp3_sentence2.wav
c2_path = TESTS_DIR / "gp3_sentence2.wav"
w2, sr2 = sf.read(str(c2_path), dtype="float32")

# Chuẩn hóa trường độ Cue 2 vừa khít slot 1.92s
target_dur2 = 1.92
w2_tmp = TESTS_DIR / "tmp_gp3_c2.wav"
w2_fit = TESTS_DIR / "tmp_gp3_c2_fit.wav"
sf.write(str(w2_tmp), w2, sr, subtype="PCM_16")

tempo2 = max(0.85, min(1.30, (len(w2) / sr) / target_dur2))
subprocess.run([
    "ffmpeg", "-y", "-i", str(w2_tmp),
    "-filter:a", f"atempo={tempo2:.3f}",
    str(w2_fit)
], check=True, capture_output=True)

w2_fitted, _ = sf.read(str(w2_fit), dtype="float32")
if len(w2_fitted) > int(target_dur2 * sr):
    w2_fitted = w2_fitted[: int(target_dur2 * sr)]

# 3. Ghép Master Timeline & DSP Audio Chain
total_sec = 3.75
total_len = int(total_sec * sr)
master = np.zeros(total_len, dtype=np.float32)

# Cue 1 at 0.00s
e1 = min(total_len, len(w1))
master[:e1] += w1[:e1]

# Cue 2 at 1.76s
s2 = int(1.76 * sr)
e2 = min(total_len, s2 + len(w2_fitted))
master[s2:e2] += w2_fitted[: e2 - s2]

# Peak normalization
p = np.max(np.abs(master))
if p > 0.95:
    master *= 0.95 / p

raw_out = TESTS_DIR / "raw_gp3_reversed_pure.wav"
dsp_out = TESTS_DIR / "giai_phap_3_reversed_pure_voice.wav"
sf.write(str(raw_out), master, sr, subtype="PCM_16")

# DSP filter: nâng đều dải động, cắt rumble, đẩy presence
dsp_filter = (
    "highpass=f=80,"
    "equalizer=f=3200:t=q:w=1.2:g=3.2,"
    "acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=3.5dB,"
    "alimiter=limit=-0.5dB"
)
subprocess.run([
    "ffmpeg", "-y", "-i", str(raw_out),
    "-af", dsp_filter, "-ar", "24000", str(dsp_out)
], check=True, capture_output=True)

print(f"✅ Đã tạo audio Giải Pháp 3 Đảo Ngược: {dsp_out}")

# 4. Render Video Thành Phẩm
base_video = OUTPUT_DIR / "wuby_demo_result.mp4"
out_video = OUTPUT_DIR / "wuby_demo_giai_phap_3_reversed.mp4"

subprocess.run([
    "ffmpeg", "-y",
    "-i", str(base_video),
    "-i", str(dsp_out),
    "-c:v", "copy",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-shortest",
    str(out_video)
], check=True, capture_output=True)

print(f"🎬 Đã render video thành phẩm Giải Pháp 3: {out_video} ({out_video.stat().st_size / 1024 / 1024:.2f} MB)")

# 5. Gửi lên Telegram
caption_audio = (
    "🌐 <b>[GIẢI PHÁP 3 - ĐẢO NGƯỢC VOICE THUẦN WUBY]</b>\n\n"
    "• <b>Giọng trước (Câu 1):</b> <i>'Gửi cho người không để ý đến bạn xem'</i> → Biểu lộ cảm xúc dỗi hờn, sinh động.\n"
    "• <b>Giọng sau (Câu 2):</b> <i>'Em bận thì cứ bận đi'</i> → Đổi sắc thái thành giọng dẫn, đĩnh đạc, kết câu dứt khoát.\n"
    "• <b>Chất âm:</b> Đúng 100% chất giọng Wuby của Giải Pháp 3 (Cross-Lingual Engine)."
)

caption_video = (
    "🎬 <b>VIDEO THÀNH PHẨM GIẢI PHÁP 3 ĐẢO NGƯỢC (THUẦN GIỌNG WUBY)</b>\n\n"
    "Video ghép in-place sub + OCR xóa chữ Trung + Chuỗi DSP Vocal cho chính giọng Giải Pháp 3 mà bạn đã chọn. "
    "Mời bạn bật loa để kiểm tra ngay!"
)

print("Đang gửi Audio lên Telegram...")
with open(dsp_out, "rb") as f:
    res_a = requests.post(
        f"https://api.telegram.org/bot{token}/sendAudio",
        data={
            "chat_id": chat_id,
            "caption": caption_audio,
            "parse_mode": "HTML",
            "title": "Giải Pháp 3 - Đảo Ngược Voice Wuby",
            "performer": "Wuby AI Voice Clone"
        },
        files={"audio": f},
        timeout=60
    ).json()
print("  -> Kết quả Audio:", res_a.get("ok"), "Msg ID:", res_a.get("result", {}).get("message_id"))

print("Đang gửi Video lên Telegram...")
with open(out_video, "rb") as f:
    res_v = requests.post(
        f"https://api.telegram.org/bot{token}/sendVideo",
        data={
            "chat_id": chat_id,
            "caption": caption_video,
            "parse_mode": "HTML",
            "supports_streaming": True
        },
        files={"video": f},
        timeout=180
    ).json()
print("  -> Kết quả Video:", res_v.get("ok"), "Msg ID:", res_v.get("result", {}).get("message_id"))

print("🎉 ĐÃ HOÀN TẤT VÀ GỬI VIDEO GIẢI PHÁP 3 LÊN TELEGRAM!")
