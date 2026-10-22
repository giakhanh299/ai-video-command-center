import sys
import os
import time
import subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent

def show_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 75)
        print("   🚀 TOOL TỰ ĐỘNG ĐĂNG BÀI ĐA KÊNH FACEBOOK & TIKTOK QUA BITBROWSER")
        print("   (Mỗi Kênh 1 Video Riêng - 1 Link Riêng - Đồng Bộ Google Sheet)")
        print("=" * 75)
        print()
        print(" [1] Liệt kê danh sách Profile trong BitBrowser")
        print(" [2] Đăng nhập TIKTOK (Mở profile TiêuWuBy)")
        print(" [3] Đăng nhập FACEBOOK (Mở profile TiêuWuBy)")
        print(" [4] 🌟 TỰ ĐỘNG ĐĂNG LIÊN HOÀN CẢ 4 FANPAGE THEO HÀNG ĐỢI GOOGLE SHEET")
        print()
        print(" --- ĐĂNG LẺ TỪNG FANPAGE THEO YÊU CẦU ---")
        print(" [5] Đăng lên Fanpage: Vũ Trụ Cày Phim (Video Cấu hình 2 - Dải đen điện ảnh)")
        print(" [6] Đăng lên Fanpage: Tiểu Wuby (Video Cấu hình 1 - Wuby Anime)")
        print(" [7] Đăng lên Fanpage: Boxman Kể Chuyện (Video Cấu hình 3 - Nam Review)")
        print(" [8] Đăng lên Fanpage: Review Sách Có Tâm (Video Cấu hình 4 - Kính Mờ)")
        print(" [0] Thoát")
        print()
        choice = input("👉 Nhập số lựa chọn của bạn (0-8): ").strip()

        if choice == '0':
            print("Tạm biệt!")
            break
        elif choice == '1':
            subprocess.run([sys.executable, "tools/auto_post_multi.py", "--list"], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '2':
            subprocess.run([sys.executable, "tools/auto_post_multi.py", "--login-tiktok", "--profile", "TiêuWuBy"], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '3':
            subprocess.run([sys.executable, "tools/auto_post_multi.py", "--login-fb", "--profile", "TiêuWuBy"], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '4':
            print("\n🚀 Đang tự động đọc hàng đợi từ Google Sheet và đăng liên hoàn...")
            subprocess.run([sys.executable, "tools/auto_post_multi.py", "--run-sheet-queue"], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '5':
            subprocess.run([
                sys.executable, "tools/auto_post_multi.py",
                "--platform", "facebook",
                "--channel", "Vũ Trụ Cày Phim",
                "--video", "workspace/video_cauhinh2_blackbar.mp4",
                "--caption", "Khách sộp của quản lý Dương - Tập 1 cực hay #VuTruCayPhim #reviewphim #reels"
            ], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '6':
            subprocess.run([
                sys.executable, "tools/auto_post_multi.py",
                "--platform", "facebook",
                "--channel", "Tiểu Wuby",
                "--video", "workspace/video_cauhinh1_wuby_hybrid.mp4",
                "--caption", "Tiểu Wuby kể chuyện nhà hàng siêu hài hước #TieuWuby #wuby #reels"
            ], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '7':
            subprocess.run([
                sys.executable, "tools/auto_post_multi.py",
                "--platform", "facebook",
                "--channel", "Boxman Kể Chuyện",
                "--video", "workspace/video_cauhinh3_sub_black.mp4",
                "--caption", "Chuyện phục vụ và khách sộp thích chiếm lời #BoxmanKeChuyen #reels"
            ], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        elif choice == '8':
            subprocess.run([
                sys.executable, "tools/auto_post_multi.py",
                "--platform", "facebook",
                "--channel", "Review Sách Có Tâm",
                "--video", "workspace/video_cauhinh4_blur.mp4",
                "--caption", "Bài học cuộc sống từ việc ăn uống thường ngày #ReviewSachCoTam #reels"
            ], cwd=str(BASE_DIR))
            input("\nNhấn Enter để quay lại menu...")
        else:
            print("Lựa chọn không hợp lệ, vui lòng thử lại!")
            time.sleep(1.2)

if __name__ == '__main__':
    show_menu()
