# -*- coding: utf-8 -*-
"""
Script to send the newly rendered video to Telegram group.
Compresses video to < 45MB if needed so Telegram Bot API accepts it without error.
"""
import os
import sys
import shutil
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
load_dotenv(BACKEND_DIR / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = "-1004439918026"
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

video_path = ROOT_DIR / "workspace" / "7615140549834237673_rendered.mp4"
if not video_path.exists():
    video_path = Path("G:/My Drive/Video titok Trinh/Đã Render/Chi_Dep_Di_Cau/cau_ca_noi_tien_canh.mp4")

print(f"[*] File video gốc: {video_path} ({video_path.stat().st_size / 1024 / 1024:.2f} MB)")

# Nén video sang định dạng nhẹ tối ưu cho Telegram (< 20MB)
tele_send_path = ROOT_DIR / "workspace" / "7615140549834237673_tele_send.mp4"
print(f"[*] Đang tối ưu nén video nhẹ (< 20MB) để gửi lên Telegram...")
cmd = [
    "ffmpeg", "-y", "-loglevel", "error",
    "-i", str(video_path),
    "-vf", "scale=540:960",
    "-c:v", "libx264", "-b:v", "800k", "-maxrate", "1000k", "-bufsize", "1500k", "-preset", "veryfast",
    "-c:a", "aac", "-b:a", "96k",
    str(tele_send_path)
]
subprocess.run(cmd, check=True)
print(f"[+] Đã tạo bản video Telegram: {tele_send_path} ({tele_send_path.stat().st_size / 1024 / 1024:.2f} MB)")

caption = (
    "🎣 <b>VIDEO MỚI CẤU HÌNH 4: CÂU CÁ NƠI TIÊN CẢNH</b> 🚀\n\n"
    "🎙 <b>Giọng đọc:</b> OmniVoice Nữ Cute (giongnucute.wav) tốc độ <b>1.45x</b>\n"
    "🔢 <b>Chuẩn hóa số:</b> 100% chữ tiếng Việt chuẩn xác (04 ➔ không bốn, 5m4 ➔ năm mét bốn, 0.4 ➔ không phẩy bốn, 1:1 ➔ một một)\n"
    "🌊 <b>Hòa âm:</b> Sông nước 70% + Tiếng Trung 30% + Thuyết minh 100%\n"
    "📝 <b>Phụ đề:</b> Karaoke viền đen 4.0px canh giữa dải mờ\n"
    "📁 <b>Google Drive Bản Gốc Full HD:</b> <code>Đã Render/Chi_Dep_Di_Cau/cau_ca_noi_tien_canh.mp4</code>"
)

print(f"[*] Đang tải video lên Telegram chat {CHAT_ID}...")
with open(tele_send_path, 'rb') as vf:
    resp = requests.post(
        f"{API_BASE}/sendVideo",
        data={
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
            "supports_streaming": True
        },
        files={"video": vf},
        timeout=300
    )

print(f"[+] Phản hồi Telegram: status_code={resp.status_code}")
res_json = resp.json()
if res_json.get("ok"):
    print("[+] GỬI VIDEO LÊN TELEGRAM THÀNH CÔNG 100%!")
else:
    print(f"[-] Lỗi gửi Telegram: {res_json}")
