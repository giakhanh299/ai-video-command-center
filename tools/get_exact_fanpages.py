import sys, os, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from bitbrowser_service import BitBrowserClient

def get_exact_fanpages():
    client = BitBrowserClient()
    with client.connect_playwright('TiêuWuBy', auto_close=False) as page:
        page.goto('https://www.facebook.com/pages/?category=your_pages', wait_until='domcontentloaded')
        time.sleep(4)

        # Lấy từ trang your_pages chính thức của Facebook:
        # Mỗi trang hiển thị là 1 khối thẻ với tên trang
        js = """
        () => {
            const pages = [];
            const links = Array.from(document.querySelectorAll('a[href*="/"]'));
            for (const a of links) {
                const text = (a.innerText || '').trim();
                const href = a.href || '';
                // Thường tên trang nằm trong thẻ span bên trong a và có link chứa id hoặc tên
                if (text && !text.includes('\\n') && text.length > 2 && text.length < 45) {
                    if (href.includes('facebook.com') && (href.includes('/profile.php?id=') || (href.split('/').length <= 5 && !href.includes('/pages/') && !href.includes('/watch') && !href.includes('/friends') && !href.includes('/marketplace') && !href.includes('/gaming') && !href.includes('/bookmarks')))) {
                        if (!['Bảng feed', 'Chào mừng', 'Bạn bè', 'Kỷ niệm', 'Đã lưu', 'Nhóm', 'Video', 'Chợ', 'Trang cá nhân', 'Trang chủ', 'Tất cả trang', 'Tạo trang mới'].includes(text)) {
                            pages.push({ name: text, url: href });
                        }
                    }
                }
            }
            return pages;
        }
        """
        raw = page.evaluate(js)
        unique = {}
        for r in raw:
            n = r['name']
            if n not in unique and not n.isdigit() and len(n) > 3:
                unique[n] = r['url']

        print("=== DANH SÁCH CHÍNH XÁC CÁC FANPAGE TRÊN NICK CỦA BẠN ===")
        for i, (name, u) in enumerate(unique.items(), 1):
            print(f"[{i}] {name} -> {u}")

if __name__ == '__main__':
    get_exact_fanpages()
