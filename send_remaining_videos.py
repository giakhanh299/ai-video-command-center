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

queue = [
    {
        "name": "CẤU HÌNH 3 (NAM REVIEW - HỘP ĐEN ĐÈ ĐÚNG TỌA ĐỘ)",
        "file": WORKSPACE / "video_cauhinh3_sub_black.mp4",
        "caption": (
            "🎬 <b>[ĐÃ FIX] CẤU HÌNH 3: NAM REVIEW (HỘP ĐEN)</b>\n\n"
            "✅ <b>Các điểm đã khắc phục triệt để:</b>\n"
            "• <b>Bắt trúng 100% tọa độ chữ Trung:</b> Quét từ 45%..90% chiều cao, khóa chuẩn dòng phụ đề tại CenterY=1276px.\n"
            "• <b>Hộp đen ôm khít cụm chữ:</b> Hộp đen chữ nhật bao đúng cụm chữ Trung (+3% padding trên/dưới), không che full ngang.\n"
            "• <b>Sub Việt đè kín chữ Trung:</b> Sub tiếng Việt lồng ngay tâm hộp đen, đè kín chữ cũ.\n"
            "• <b>Âm thanh:</b> Tắt sạch 100% tiếng người dẫn Trung, giọng Nam Minh rõ nét."
        )
    },
    {
        "name": "CẤU HÌNH 4 (NAM REVIEW - BLUR MỜ KÍNH CHUẨN BBOX)",
        "file": WORKSPACE / "video_cauhinh4_blur.mp4",
        "caption": (
            "🎬 <b>[ĐÃ FIX] CẤU HÌNH 4: NAM REVIEW (BLUR MỜ KÍNH)</b>\n\n"
            "✅ <b>Các điểm đã khắc phục triệt để:</b>\n"
            "• <b>Khóa chuẩn tọa độ chữ:</b> Bắt chính xác cụm chữ Trung ở CenterY=1276px (+3% padding trên/dưới).\n"
            "• <b>Hiệu ứng kính mờ (Frosted Glass):</b> Gaussian blur sigma=12 + phủ tối 58% + viền kính mỏng 1px ôm trọn bbox.\n"
            "• <b>Sub Việt nổi bật:</b> Sub trắng viền đen lồng ngay tâm dải kính mờ, che sạch chữ gốc.\n"
            "• <b>Âm thanh:</b> Giọng Nam Minh chuẩn studio qua True Peak Limiter."
        )
    },
    {
        "name": "CẤU HÌNH 1 (WUBY ANIME - ĐÃ FIX)",
        "file": WORKSPACE / "video_cauhinh1_wuby_hybrid.mp4",
        "caption": (
            "🎬 <b>[ĐÃ FIX] CẤU HÌNH 1: WUBY ANIME</b>\n\n"
            "✅ <b>Các điểm đã khắc phục triệt để:</b>\n"
            "• <b>Xóa sạch chữ Trung dọc bên trái:</b> Quét và làm mờ biến mất cột chữ dọc.\n"
            "• <b>Sửa dính từ:</b> Đã chỉnh đoạn 01:06 'tự nhận diện vé máy bay...'.\n"
            "• <b>Sửa câu dịch cứng:</b> Câu 01:52 dịch tự nhiên: 'Sợ nhất là bị người ta cố tình đánh giá xấu, một đánh giá xấu lúc này đúng là đòn chí mạng với tôi!'.\n"
            "• <b>Audio Limiter:</b> Thêm bộ lọc chuẩn EBU R128 (-0.92 limit), âm thanh trong trẻo, không clipping."
        )
    }
]

for item in queue:
    fpath = item["file"]
    if not fpath.exists():
        print(f"Bỏ qua {item['name']}: không thấy file", flush=True)
        continue
    size_mb = os.path.getsize(fpath) / (1024 * 1024)
    print(f"\nĐang tải {item['name']} ({size_mb:.2f} MB)...", flush=True)
    t0 = time.time()
    for attempt in range(3):
        try:
            with open(fpath, "rb") as vf:
                r = requests.post(
                    API_URL,
                    data={"chat_id": CHAT_ID, "caption": item["caption"], "parse_mode": "HTML", "supports_streaming": True},
                    files={"video": (fpath.name, vf, "video/mp4")},
                    timeout=240
                ).json()
            if r.get("ok"):
                print(f"  -> Tải thành công {item['name']} trong {time.time()-t0:.1f}s!", flush=True)
                break
            else:
                print(f"  -> Lỗi từ Telegram: {r}", flush=True)
        except Exception as e:
            print(f"  -> Lỗi kết nối (lần {attempt+1}): {e}", flush=True)
            time.sleep(3)

print("\n🎉 ĐÃ TẢI XONG TOÀN BỘ CÁC VIDEO LÊN TELEGRAM!", flush=True)
