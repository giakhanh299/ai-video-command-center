"""
TikTok Auto Uploader & Poster via BitBrowser & Playwright (100% Human Simulation Engine)
Automates video upload to TikTok Creator Center / TikTok Studio using authenticated BitBrowser profiles.
Simulates natural mouse movements, realistic keystroke jitter, and evasions against bot detection.
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

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
TIKTOK_FALLBACK_URL = "https://www.tiktok.com/creator-center/upload"

class TikTokUploader:
    def __init__(self, page: Page):
        self.page = page
        apply_stealth_evasions(self.page)

    def is_logged_in(self) -> bool:
        """Kiểm tra xem profile BitBrowser đã đăng nhập TikTok hay chưa."""
        current_url = self.page.url.lower()
        if "login" in current_url:
            return False

        selectors = [
            'header [data-e2e="profile-icon"]',
            'div[class*="avatar"]',
            'img[class*="avatar"]',
            'span[class*="user-name"]',
            'button:has-text("Đăng")',
            'button:has-text("Post")',
            'input[type="file"]'
        ]
        for sel in selectors:
            try:
                if self.page.locator(sel).first.is_visible(timeout=2000):
                    return True
            except Exception:
                pass
        return False

    def navigate_to_upload_page(self, wait_sec: int = 15) -> bool:
        """Mở trang Upload của TikTok và kiểm tra sẵn sàng."""
        print(f"[TikTok] Đang chuyển đến trang Upload ({TIKTOK_UPLOAD_URL})...")
        try:
            self.page.goto(TIKTOK_UPLOAD_URL, timeout=45000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"[TikTok] Lỗi mở {TIKTOK_UPLOAD_URL}: {e}, thử {TIKTOK_FALLBACK_URL}...")
            self.page.goto(TIKTOK_FALLBACK_URL, timeout=45000, wait_until="domcontentloaded")

        human_delay(2.0, 3.5)

        for _ in range(wait_sec):
            if "login" in self.page.url.lower():
                print("⚠️ [TikTok] Tài khoản chưa đăng nhập! Vui lòng đăng nhập trên cửa sổ trình duyệt...")
                return False

            file_input = self._find_file_input()
            if file_input:
                print("✅ [TikTok] Đã vào trang Upload sẵn sàng (Mô phỏng người thật bật)!")
                return True
            human_delay(0.8, 1.2)

        print("⚠️ [TikTok] Không tìm thấy input upload sau thời gian chờ.")
        return False

    def _find_file_input(self):
        """Tìm thẻ input file (kể cả khi nằm trong iframe của TikTok Studio)."""
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

    def upload_video(
        self,
        video_path: str | Path,
        caption: str = "",
        hashtags: list[str] | None = None,
        schedule_time_str: str | None = None,
        max_upload_wait_sec: int = 180
    ) -> dict[str, Any]:
        """
        Quy trình upload và đăng video mô phỏng người thật:
        1. Đưa file video mp4 vào
        2. Dừng nghỉ tự nhiên quan sát
        3. Cuộn nhẹ trang và gõ Caption/Hashtags từng chữ với độ trễ jitter
        4. Chờ upload xử lý 100%
        5. Rê chuột Bézier đến nút Đăng và click
        6. Chờ thông báo thành công
        """
        video_file = Path(video_path).resolve()
        if not video_file.exists():
            raise FileNotFoundError(f"File video không tồn tại: {video_file}")

        print(f"[TikTok] Bắt đầu upload video: {video_file.name} ({video_file.stat().st_size / (1024*1024):.2f} MB)")

        file_input = self._find_file_input()
        if not file_input:
            raise RuntimeError("TIKTOK_UPLOAD_INPUT_NOT_FOUND: Không tìm thấy vùng tải video.")

        file_input.set_input_files(str(video_file))
        print("⏳ [TikTok] Đã nạp file video, đang chờ hệ thống TikTok tiếp nhận...")

        human_delay(3.5, 5.5)

        # Điền Caption & Hashtags bằng gõ tay người thật
        full_caption = caption.strip()
        if hashtags:
            clean_tags = ["#" + tag.lstrip("#") for tag in hashtags]
            full_caption += " " + " ".join(clean_tags)

        if full_caption:
            print(f"[TikTok] Đang gõ Caption mô phỏng người thật (keystroke jitter): {full_caption[:50]}...")
            self._fill_caption_human(full_caption)

        # Cuộn chuột nhẹ nhàng xem lại nội dung
        human_delay(1.5, 2.5)
        human_scroll(self.page, 150)

        # Chờ upload hoàn tất
        print("⏳ [TikTok] Đang đợi upload hoàn tất 100%...")
        uploaded = self._wait_for_upload_finish(max_upload_wait_sec)
        if not uploaded:
            print("⚠️ [TikTok] Hết thời gian chờ progress bar, kiểm tra nút Đăng...")

        human_delay(2.0, 4.0)

        # Rê chuột tự nhiên và bấm nút Đăng (Post)
        print("🚀 [TikTok] Đang rê chuột bấm nút ĐĂNG bài...")
        post_btn = self._find_post_button()
        if not post_btn:
            raise RuntimeError("TIKTOK_POST_BUTTON_NOT_FOUND: Không tìm thấy nút Đăng.")

        human_click(self.page, post_btn)
        human_delay(3.0, 5.0)

        # Kiểm tra kết quả
        success = self._check_post_success(wait_sec=20)

        return {
            "success": success,
            "video_name": video_file.name,
            "caption": full_caption,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _fill_caption_human(self, caption: str):
        """Nhập nội dung bài đăng vào khung soạn thảo của TikTok với nhịp gõ người thật."""
        selectors = [
            'div[contenteditable="true"]',
            'div[class*="editor"] div[contenteditable="true"]',
            'div[class*="notranslate"][contenteditable="true"]',
            'textarea[placeholder*="video"]',
            'div[data-e2e="caption-input"]'
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
                human_delay(0.3, 0.6)
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                human_delay(0.2, 0.4)
                human_type(self.page, editor, caption)
                return
            except Exception as e:
                print(f"[TikTok] Chuyển fallback gõ bàn phím: {e}")

        # Fallback
        human_type(self.page, None, caption)

    def _wait_for_upload_finish(self, max_wait_sec: int) -> bool:
        """Đợi upload video kết thúc."""
        t0 = time.time()
        while time.time() - t0 < max_wait_sec:
            try:
                post_btn = self._find_post_button()
                if post_btn and post_btn.is_enabled():
                    progress_loc = self.page.locator('div:has-text("%")')
                    if progress_loc.count() == 0:
                        return True
            except Exception:
                pass
            human_delay(2.0, 3.5)
        return False

    def _find_post_button(self):
        """Tìm nút Đăng / Post trên giao diện TikTok Studio."""
        selectors = [
            'button:has-text("Đăng")',
            'button:has-text("Post")',
            'button[data-e2e="post_video_button"]',
            'button[class*="btn-post"]'
        ]
        for sel in selectors:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    return btn
            except Exception:
                pass
        return None

    def _check_post_success(self, wait_sec: int = 20) -> bool:
        """Kiểm tra thông báo đăng bài thành công."""
        success_indicators = [
            'text="Video của bạn đã được tải lên"',
            'text="Your video has been uploaded"',
            'text="Quản lý bài đăng"',
            'text="Manage your posts"',
            'button:has-text("Tải video khác lên")',
            'button:has-text("Upload another video")'
        ]
        for _ in range(wait_sec):
            for ind in success_indicators:
                try:
                    if self.page.locator(ind).first.is_visible(timeout=1000):
                        print("🎉 [TikTok] ĐĂNG VIDEO THÀNH CÔNG RỰC RỠ (HUMAN SIMULATED)!")
                        return True
                except Exception:
                    pass
            time.sleep(1)
        return False
