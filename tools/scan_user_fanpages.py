import sys, os, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from bitbrowser_service import BitBrowserClient

def scan():
    client = BitBrowserClient()
    if not client.is_service_running():
        print("❌ BitBrowser chưa bật.")
        return

    with client.connect_playwright('TiêuWuBy', auto_close=False) as page:
        print("🌐 Đang kiểm tra danh sách Fanpage của bạn trên Facebook...")
        page.goto('https://www.facebook.com/pages/?category=your_pages', wait_until='domcontentloaded')
        time.sleep(5)

        print(f"👉 URL hiện tại: {page.url}")

        # Kiểm tra xem có đang ở trang login không
        if "login" in page.url.lower():
            print("⚠️ Chưa đăng nhập hoặc bị điều hướng về trang đăng nhập.")
            return

        # 1. Tìm các thẻ link hoặc span chứa tên trang
        # Trên giao diện www.facebook.com/pages/?category=your_pages
        # Facebook hiển thị danh sách các trang trong các thẻ a hoặc div role="article"
        page.wait_for_timeout(3000)

        # Trích xuất tên trang từ trang Your Pages
        js_code = """
        () => {
            const results = [];
            // Tìm tất cả các link dẫn đến page profile
            const links = Array.from(document.querySelectorAll('a[href*="/"]'));
            for (const a of links) {
                const text = a.innerText ? a.innerText.trim() : '';
                const href = a.href || '';
                // Lọc các link trang thực tế (thường có text, không phải link chức năng chung)
                if (text && text.length > 2 && text.length < 50 && !text.includes('\\n')) {
                    if (href.includes('/profile.php') || href.includes('facebook.com/') && !href.includes('/pages/') && !href.includes('/groups/') && !href.includes('/friends/') && !href.includes('/watch/')) {
                        results.push({ name: text, href: href });
                    }
                }
            }
            return results;
        }
        """
        extracted = page.evaluate(js_code)

        # Lấy trang từ Meta Business Suite asset switcher nếu có
        page.goto('https://business.facebook.com/latest/home', wait_until='domcontentloaded')
        time.sleep(4)
        print(f"👉 URL Meta Business: {page.url}")

        js_mbs = """
        () => {
            const list = [];
            // Tìm tên account/page trên header của Meta Business Suite
            const headers = Array.from(document.querySelectorAll('span, div[role="heading"]'));
            for (const el of headers) {
                const t = el.innerText ? el.innerText.trim() : '';
                if (t && t.length > 2 && t.length < 50 && !t.includes('\\n') && !['Meta Business Suite', 'Trang chủ', 'Thông báo', 'Hộp thư', 'Bài viết'].includes(t)) {
                    list.push(t);
                }
            }
            return list;
        }
        """
        mbs_list = page.evaluate(js_mbs)

        print("\n" + "="*50)
        print("📋 KẾT QUẢ QUÉT TÀI KHOẢN FACEBOOK CỦA BẠN:")
        print("="*50)

        # Tổng hợp các tên khả nghi là Fanpage
        detected = set()
        for item in extracted:
            name = item.get('name', '')
            if name and not any(k in name.lower() for k in ['bảng tin', 'bạn bè', 'video', 'chợ', 'kỷ niệm', 'đã lưu', 'nhóm', 'trang', 'xem thêm', 'tất cả']):
                detected.add(name)

        for name in mbs_list:
            if name and not any(k in name.lower() for k in ['tạo bài viết', 'tạo thước phim', 'công cụ lập kế hoạch', 'quảng cáo', 'tất cả công cụ']):
                detected.add(name)

        if detected:
            print(f"🎉 Phát hiện {len(detected)} Fanpage / Kênh:")
            for idx, p in enumerate(sorted(detected), 1):
                print(f"  [{idx}] {p}")
        else:
            print("⚠️ Chưa bóc tách được danh sách cụ thể, chụp màn hình để kiểm tra...")
            page.screenshot(path="workspace/fb_pages_screen.png")
            print("Đã lưu ảnh chụp màn hình tại workspace/fb_pages_screen.png")

if __name__ == '__main__':
    scan()
