#!/usr/bin/env python3
"""
run_reversed_multivoice_pipeline.py - Đảo ngược Voice theo yêu cầu:
- Giọng trước (Cue 1): BIỂU LỘ CẢM XÚC (Anime Wuby Clone - F0 ~335Hz)
- Giọng sau (Cue 2): GIỌNG DẪN (Narrator / MC - Nam & Nữ)
- Render video hoàn chỉnh & Gửi trực tiếp lên nhóm Telegram
"""
import os
import sys
import time
import subprocess
import asyncio
from pathlib import Path
import soundfile as sf
import numpy as np
import torch
import edge_tts
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
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"
TESTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70, flush=True)
print("🚀 BẮT ĐẦU QUY TRÌNH ĐẢO NGƯỢC VOICE (GIỌNG TRƯỚC CẢM XÚC - GIỌNG SAU DẪN)", flush=True)
print("=" * 70, flush=True)

# -------------------------------------------------------------
# BƯỚC 1: SINH GIỌNG TRƯỚC (BIỂU LỘ CẢM XÚC - HOẠT HÌNH WUBY)
# -------------------------------------------------------------
print("\n[1/5] Đang sinh Giọng Trước (Biểu lộ cảm xúc - Hoạt hình Wuby)...", flush=True)
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

text_cue1 = "Hãy gửi cho người không để ý đến bạn xem!"
print(f"  -> Tổng hợp câu 1: '{text_cue1}'...", flush=True)
t0 = time.time()
res1 = model.generate(
    text=text_cue1,
    language="Vietnamese",
    voice_clone_prompt=prompt_emotion,
    num_step=20
)
wav1 = np.asarray(res1[0] if isinstance(res1, (list, tuple)) else res1, dtype=np.float32).reshape(-1)
sr = 24000

# Cắt bỏ khoảng lặng
thresh1 = 0.02 * np.max(np.abs(wav1))
non_sil1 = np.where(np.abs(wav1) > thresh1)[0]
if len(non_sil1) > 0:
    wav1 = wav1[non_sil1[0] : non_sil1[-1] + int(0.05 * sr)]

# Lưu file tạm để dùng FFmpeg atempo co giãn chuẩn xác vừa khít 1.76s
tmp_c1_in = TESTS_DIR / "tmp_c1_raw.wav"
tmp_c1_fit = TESTS_DIR / "tmp_c1_fit.wav"
sf.write(str(tmp_c1_in), wav1, sr, subtype="PCM_16")

dur1 = len(wav1) / sr
target_dur1 = 1.76
tempo1 = max(0.85, min(1.35, dur1 / target_dur1))
subprocess.run([
    "ffmpeg", "-y", "-i", str(tmp_c1_in),
    "-filter:a", f"atempo={tempo1:.3f}",
    str(tmp_c1_fit)
], check=True, capture_output=True)

wav1_fit, _ = sf.read(str(tmp_c1_fit), dtype="float32")
if len(wav1_fit) > int(target_dur1 * sr):
    wav1_fit = wav1_fit[: int(target_dur1 * sr)]
print(f"  -> ✅ Giọng trước (Biểu cảm): {len(wav1_fit)/sr:.2f}s (chuẩn timeline 1.76s)", flush=True)

# -------------------------------------------------------------
# BƯỚC 2: SINH GIỌNG SAU (GIỌNG DẪN CHUYỆN / NARRATOR)
# -------------------------------------------------------------
print("\n[2/5] Đang sinh Giọng Sau (Giọng Dẫn Chuyện)...", flush=True)
text_cue2 = "Em bận thì cứ bận đi."
target_dur2 = 1.92

async def make_narrator(voice, text, out_wav_fit):
    mp3_tmp = TESTS_DIR / f"tmp_{voice}.mp3"
    wav_tmp = TESTS_DIR / f"tmp_{voice}.wav"
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    await communicate.save(str(mp3_tmp))
    subprocess.run(["ffmpeg", "-y", "-i", str(mp3_tmp), "-ar", "24000", "-ac", "1", str(wav_tmp)], check=True, capture_output=True)
    w, _ = sf.read(str(wav_tmp), dtype="float32")
    non_sil = np.where(np.abs(w) > 0.02 * np.max(np.abs(w)))[0]
    if len(non_sil) > 0:
        w = w[non_sil[0] : non_sil[-1] + int(0.05 * sr)]
    sf.write(str(wav_tmp), w, sr, subtype="PCM_16")
    tempo = max(0.85, min(1.30, (len(w) / sr) / target_dur2))
    subprocess.run(["ffmpeg", "-y", "-i", str(wav_tmp), "-filter:a", f"atempo={tempo:.3f}", str(out_wav_fit)], check=True, capture_output=True)

# 2A. Nam Dẫn (vi-VN-NamMinhNeural - MC Đĩnh đạc)
out_fit_nam = TESTS_DIR / "tmp_c2_nam_fit.wav"
asyncio.run(make_narrator("vi-VN-NamMinhNeural", text_cue2, out_fit_nam))
wav2_nam, _ = sf.read(str(out_fit_nam), dtype="float32")
if len(wav2_nam) > int(target_dur2 * sr):
    wav2_nam = wav2_nam[: int(target_dur2 * sr)]
print(f"  -> ✅ Giọng sau (Nam Dẫn MC): {len(wav2_nam)/sr:.2f}s (chuẩn timeline 1.92s)", flush=True)

# 2B. Nữ Dẫn (vi-VN-HoaiMyNeural - MC Truyền cảm)
out_fit_nu = TESTS_DIR / "tmp_c2_nu_fit.wav"
asyncio.run(make_narrator("vi-VN-HoaiMyNeural", text_cue2, out_fit_nu))
wav2_nu, _ = sf.read(str(out_fit_nu), dtype="float32")
if len(wav2_nu) > int(target_dur2 * sr):
    wav2_nu = wav2_nu[: int(target_dur2 * sr)]
print(f"  -> ✅ Giọng sau (Nữ Dẫn MC): {len(wav2_nu)/sr:.2f}s (chuẩn timeline 1.92s)", flush=True)

# -------------------------------------------------------------
# BƯỚC 3: GHÉP TIMELINE MASTER & CHUỖI DSP STUDIO
# -------------------------------------------------------------
print("\n[3/5] Ghép Timeline Master & Xử lý DSP Vocal Chain...", flush=True)
total_sec = 3.75
total_len = int(total_sec * sr)

dsp_filter = (
    "highpass=f=80,"
    "equalizer=f=3200:t=q:w=1.2:g=3.0,"
    "acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=3.5dB,"
    "alimiter=limit=-0.5dB"
)

def create_master_dsp(c1_data, c2_data, out_name):
    master = np.zeros(total_len, dtype=np.float32)
    # Cue 1 at 0.0s
    e1 = min(total_len, len(c1_data))
    master[:e1] += c1_data[:e1]
    # Cue 2 at 1.76s
    s2 = int(1.76 * sr)
    e2 = min(total_len, s2 + len(c2_data))
    master[s2:e2] += c2_data[: e2 - s2]
    # Peak norm
    p = np.max(np.abs(master))
    if p > 0.95:
        master *= 0.95 / p
    raw_path = TESTS_DIR / f"raw_{out_name}.wav"
    dsp_path = TESTS_DIR / f"{out_name}.wav"
    sf.write(str(raw_path), master, sr, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-y", "-i", str(raw_path), "-af", dsp_filter, "-ar", "24000", str(dsp_path)], check=True, capture_output=True)
    return dsp_path

audio_nam_dan = create_master_dsp(wav1_fit, wav2_nam, "reversed_voice_nam_dan")
print(f"  -> ✅ Audio Bản 1 (Giọng trước Cảm xúc + Giọng sau Nam Dẫn): {audio_nam_dan}", flush=True)

audio_nu_dan = create_master_dsp(wav1_fit, wav2_nu, "reversed_voice_nu_dan")
print(f"  -> ✅ Audio Bản 2 (Giọng trước Cảm xúc + Giọng sau Nữ Dẫn): {audio_nu_dan}", flush=True)

# -------------------------------------------------------------
# BƯỚC 4: RENDER VIDEO THÀNH PHẨM (NVENC GPU)
# -------------------------------------------------------------
print("\n[4/5] Render Video Thành Phẩm Hoàn Chỉnh...", flush=True)
base_video = OUTPUT_DIR / "wuby_demo_result.mp4"
if not base_video.exists():
    base_video = SAMPLE_DIR / "input_video.mp4"

video_nam_dan = OUTPUT_DIR / "wuby_demo_reversed_voice_nam_dan.mp4"
subprocess.run([
    "ffmpeg", "-y", "-i", str(base_video), "-i", str(audio_nam_dan),
    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(video_nam_dan)
], check=True, capture_output=True)
print(f"  -> 🎬 Video Bản 1 (Nam Dẫn): {video_nam_dan} ({video_nam_dan.stat().st_size / 1024 / 1024:.2f} MB)", flush=True)

video_nu_dan = OUTPUT_DIR / "wuby_demo_reversed_voice_nu_dan.mp4"
subprocess.run([
    "ffmpeg", "-y", "-i", str(base_video), "-i", str(audio_nu_dan),
    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(video_nu_dan)
], check=True, capture_output=True)
print(f"  -> 🎬 Video Bản 2 (Nữ Dẫn): {video_nu_dan} ({video_nu_dan.stat().st_size / 1024 / 1024:.2f} MB)", flush=True)

# -------------------------------------------------------------
# BƯỚC 5: GỬI TOÀN BỘ LÊN NHÓM TELEGRAM
# -------------------------------------------------------------
print("\n[5/5] Đang gửi trọn bộ Audio & Video lên Telegram...", flush=True)

def send_tele_audio(fpath, title, cap):
    with open(fpath, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendAudio",
            data={"chat_id": chat_id, "caption": cap, "parse_mode": "HTML", "title": title, "performer": "Wuby Multi-Voice"},
            files={"audio": f},
            timeout=60
        ).json()
        print(f"  -> Audio [{title}]: {r.get('ok')} (Msg ID: {r.get('result', {}).get('message_id')})", flush=True)

def send_tele_video(fpath, cap):
    with open(fpath, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendVideo",
            data={"chat_id": chat_id, "caption": cap, "parse_mode": "HTML", "supports_streaming": True},
            files={"video": f},
            timeout=180
        ).json()
        print(f"  -> Video [{fpath.name}]: {r.get('ok')} (Msg ID: {r.get('result', {}).get('message_id')})", flush=True)

intro_msg = (
    "🔄 <b>BẢN NÂNG CẤP: ĐẢO NGƯỢC VOICE THEO YÊU CẦU</b>\n\n"
    "• <b>Giọng trước (0.0s – 1.76s):</b> <i>'Gửi cho người không để ý đến bạn xem'</i> → <b>BIỂU LỘ CẢM XÚC</b> (Clone nhân vật hoạt hình gốc, ngữ điệu dỗi hờn, sinh động).\n"
    "• <b>Giọng sau (1.76s – 3.68s):</b> <i>'Em bận thì cứ bận đi'</i> → <b>GIỌNG DẪN CHUYỆN</b> (Đĩnh đạc, rõ ràng, không bao giờ hụt hơi).\n\n"
    "Dưới đây là 2 phiên bản phối giọng kèm Video thành phẩm hoàn chỉnh:"
)
requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": intro_msg, "parse_mode": "HTML"}, timeout=30)
time.sleep(1)

# Gửi Audio Bản 1 (Nam Dẫn)
cap_a1 = (
    "🎙️ <b>[BẢN 1 - NAM DẪN] Giọng trước Cảm xúc + Giọng sau Nam MC Dẫn</b>\n\n"
    "• <b>Câu 1:</b> Giọng hoạt hình Wuby cảm xúc cao trào.\n"
    "• <b>Câu 2:</b> Giọng Nam MC đĩnh đạc, ấm áp, dứt khoát.\n"
    "• Đã cân bằng dải động DSP studio."
)
send_tele_audio(audio_nam_dan, "Bản 1 - Giọng Trước Cảm Xúc / Sau Nam Dẫn", cap_a1)
time.sleep(1)

# Gửi Video Bản 1 (Nam Dẫn)
cap_v1 = (
    "🎬 <b>VIDEO THÀNH PHẨM (BẢN 1: NAM DẪN CHUYỆN)</b>\n\n"
    "Video ghép in-place subtitle + OCR xóa chữ Trung + Giọng trước Hoạt hình Cảm xúc & Giọng sau Nam Dẫn. Mời bạn bật loa để trải nghiệm!"
)
send_tele_video(video_nam_dan, cap_v1)
time.sleep(1)

# Gửi Audio Bản 2 (Nữ Dẫn)
cap_a2 = (
    "🎙️ <b>[BẢN 2 - NỮ DẪN] Giọng trước Cảm xúc + Giọng sau Nữ MC Dẫn</b>\n\n"
    "• <b>Câu 1:</b> Giọng hoạt hình Wuby cảm xúc.\n"
    "• <b>Câu 2:</b> Giọng Nữ MC truyền cảm, thanh thoát.\n"
    "• Đã cân bằng dải động DSP studio."
)
send_tele_audio(audio_nu_dan, "Bản 2 - Giọng Trước Cảm Xúc / Sau Nữ Dẫn", cap_a2)
time.sleep(1)

# Gửi Video Bản 2 (Nữ Dẫn)
cap_v2 = (
    "🎬 <b>VIDEO THÀNH PHẨM (BẢN 2: NỮ DẪN CHUYỆN)</b>\n\n"
    "Video thành phẩm hoàn chỉnh với Giọng trước Hoạt hình Cảm xúc & Giọng sau Nữ Dẫn chuyện truyền cảm!"
)
send_tele_video(video_nu_dan, cap_v2)

print("\n" + "=" * 70, flush=True)
print("🎉 ĐÃ HOÀN TẤT VÀ GỬI ĐẦY ĐỦ CẢ 2 BẢN AUDIO & VIDEO LÊN TELEGRAM!", flush=True)
print("=" * 70, flush=True)
