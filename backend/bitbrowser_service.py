"""
BitBrowser Automation Service
Connects to BitBrowser Local REST API (default port 54345) and controls browser profiles via Playwright CDP.
"""

from __future__ import annotations
import os
import sys
import time
import requests
from pathlib import Path
from typing import Any, Generator
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

DEFAULT_BITBROWSER_URL = "http://127.0.0.1:54345"

class BitBrowserClient:
    def __init__(self, api_url: str = DEFAULT_BITBROWSER_URL):
        self.api_url = api_url.rstrip("/")

    def is_service_running(self) -> bool:
        """Kiểm tra BitBrowser có đang chạy trên máy không."""
        try:
            resp = requests.post(f"{self.api_url}/browser/list", json={"page": 0, "pageSize": 1}, timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def list_profiles(self, page: int = 0, page_size: int = 50) -> list[dict[str, Any]]:
        """Lấy danh sách tất cả các profile (cửa sổ trình duyệt) trong BitBrowser."""
        try:
            resp = requests.post(
                f"{self.api_url}/browser/list",
                json={"page": page, "pageSize": page_size},
                timeout=10
            )
            data = resp.json()
            if data.get("success"):
                return data.get("data", {}).get("list", [])
            return []
        except Exception as e:
            print(f"[BitBrowser] Lỗi lấy danh sách profile: {e}")
            return []

    def find_profile(self, identifier: str) -> dict[str, Any] | None:
        """Tìm profile theo ID hoặc Tên (name)."""
        profiles = self.list_profiles(page=0, page_size=100)
        ident_lower = identifier.lower().strip()
        for p in profiles:
            if p.get("id") == identifier or p.get("name", "").lower().strip() == ident_lower:
                return p
        return None

    def open_profile(self, profile_id: str, args: list[str] | None = None) -> dict[str, Any]:
        """
        Mở cửa sổ trình duyệt theo Profile ID.
        Trả về dictionary chứa ws endpoint, http CDP endpoint, driver path, v.v.
        """
        payload: dict[str, Any] = {"id": profile_id}
        if args:
            payload["args"] = args
        resp = requests.post(f"{self.api_url}/browser/open", json=payload, timeout=20)
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"BITBROWSER_OPEN_FAILED: {data.get('msg', 'Unknown error')}")
        return data.get("data", {})

    def close_profile(self, profile_id: str) -> bool:
        """Đóng cửa sổ trình duyệt theo Profile ID."""
        try:
            resp = requests.post(f"{self.api_url}/browser/close", json={"id": profile_id}, timeout=10)
            data = resp.json()
            return bool(data.get("success"))
        except Exception as e:
            print(f"[BitBrowser] Lỗi đóng profile {profile_id}: {e}")
            return False

    def is_running(self, profile_id: str) -> bool:
        """Kiểm tra profile có đang mở không."""
        try:
            resp = requests.post(f"{self.api_url}/browser/pids", json={"ids": [profile_id]}, timeout=5)
            data = resp.json()
            pids = data.get("data", {})
            return str(profile_id) in pids and pids[str(profile_id)] is not None
        except Exception:
            return False

    @contextmanager
    def connect_playwright(self, profile_identifier: str, auto_close: bool = False) -> Generator[Page, None, None]:
        """
        Context manager tự động mở BitBrowser profile, kết nối Playwright qua CDP và trả về Page chính.
        Nếu auto_close=True, sẽ tự động đóng cửa sổ profile khi kết thúc block with.
        """
        target = self.find_profile(profile_identifier)
        if not target:
            raise ValueError(f"Không tìm thấy profile BitBrowser nào với tên/ID: '{profile_identifier}'")

        profile_id = target["id"]
        profile_name = target.get("name", profile_id)
        print(f"[BitBrowser] Đang mở profile: '{profile_name}' (ID: {profile_id})...")

        open_data = self.open_profile(profile_id)
        ws_endpoint = open_data.get("ws")
        if not ws_endpoint:
            raise RuntimeError(f"Không nhận được WebSocket CDP endpoint từ BitBrowser: {open_data}")

        print(f"[BitBrowser] Đã mở profile thành công. Kết nối Playwright tới {ws_endpoint}...")

        with sync_playwright() as pw:
            browser: Browser = pw.chromium.connect_over_cdp(ws_endpoint)
            try:
                context: BrowserContext = browser.contexts[0] if browser.contexts else browser.new_context()
                page: Page = context.pages[0] if context.pages else context.new_page()
                page.bring_to_front()
                yield page
            finally:
                browser.close()
                if auto_close:
                    print(f"[BitBrowser] Đang đóng profile '{profile_name}'...")
                    self.close_profile(profile_id)
