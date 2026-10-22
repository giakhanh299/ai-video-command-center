import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / "backend" / ".env")

token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
chat_id = "-1004439918026"

ab_dir = BASE_DIR / "tests" / "ab_test"
files = [
    ("A_default_voice.wav", "🔊 <b>File A (Default Voice):</b> Giọng mặc định Hoài My (hamy) - KHÔNG CLONE (F0 ~224 Hz)"),
    ("B_reference_01.wav", "🎙️ <b>File B (Clone Nhân Vật Hoạt Hình Gốc):</b> F0 ~335.7 Hz - Giọng nhân vật anime/hoạt hình cao vút đúng bản gốc"),
    ("C_reference_02.wav", "🎙️ <b>File C (Clone Nam Dẫn Chương Trình):</b> F0 ~137.5 Hz - Giọng nam MC trầm ấm (chênh lệch F0 ~198.1 Hz với File B)")
]

print("Đang gửi bộ test A/B âm thanh lên nhóm Telegram...")
for fname, cap in files:
    fpath = ab_dir / fname
    if fpath.exists():
        with open(fpath, "rb") as f:
            res = requests.post(
                f"https://api.telegram.org/bot{token}/sendAudio",
                data={"chat_id": chat_id, "caption": cap, "parse_mode": "HTML", "title": fname},
                files={"audio": f},
                timeout=60
            )
        d = res.json()
        print(f"✅ {fname}: {d.get('ok')}")
    else:
        print(f"⚠️ Không tìm thấy {fname}")
