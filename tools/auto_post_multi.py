"""
CLI Tool: Đăng bài tự động đa kênh (TikTok & Facebook Fanpage) qua BitBrowser
Tự động đồng bộ báo cáo trạng thái lên Google Sheet tab QUAN_LY_DANG_BAI
Hỗ trợ:
  1. Đăng theo hàng đợi từng Kênh riêng biệt từ Google Sheet (Mỗi kênh 1 video, 1 caption, 1 link riêng)
  2. Đăng trực tiếp từ tham số dòng lệnh
"""

import sys
import os
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from bitbrowser_service import BitBrowserClient
from posting_manager import PostingManager

def main():
    parser = argparse.ArgumentParser(description="Đăng bài tự động đa nền tảng (TikTok + Nhiều Fanpage Facebook) qua BitBrowser")
    parser.add_argument("--list", action="store_true", help="Liệt kê danh sách profiles trong BitBrowser")
    parser.add_argument("--login-tiktok", action="store_true", help="Mở trình duyệt để đăng nhập TikTok")
    parser.add_argument("--login-fb", action="store_true", help="Mở trình duyệt để đăng nhập Facebook / Fanpage")
    parser.add_argument("--run-sheet-queue", action="store_true", help="Tự động đọc Google Sheet và đăng toàn bộ các kênh đang ở trạng thái '⚪ Chờ đăng'")
    parser.add_argument("--row", type=int, help="Chỉ định chính xác số dòng trên Google Sheet để đăng (vd: --row 4)")
    parser.add_argument("--platform", choices=["tiktok", "facebook", "both"], default="tiktok", help="Nền tảng đăng bài")
    parser.add_argument("--profile", default="TiêuWuBy", help="Tên hoặc ID profile BitBrowser (mặc định: TiêuWuBy)")
    parser.add_argument("--channel", default="", help="Tên Fanpage / Kênh hiển thị trên Google Sheet")
    parser.add_argument("--pages", default="", help="Danh sách tên các Fanpage ngăn cách bằng dấu phẩy (vd: 'Trang 1, Trang 2, Trang 3')")
    parser.add_argument("--video", help="Đường dẫn file video mp4 cần đăng")
    parser.add_argument("--caption", default="", help="Nội dung Caption / Tiêu đề bài đăng")
    parser.add_argument("--hashtags", nargs="*", default=["reviewphim", "fyp", "trending"], help="Danh sách hashtag")
    parser.add_argument("--auto-close", action="store_true", help="Đóng trình duyệt sau khi đăng bài")

    args = parser.parse_args()

    client = BitBrowserClient()
    if not client.is_service_running():
        print("❌ [LỖI] BitBrowser chưa được khởi động trên máy tính của bạn!")
        print("👉 Vui lòng mở ứng dụng BitBrowser lên trước rồi chạy lại lệnh.")
        return

    # 1. Liệt kê profiles
    if args.list:
        profiles = client.list_profiles()
        print(f"\n📋 DANH SÁCH PROFILES TRONG BITBROWSER ({len(profiles)} profile):")
        print("-" * 65)
        for i, p in enumerate(profiles, start=1):
            print(f"[{i}] Tên: {p.get('name')} | ID: {p.get('id')} | Seq: {p.get('seq')}")
        print("-" * 65)
        return

    # 2. Đăng nhập TikTok
    if args.login_tiktok:
        print(f"\n🌐 MỞ TRÌNH DUYỆT ĐĂNG NHẬP TIKTOK: Profile '{args.profile}'...")
        with client.connect_playwright(args.profile, auto_close=False) as page:
            page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
            print("👉 Trình duyệt đã mở trang đăng nhập TikTok.")
            print("👉 Bạn hãy đăng nhập tài khoản. BitBrowser sẽ TỰ ĐỘNG LƯU PHIÊN ĐĂNG NHẬP vĩnh viễn.")
            input("\nSau khi đã đăng nhập thành công, nhấn [ENTER] tại đây để kết thúc...")
        return

    # 3. Đăng nhập Facebook Fanpage
    if args.login_fb:
        print(f"\n🌐 MỞ TRÌNH DUYỆT ĐĂNG NHẬP FACEBOOK: Profile '{args.profile}'...")
        with client.connect_playwright(args.profile, auto_close=False) as page:
            page.goto("https://business.facebook.com/latest/reels_composer", wait_until="domcontentloaded")
            print("👉 Trình duyệt đã mở Meta Business Suite / Facebook Reels.")
            print("👉 Bạn hãy đăng nhập tài khoản Facebook quản lý các Fanpage.")
            print("👉 BitBrowser sẽ TỰ ĐỘNG LƯU PHIÊN ĐĂNG NHẬP vĩnh viễn cho tất cả các Fanpage.")
            input("\nSau khi đã đăng nhập thành công, nhấn [ENTER] tại đây để kết thúc...")
        return

    # 4. Chạy hàng đợi từ Google Sheet (Mỗi kênh 1 dòng riêng biệt)
    if args.run_sheet_queue or args.row:
        mgr = PostingManager()
        mgr.run_queue_from_sheet(row_idx_target=args.row)
        return

    # 5. Đăng thủ công qua cờ dòng lệnh
    if not args.video:
        print("⚠️ Bạn chưa chỉ định file video cần đăng! Hãy dùng cờ --video <đường_dẫn_video.mp4> hoặc cờ --run-sheet-queue để chạy từ Google Sheet.")
        return

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        print(f"❌ File video không tồn tại: {video_path}")
        return

    page_list = [p.strip() for p in args.pages.split(",") if p.strip()] if args.pages else None

    print(f"\n🚀 BẮT ĐẦU QUY TRÌNH ĐĂNG BÀI:")
    print(f"  • Nền tảng: {args.platform.upper()}")
    print(f"  • Profile BitBrowser: {args.profile}")
    if page_list:
        print(f"  • Danh sách Fanpage ({len(page_list)} trang): {', '.join(page_list)}")
    print(f"  • Video: {video_path.name}")
    print(f"  • Caption: {args.caption}")
    print(f"  • Hashtags: {args.hashtags}")

    mgr = PostingManager()
    res = mgr.post_video(
        platform=args.platform,
        video_path=video_path,
        caption=args.caption,
        hashtags=args.hashtags,
        profile_identifier=args.profile,
        channel_name=args.channel,
        pages=page_list,
        auto_close=args.auto_close
    )

    print("\n" + "=" * 55)
    print("📊 TỔNG KẾT KẾT QUẢ ĐĂNG BÀI:")
    for target, outcome in res.items():
        stt_icon = "🟢 THÀNH CÔNG" if outcome.get("success") else "🔴 THẤT BẠI"
        print(f"  • {target}: {stt_icon} {outcome.get('error', '')}")
    print("👉 Đã đồng bộ chi tiết trạng thái từng Fanpage lên Google Sheet tab QUAN_LY_DANG_BAI!")
    print("=" * 55)

if __name__ == "__main__":
    main()
