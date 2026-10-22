"""
CLI Tool: Đăng bài tự động lên TikTok qua BitBrowser
Sử dụng:
  python tools/auto_post_tiktok.py --list
  python tools/auto_post_tiktok.py --login --profile TiêuWuBy
  python tools/auto_post_tiktok.py --video workspace/video_cauhinh1_wuby_hybrid.mp4 --caption "Review phim cực cuốn" --hashtags reviewphim wuby tiktok --profile TiêuWuBy
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
from tiktok_auto_post import TikTokUploader

def main():
    parser = argparse.ArgumentParser(description="Tự động đăng video TikTok qua BitBrowser")
    parser.add_argument("--list", action="store_true", help="Liệt kê tất cả profiles trong BitBrowser")
    parser.add_argument("--login", action="store_true", help="Mở trình duyệt để người dùng đăng nhập TikTok sẵn (lưu session)")
    parser.add_argument("--profile", default="TiêuWuBy", help="Tên hoặc ID của Profile BitBrowser (mặc định: TiêuWuBy)")
    parser.add_argument("--video", help="Đường dẫn file video mp4 cần đăng")
    parser.add_argument("--caption", default="", help="Nội dung Caption/Tiêu đề bài đăng")
    parser.add_argument("--hashtags", nargs="*", default=["reviewphim", "fyp", "tiktok"], help="Danh sách hashtag")
    parser.add_argument("--auto-close", action="store_true", help="Tự động đóng trình duyệt sau khi đăng xong")

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

    # 2. Chế độ đăng nhập sẵn
    if args.login:
        print(f"\n🌐 MỞ TRÌNH DUYỆT ĐỂ ĐĂNG NHẬP: Profile '{args.profile}'...")
        with client.connect_playwright(args.profile, auto_close=False) as page:
            page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
            print("👉 Trình duyệt đã mở trang đăng nhập TikTok.")
            print("👉 Bạn hãy đăng nhập tài khoản TikTok trên cửa sổ trình duyệt đó.")
            print("👉 BitBrowser sẽ TỰ ĐỘNG LƯU COOKIE & PHIÊN ĐĂNG NHẬP mãi mãi cho các lần sau.")
            input("\nSau khi đã đăng nhập thành công trên trình duyệt, nhấn [ENTER] tại đây để hoàn tất...")
        return

    # 3. Đăng video
    if not args.video:
        print("⚠️ Bạn chưa chỉ định file video cần đăng! Hãy dùng cờ --video <đường_dẫn_video.mp4>")
        print("Ví dụ:")
        print("  python tools/auto_post_tiktok.py --video workspace/video_cauhinh1_wuby_hybrid.mp4 --caption \"Phim siêu hay\"")
        return

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        print(f"❌ File video không tồn tại: {video_path}")
        return

    print(f"\n🚀 BẮT ĐẦU QUY TRÌNH ĐĂNG BÀI TỰ ĐỘNG LÊN TIKTOK...")
    print(f"  • Profile BitBrowser: {args.profile}")
    print(f"  • Video: {video_path.name}")
    print(f"  • Caption: {args.caption}")
    print(f"  • Hashtags: {args.hashtags}")

    with client.connect_playwright(args.profile, auto_close=args.auto_close) as page:
        uploader = TikTokUploader(page)
        
        # Mở trang upload
        ready = uploader.navigate_to_upload_page()
        if not ready:
            print("\n⚠️ Profile chưa đăng nhập tài khoản TikTok hoặc không vào được trang Upload.")
            print("👉 Vui lòng chạy lệnh: python tools/auto_post_tiktok.py --login --profile TiêuWuBy")
            print("để đăng nhập 1 lần duy nhất.")
            return

        # Thực hiện upload và đăng
        res = uploader.upload_video(
            video_path=video_path,
            caption=args.caption,
            hashtags=args.hashtags
        )

        if res.get("success"):
            print(f"\n🎉🎉🎉 ĐĂNG VIDEO THÀNH CÔNG RỰC RỠ: {res.get('video_name')}")
        else:
            print(f"\n⚠️ Đã thực hiện thao tác đăng nhưng chưa nhận diện được thông báo thành công. Vui lòng kiểm tra cửa sổ trình duyệt.")

if __name__ == "__main__":
    main()
