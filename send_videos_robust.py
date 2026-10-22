import sys
import os
import time
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')

BOT_TOKEN = "8531992939:AAFJmsTA0752eu96oHBa84MfZkjbejKxCe0"
CHAT_ID = "-1004462729383"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"

WORKSPACE = Path("D:/0.1_FACE_BOOK/Lay video tiktok/workspace")
videos = [
    ("CẤU HÌNH 2 (REVIEW PHIM ĐIỆN ẢNH - ĐÃ FIX)", WORKSPACE / "video_cauhinh2_blackbar.mp4",
     "🎬 <b>[ĐÃ FIX] CẤU HÌNH 2: REVIEW PHIM ĐIỆN ẢNH</b>\n\n"
     "✅ Title 6s biến mất đúng mốc, không kéo dài.\n"
     "✅ Dải đen đáy tự động bám trọn vùng chữ Trung, triệt tiêu lỗi 2 lớp sub.\n"
     "✅ Sub Việt lồng đúng tâm dải đen đè khít vị trí cũ.\n"
     "✅ Âm thanh qua True Peak Limiter EBU R128 (-0.92 limit) chống clipping."),
     
    ("CẤU HÌNH 3 (NAM REVIEW HỘP ĐEN - ĐÃ FIX)", WORKSPACE / "video_cauhinh3_sub_black.mp4",
     "🎬 <b>[ĐÃ FIX] CẤU HÌNH 3: NAM REVIEW (HỘP ĐEN)</b>\n\n"
     "✅ Thuật toán quét 45%..90% bắt chuẩn tọa độ cụm chữ Trung CenterY=1276px.\n"
     "✅ Hộp đen ôm khít cụm chữ (+3% trên/dưới), không che full ngang.\n"
     "✅ Sub Việt đè chính xác lên cụm chữ cũ.\n"
     "✅ Tắt sạch 100% tiếng người dẫn Trung."),
     
    ("CẤU HÌNH 4 (NAM REVIEW KÍNH MỜ BBOX - ĐÃ FIX)", WORKSPACE / "video_cauhinh4_blur.mp4",
     "🎬 <b>[ĐÃ FIX] CẤU HÌNH 4: NAM REVIEW (BLUR MỜ KÍNH)</b>\n\n"
     "✅ Khóa chuẩn tọa độ chữ tại CenterY=1276px (+3% trên/dưới).\n"
     "✅ Hiệu ứng kính mờ (Frosted glass) mượt mà + viền kính ôm trọn bbox.\n"
     "✅ Sub Việt nổi bật, che sạch chữ gốc.\n"
     "✅ Âm thanh Nam Minh chuẩn studio qua True Peak Limiter."),
     
    ("CẤU HÌNH 1 (WUBY ANIME - ĐÃ FIX)", WORKSPACE / "video_cauhinh1_wuby_hybrid.mp4",
     "🎬 <b>[ĐÃ FIX] CẤU HÌNH 1: WUBY ANIME</b>\n\n"
     "✅ Xóa sạch cột chữ Trung dọc bên trái.\n"
     "✅ Sửa dính từ tại 01:06.\n"
     "✅ Sửa câu dịch cứng tại 01:52 mượt mà, chuẩn điện ảnh.\n"
     "✅ Audio Limiter kiểm soát peak an toàn EBU R128.")
]

for name, path, cap in videos:
    if not path.exists():
        print(f"File không tồn tại: {path}")
        continue
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"\nĐang tải {name} ({size_mb:.2f} MB)...")
    for attempt in range(3):
        try:
            with open(path, "rb") as vf:
                r = requests.post(
                    API_URL,
                    data={"chat_id": CHAT_ID, "caption": cap, "parse_mode": "HTML", "supports_streaming": True},
                    files={"video": (path.name, vf, "video/mp4")},
                    timeout=240
                ).json()
            if r.get("ok"):
                print(f"  -> Tải thành công {name}!")
                break
            else:
                print(f"  -> Lỗi từ Telegram: {r}")
        except Exception as e:
            print(f"  -> Lỗi kết nối (lần {attempt+1}): {e}")
            time.sleep(3)

print("\nHOÀN THÀNH TẤT CẢ VIDEO LÊN TELEGRAM!")
