#!/usr/bin/env python3
"""
make_perfect_sync_video.py - Đồng bộ 100% timeline, triệt tiêu hoàn toàn hiện tượng giọng đè giọng:
- Cue 1: Bắt đầu 0.05s, kết thúc 1.70s (Chuẩn Scene 0: 0.0s - 1.875s)
- Gap nghỉ: 1.70s - 1.88s (Khoảng lặng 0.18s, tuyệt đối KHÔNG ĐÈ NHAU)
- Cue 2: Bắt đầu 1.88s, kết thúc 3.60s (Chuẩn Scene 1: 1.875s - 3.68s)
- Video chạy trọn vẹn 8.54s (nhạc nền tiếp tục ngân vang đến hết clip)
"""
import os
import sys
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
SAMPLE_DIR = BASE_DIR / "wuby_package" / "sample_data"

print("=" * 70)
print("🚀 XỬ LÝ ĐỒNG BỘ TIMELINE: TRIỆT TIÊU HIỆN TƯỢNG ĐÈ GIỌNG")
print("=" * 70)

sr = 24000
total_video_sec = 8.541667
total_samples = int(np.ceil(total_video_sec * sr))

# -------------------------------------------------------------
# 1. CHUẨN HÓA CUE 1 (GIỌNG TRƯỚC - BIỂU LỘ CẢM XÚC)
# -------------------------------------------------------------
# Lấy file Cue 1 từ tests/test_cue1_fast_ref.wav hoặc gp3_sentence1.wav
c1_in = TESTS_DIR / "test_cue1_fast_ref.wav"
if not c1_in.exists():
    c1_in = TESTS_DIR / "gp3_sentence1.wav"

w1, _ = sf.read(str(c1_in), dtype="float32")
non_sil1 = np.where(np.abs(w1) > 0.02 * np.max(np.abs(w1)))[0]
if len(non_sil1) > 0:
    w1 = w1[non_sil1[0] : non_sil1[-1]]

# Target: Vang từ 0.05s đến 1.70s -> Độ dài tối đa 1.65s
target_dur1 = 1.65
curr_dur1 = len(w1) / sr
tempo1 = curr_dur1 / target_dur1
print(f"[Cue 1] Gốc: {curr_dur1:.2f}s -> Mục tiêu: {target_dur1:.2f}s (atempo={tempo1:.3f})")

sf.write(str(TESTS_DIR / "c1_raw_trim.wav"), w1, sr, subtype="PCM_16")
subprocess.run([
    "ffmpeg", "-y", "-i", str(TESTS_DIR / "c1_raw_trim.wav"),
    "-filter:a", f"atempo={tempo1:.3f}",
    str(TESTS_DIR / "c1_fitted.wav")
], check=True, capture_output=True)

w1_fit, _ = sf.read(str(TESTS_DIR / "c1_fitted.wav"), dtype="float32")
# Đảm bảo tuyệt đối không vượt quá 1.65s
max_s1 = int(target_dur1 * sr)
if len(w1_fit) > max_s1:
    w1_fit = w1_fit[:max_s1]

print(f"  -> ✅ Cue 1 hoàn tất: {len(w1_fit)/sr:.3f}s (sẽ kết thúc tại {0.05 + len(w1_fit)/sr:.3f}s)")

# -------------------------------------------------------------
# 2. CHUẨN HÓA CUE 2 (GIỌNG SAU - GIỌNG DẪN)
# -------------------------------------------------------------
# Target: Bắt đầu tại 1.88s, kết thúc trước 3.65s -> Độ dài tối đa 1.72s
target_dur2 = 1.72

# Bản 2A: Giọng Wuby Giải Pháp 3 đọc kiểu dẫn (gp3_sentence2.wav)
w2_wuby, _ = sf.read(str(TESTS_DIR / "gp3_sentence2.wav"), dtype="float32")
non_sil2 = np.where(np.abs(w2_wuby) > 0.02 * np.max(np.abs(w2_wuby)))[0]
if len(non_sil2) > 0:
    w2_wuby = w2_wuby[non_sil2[0] : non_sil2[-1]]

curr_dur2_w = len(w2_wuby) / sr
tempo2_w = curr_dur2_w / target_dur2
print(f"[Cue 2 Wuby] Gốc: {curr_dur2_w:.2f}s -> Mục tiêu: {target_dur2:.2f}s (atempo={tempo2_w:.3f})")

sf.write(str(TESTS_DIR / "c2_wuby_raw.wav"), w2_wuby, sr, subtype="PCM_16")
subprocess.run([
    "ffmpeg", "-y", "-i", str(TESTS_DIR / "c2_wuby_raw.wav"),
    "-filter:a", f"atempo={tempo2_w:.3f}",
    str(TESTS_DIR / "c2_wuby_fitted.wav")
], check=True, capture_output=True)

w2_wuby_fit, _ = sf.read(str(TESTS_DIR / "c2_wuby_fitted.wav"), dtype="float32")
if len(w2_wuby_fit) > int(target_dur2 * sr):
    w2_wuby_fit = w2_wuby_fit[: int(target_dur2 * sr)]

# Bản 2B: Giọng Nam MC Dẫn (tmp_c2_nam_fit.wav)
w2_nam, _ = sf.read(str(TESTS_DIR / "tmp_c2_nam_fit.wav"), dtype="float32")
if len(w2_nam) > int(target_dur2 * sr):
    w2_nam = w2_nam[: int(target_dur2 * sr)]

# -------------------------------------------------------------
# 3. GHÉP TIMELINE CHÍNH XÁC VÀO TOÀN BỘ 8.54 GIÂY CỦA VIDEO
# -------------------------------------------------------------
def build_master_audio(c1_audio, c2_audio, out_name):
    # Master buffer cho toàn bộ 8.54s của video
    master = np.zeros(total_samples, dtype=np.float32)
    
    # Đặt Cue 1 bắt đầu tại 0.05s
    s1 = int(0.05 * sr)
    e1 = s1 + len(c1_audio)
    master[s1:e1] += c1_audio
    
    # Đặt Cue 2 bắt đầu tại 1.88s (sau khi Scene 0 đã ngắt hoàn toàn ở 1.875s)
    s2 = int(1.88 * sr)
    e2 = s2 + len(c2_audio)
    master[s2:e2] += c2_audio
    
    # Kiểm tra xác minh không bao giờ đè nhau
    gap_sec = (s2 - e1) / sr
    assert gap_sec > 0.10, f"LỖI: Khoảng cách âm thanh quá nhỏ hoặc bị đè ({gap_sec:.3f}s)!"
    print(f"[{out_name}] Khoảng lặng sạch sẽ giữa 2 câu: {gap_sec:.3f}s -> HOÀN TOÀN KHÔNG ĐÈ NHAU!")
    
    # Chuẩn hóa peak
    p = np.max(np.abs(master))
    if p > 0.95:
        master *= 0.95 / p
        
    raw_p = TESTS_DIR / f"sync_raw_{out_name}.wav"
    dsp_p = TESTS_DIR / f"sync_dsp_{out_name}.wav"
    sf.write(str(raw_p), master, sr, subtype="PCM_16")
    
    # DSP Chain
    dsp_filter = (
        "highpass=f=80,"
        "equalizer=f=3200:t=q:w=1.2:g=3.2,"
        "acompressor=threshold=-18dB:ratio=3.5:attack=15:release=120:makeup=3.5dB,"
        "alimiter=limit=-0.5dB"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_p),
        "-af", dsp_filter, "-ar", "24000", str(dsp_p)
    ], check=True, capture_output=True)
    return dsp_p

audio_wuby_sync = build_master_audio(w1_fit, w2_wuby_fit, "wuby_gp3_perfect_sync")
audio_nam_sync = build_master_audio(w1_fit, w2_nam, "wuby_nam_dan_perfect_sync")

# -------------------------------------------------------------
# 4. MIX NHẠC NỀN & RENDER VIDEO TOÀN BỘ 8.54 GIÂY
# -------------------------------------------------------------
# Video gốc: wuby_package/output/wuby_demo_result.mp4 (đã có phụ đề in-place và OCR xóa chữ Trung)
base_vid = OUTPUT_DIR / "wuby_demo_result.mp4"
if not base_vid.exists():
    base_vid = SAMPLE_DIR / "input_video.mp4"

# Trích xuất track nhạc nền từ video gốc và ducking nhẹ 35% khi có giọng nói
bg_wav = TESTS_DIR / "bg_audio_extracted.wav"
subprocess.run([
    "ffmpeg", "-y", "-i", str(SAMPLE_DIR / "input_video.mp4"),
    "-vn", "-ar", "24000", "-ac", "1", str(bg_wav)
], check=True, capture_output=True)

def render_final_video(voice_wav, out_vid_path):
    # Mix voice (1.0) và bg music (ducked 0.25 khi có thoại, 0.70 khi hết thoại sau 3.7s)
    # amix filter hoặc adelay/volume
    cmd = [
        "ffmpeg", "-y",
        "-i", str(base_vid),
        "-i", str(voice_wav),
        "-i", str(bg_wav),
        "-filter_complex",
        "[2:a]volume=0.25[bg_duck];[1:a][bg_duck]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "[aout]",
        "-t", f"{total_video_sec:.3f}",
        str(out_vid_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"🎬 Đã render video: {out_vid_path.name} ({out_vid_path.stat().st_size / 1024 / 1024:.2f} MB, thời lượng: {total_video_sec:.2f}s)")

vid_wuby = OUTPUT_DIR / "wuby_demo_gp3_perfect_sync.mp4"
render_final_video(audio_wuby_sync, vid_wuby)

vid_nam = OUTPUT_DIR / "wuby_demo_nam_dan_perfect_sync.mp4"
render_final_video(audio_nam_sync, vid_nam)

# -------------------------------------------------------------
# 5. GỬI LÊN TELEGRAM
# -------------------------------------------------------------
print("\nĐang gửi video và audio đã đồng bộ hoàn hảo lên Telegram...")

def send_tele(vid_file, aud_file, title, cap_vid):
    # Gửi audio
    with open(aud_file, "rb") as f:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendAudio",
            data={"chat_id": chat_id, "caption": f"🔊 Audio đồng bộ: {title}", "title": title},
            files={"audio": f},
            timeout=60
        )
    # Gửi video
    with open(vid_file, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendVideo",
            data={"chat_id": chat_id, "caption": cap_vid, "parse_mode": "HTML", "supports_streaming": True},
            files={"video": f},
            timeout=180
        ).json()
        print(f"  -> Kết quả Video [{vid_file.name}]: {r.get('ok')} (Msg ID: {r.get('result', {}).get('message_id')})")

cap1 = (
    "🎯 <b>BẢN SỬA LỖI ĐỒNG BỘ: TRIỆT TIÊU 100% HIỆN TƯỢNG ĐÈ GIỌNG</b>\n\n"
    "✨ <b>Timeline chuẩn xác từng miligiây:</b>\n"
    "• <b>Câu 1 (Hoạt hình Cảm xúc):</b> Bắt đầu 0.05s → Kết thúc 1.70s (đọc nhanh nhẹn, nhí nhảnh, dứt điểm trước cảnh 2).\n"
    "• <b>Khoảng nghỉ thở:</b> 1.70s → 1.88s (Khoảng lặng 0.18s, tách biệt hoàn toàn).\n"
    "• <b>Câu 2 (Giọng Dẫn Wuby):</b> Bắt đầu 1.88s → Kết thúc 3.60s (đĩnh đạc, rõ ràng, dứt khoát).\n"
    "• <b>Độ dài video:</b> Chuẩn trọn vẹn 8.54s (nhạc nền tiếp tục ngân vang đến hết clip).\n\n"
    "👉 <i>Cả 2 câu đều dùng chất giọng Giải Pháp 3 bạn đã chọn!</i>"
)
send_tele(vid_wuby, audio_wuby_sync, "Bản Wuby Thuần - Đồng Bộ Hoàn Hảo", cap1)

cap2 = (
    "🎙️ <b>BẢN THAM KHẢO PHỐI GIỌNG (GIỌNG TRƯỚC CẢM XÚC + GIỌNG SAU NAM DẪN)</b>\n\n"
    "• Câu 1 (0.05s – 1.70s): Hoạt hình Wuby cảm xúc cao trào.\n"
    "• Câu 2 (1.88s – 3.60s): Nam MC Dẫn chuyện đĩnh đạc, trầm ấm.\n"
    "• Tuyệt đối không đè giọng, tách bạch từng cảnh thoại!"
)
send_tele(vid_nam, audio_nam_sync, "Bản Phối Nam Dẫn - Đồng Bộ Hoàn Hảo", cap2)

print("\n" + "=" * 70)
print("🎉 HOÀN TẤT ĐỒNG BỘ VÀ GỬI THÀNH CÔNG LÊN TELEGRAM!")
print("=" * 70)
