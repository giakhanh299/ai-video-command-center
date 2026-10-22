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
group_str = os.getenv("TELEGRAM_GROUP_ID", "-1004439918026,-5579042871").strip()
groups = [g.strip() for g in group_str.split(",") if g.strip()]

video_path = BASE_DIR / "wuby_package" / "output" / "wuby_demo_result.mp4"
report_path = BASE_DIR / "wuby_package" / "output" / "wuby_demo_result_voice_report.json"

if not video_path.exists():
    print(f"Lỗi: Không tìm thấy file video {video_path}")
    sys.exit(1)

caption = (
    "🎬 <b>VIDEO TEST: WUBY V4 MULTI-VOICE ROUTER (CLONE GIỌNG GỐC)</b>\n\n"
    "✅ <b>Trạng thái:</b> CLONE_SUCCESS (Clone giọng gốc sang Tiếng Việt)\n"
    "🎙️ <b>Backend:</b> KhanhTTS-OmniVoice (Discrete Acoustic Tokens)\n"
    "🎯 <b>Reference:</b> character_original.ref.wav (Giọng hoạt hình gốc)\n"
    "📝 <b>Transcript gốc:</b> 你不理你的人看你忙吧\n"
    "🇻🇳 <b>Đầu ra:</b> Đọc phụ đề tiếng Việt, bảo toàn màu giọng, cao độ F0 và giới tính gốc\n"
    "⚡ <b>Pipeline:</b> OCR Chinese + Scene Boundary + Inplace Erase + Voice Clone + NVENC"
)

print(f"Đang gửi video: {video_path.name} ({video_path.stat().st_size:,} bytes)")
for gid in groups:
    print(f"--> Gửi tới nhóm Telegram ID: {gid}...")
    try:
        with open(video_path, "rb") as f:
            res = requests.post(
                f"https://api.telegram.org/bot{token}/sendVideo",
                data={"chat_id": gid, "caption": caption, "parse_mode": "HTML"},
                files={"video": f},
                timeout=180
            )
        data = res.json()
        if data.get("ok"):
            print(f"✅ Gửi thành công tới {gid} (Message ID: {data['result']['message_id']})")
        else:
            # Handle supergroup migration if any
            migrate_to = data.get("parameters", {}).get("migrate_to_chat_id")
            if migrate_to:
                print(f"⚠️ Nhóm {gid} đã chuyển sang supergroup ID {migrate_to}. Đang thử lại...")
                with open(video_path, "rb") as f2:
                    res2 = requests.post(
                        f"https://api.telegram.org/bot{token}/sendVideo",
                        data={"chat_id": migrate_to, "caption": caption, "parse_mode": "HTML"},
                        files={"video": f2},
                        timeout=180
                    )
                data2 = res2.json()
                if data2.get("ok"):
                    print(f"✅ Gửi thành công tới supergroup {migrate_to}!")
                else:
                    print(f"❌ Thất bại gửi tới {migrate_to}: {data2}")
            else:
                print(f"❌ Thất bại gửi tới {gid}: {data}")
    except Exception as e:
        print(f"❌ Lỗi ngoại lệ khi gửi tới {gid}: {e}")
