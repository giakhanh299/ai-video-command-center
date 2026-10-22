"""
Facebook Fanpage / Reels Auto Uploader via BitBrowser & Playwright (100% Human Simulation Engine)
Automates video and Reels posting to multiple Facebook Fanpages from 1 personal Facebook profile.
Supports multi-fanpage batch posting, realistic Bézier mouse movements, keystroke jitter, and evasions.
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from typing import Any
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from human_simulator import (
    apply_stealth_evasions,
    human_delay,
    human_click,
    human_type,
    human_scroll
)

FB_REELS_BUSINESS_URL = "https://business.facebook.com/latest/reels_composer"
FB_REELS_DIRECT_URL = "https://www.facebook.com/reels/create"

class FacebookFanpageUploader:
    def __init__(self, page: Page):
        self.page = page
        apply_stealth_evasions(self.page)

    def is_logged_in(self) -> bool:
        """Kiểm tra xem profile BitBrowser đã đăng nhập Facebook hay chưa."""
        current_url = self.page.url.lower()
        if "login" in current_url:
            return False

        selectors = [
            'div[aria-label*="Tài khoản"]',
            'div[aria-label*="Account"]',
            'svg[aria-label*="Facebook"]',
            'input[type="file"]',
            'div[role="feed"]'
        ]
        for sel in selectors:
            try:
                if self.page.locator(sel).first.is_visible(timeout=2000):
                    return True
            except Exception:
                pass
        return False

    def navigate_to_composer(self, wait_sec: int = 15) -> bool:
        """Mở trang tạo Reels / đăng bài Fanpage trên Meta Business Suite hoặc Facebook."""
        print(f"[Facebook] Đang chuyển đến giao diện đăng bài Reels ({FB_REELS_BUSINESS_URL})...")
        try:
            self.page.goto(FB_REELS_BUSINESS_URL, timeout=45000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"[Facebook] Không vào được Business Suite ({e}), chuyển sang {FB_REELS_DIRECT_URL}...")
            self.page.goto(FB_REELS_DIRECT_URL, timeout=45000, wait_until="domcontentloaded")

        human_delay(2.5, 4.0)

        for _ in range(wait_sec):
            if "login" in self.page.url.lower():
                print("⚠️ [Facebook] Tài khoản chưa đăng nhập Facebook! Vui lòng đăng nhập trên cửa sổ trình duyệt...")
                return False

            if self._find_file_input() or self.page.locator(':text("Thêm video"), :text("Tạo thước phim")').count() > 0:
                print("✅ [Facebook] Đã vào trang đăng bài / tạo Reels sẵn sàng (Mô phỏng người thật bật)!")
                return True
            human_delay(0.8, 1.2)

        print("⚠️ [Facebook] Không tìm thấy input upload sau thời gian chờ.")
        return False

    def select_fanpage(self, page_name: str) -> bool:
        """
        Chuyển đổi sang Fanpage mong muốn nếu tài khoản quản lý nhiều Fanpage.
        Meta Business Suite có bộ chọn trang ở thanh trên cùng hoặc góc trái.
        """
        if not page_name:
            return True

        print(f"[Facebook] Đang chọn Fanpage mục tiêu: '{page_name}'...")
        switcher_selectors = [
            'div[aria-label*="Chọn trang"]',
            'div[aria-label*="Select a Page"]',
            'div[aria-label*="chuyển trang"]',
            'div[aria-haspopup="listbox"]',
            'div[role="combobox"]',
            'button[aria-label*="Trang"]',
            'div[class*="account-switcher"]'
        ]
        switcher = None
        for sel in switcher_selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    switcher = loc
                    break
            except Exception:
                pass

        if switcher:
            try:
                human_click(self.page, switcher)
                human_delay(1.0, 2.0)

                # Tìm item trang
                page_item = self.page.locator(f'div[role="option"]:has-text("{page_name}")').first
                if not page_item.is_visible(timeout=1500):
                    page_item = self.page.locator(f'span:has-text("{page_name}")').first

                if page_item and page_item.is_visible():
                    human_click(self.page, page_item)
                    human_delay(2.0, 3.5)
                    print(f"✅ [Facebook] Đã chọn thành công Fanpage: '{page_name}'!")
                    return True

                # Nếu danh sách dài, thử tìm ô search
                search_input = self.page.locator('input[placeholder*="Tìm"], input[placeholder*="Search"]').first
                if search_input and search_input.is_visible():
                    search_input.fill(page_name)
                    human_delay(1.0, 1.8)
                    filtered = self.page.locator(f'div[role="option"]:has-text("{page_name}"), span:has-text("{page_name}")').first
                    if filtered and filtered.is_visible():
                        human_click(self.page, filtered)
                        human_delay(2.0, 3.5)
                        print(f"✅ [Facebook] Đã tìm và chọn Fanpage: '{page_name}'!")
                        return True
            except Exception as e:
                print(f"[Facebook] Lưu ý khi đổi Fanpage: {e}")

        print(f"ℹ️ [Facebook] Tiếp tục đăng bài trên Fanpage đang hoạt động hiện tại.")
        return False

    def _find_file_input(self):
        """Tìm thẻ input file cho video."""
        try:
            inp = self.page.locator('input[type="file"]').first
            if inp.count() > 0:
                return inp
        except Exception:
            pass

        for frame in self.page.frames:
            try:
                inp = frame.locator('input[type="file"]').first
                if inp.count() > 0:
                    return inp
            except Exception:
                pass
        return None

    def upload_reels(
        self,
        video_path: str | Path,
        caption: str = "",
        hashtags: list[str] | None = None,
        page_name: str | None = None,
        max_upload_wait_sec: int = 180,
        publish_mode: str = "Đăng ngay"
    ) -> dict[str, Any]:
        """
        Quy trình upload và đăng Reels lên Fanpage:
        1. Chọn Fanpage (nếu có chỉ định)
        2. Nạp file video mp4 vào input
        3. Dừng nghỉ tự nhiên quan sát
        4. Điền Caption & Hashtags bằng gõ tay người thật
        5. Bấm Tiếp -> Tiếp -> Đăng (Publish)
        6. Chờ thông báo thành công
        """
        video_file = Path(video_path).resolve()
        if not video_file.exists():
            raise FileNotFoundError(f"File video không tồn tại: {video_file}")

        print(f"[Facebook] Bắt đầu upload video lên Fanpage: {video_file.name} ({video_file.stat().st_size / (1024*1024):.2f} MB)")

        if page_name:
            self.select_fanpage(page_name)

        file_input = self._find_file_input()
        if file_input:
            file_input.set_input_files(str(video_file))
        else:
            them_btn = self.page.locator(':text("Thêm video")').first
            if them_btn.is_visible():
                with self.page.expect_file_chooser(timeout=15000) as fc_info:
                    them_btn.click()
                fc_info.value.set_files(str(video_file))
            else:
                raise RuntimeError("FB_UPLOAD_INPUT_NOT_FOUND: Không tìm thấy vùng tải video.")
        print("⏳ [Facebook] Đã nạp file video, đang đợi Facebook xử lý...")

        human_delay(3.5, 5.5)

        # Điền caption & hashtags
        full_caption = caption.strip()
        if hashtags:
            clean_tags = ["#" + tag.lstrip("#") for tag in hashtags]
            full_caption += " " + " ".join(clean_tags)

        if full_caption:
            print(f"[Facebook] Đang gõ Caption mô phỏng người thật: {full_caption[:50]}...")
            self._fill_caption_human(full_caption)

        human_delay(2.0, 3.5)
        human_scroll(self.page, 180)

        # Chờ upload hoàn tất
        print("⏳ [Facebook] Đang đợi upload hoàn tất 100%...")
        time.sleep(10)

        # Bấm các bước Tiếp (Next) của Meta Composer bằng human click
        for step in range(3):
            next_btn = self._find_button(["Tiếp", "Next", "Tiếp tục"])
            if next_btn and next_btn.is_enabled():
                print(f"[Facebook] Rê chuột bấm bước {step+1}: Tiếp...")
                human_click(self.page, next_btn)
                human_delay(2.0, 3.5)
            else:
                break

        # Xử lý chế độ đăng: Lưu bản nháp vs Đăng ngay
        is_draft = "nháp" in publish_mode.lower()
        if is_draft:
            print("📝 [Facebook] Chế độ: LƯU BẢN NHÁP (Draft). Đang chọn tùy chọn Lưu bản nháp...")
            draft_radio = self.page.locator('div[role="radio"]:has-text("nháp"), div[role="button"]:has-text("nháp"), :text("Lưu làm bản nháp"), :text("Lưu bản nháp")').first
            if draft_radio.is_visible():
                human_click(self.page, draft_radio)
                human_delay(1.5, 2.5)
            
            save_btn = self._find_button(["Lưu", "Lưu làm bản nháp", "Save", "Lưu bản nháp"])
            if save_btn:
                print("🚀 [Facebook] Bấm nút [LƯU BẢN NHÁP]...")
                human_click(self.page, save_btn)
                human_delay(4.0, 6.0)
            else:
                raise RuntimeError("FB_DRAFT_BUTTON_NOT_FOUND: Không tìm thấy nút Lưu bản nháp.")
        else:
            # Bấm nút Đăng / Chia sẻ / Publish
            print("🚀 [Facebook] Đang rê chuột bấm nút ĐĂNG REELS / BÀI VIẾT...")
            publish_btn = self._find_button(["Đăng", "Chia sẻ", "Publish", "Share"])
            if not publish_btn:
                raise RuntimeError("FB_PUBLISH_BUTTON_NOT_FOUND: Không tìm thấy nút Đăng.")

            human_click(self.page, publish_btn)
            human_delay(4.0, 6.0)

        # Kiểm tra thành công
        success = self._check_post_success(wait_sec=25)

        return {
            "success": success,
            "platform": "Facebook Fanpage / Reels",
            "page_name": page_name or "Mặc định",
            "video_name": video_file.name,
            "caption": full_caption,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _fill_caption_human(self, caption: str):
        """Điền nội dung bài viết vào khung soạn thảo Facebook với nhịp gõ người thật."""
        selectors = [
            'div[role="textbox"]',
            'div[contenteditable="true"]',
            'textarea[aria-label*="Mô tả"]',
            'textarea[placeholder*="Mô tả"]',
            'div[aria-label*="Mô tả"]',
            'div[aria-label*="caption"]'
        ]
        editor = None
        for sel in selectors:
            try:
                loc = self.page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    editor = loc
                    break
            except Exception:
                pass

        if editor:
            try:
                human_click(self.page, editor)
                human_delay(0.3, 0.5)
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                human_delay(0.2, 0.4)
                human_type(self.page, editor, caption)
                return
            except Exception:
                pass

        human_type(self.page, None, caption)

    def _find_button(self, labels: list[str]):
        """Tìm nút bấm theo danh sách nhãn tiếng Việt / tiếng Anh."""
        for label in labels:
            try:
                btn = self.page.locator(f'button:has-text("{label}")').first
                if btn.is_visible(timeout=1000):
                    return btn
            except Exception:
                pass
            try:
                btn = self.page.locator(f'div[role="button"]:has-text("{label}")').first
                if btn.is_visible(timeout=1000):
                    return btn
            except Exception:
                pass
        return None

    def _check_post_success(self, wait_sec: int = 25) -> bool:
        """Kiểm tra thông báo đăng bài thành công trên Facebook."""
        success_indicators = [
            'text="Thước phim của bạn đang được xử lý"',
            'text="Đã lên lịch"',
            'text="Đã đăng"',
            'text="Your reel is being processed"',
            'text="Your video has been published"',
            'text="Quản lý thước phim"'
        ]
        for _ in range(wait_sec):
            for ind in success_indicators:
                try:
                    if self.page.locator(ind).first.is_visible(timeout=1000):
                        print("🎉 [Facebook] ĐĂNG REELS / FANPAGE THÀNH CÔNG RỰC RỠ (HUMAN SIMULATED)!")
                        return True
                except Exception:
                    pass
            time.sleep(1)
        return False
