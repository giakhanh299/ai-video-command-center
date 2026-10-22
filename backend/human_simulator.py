"""
Human Simulator & Anti-Bot Stealth Engine for Playwright & BitBrowser
Simulates 100% human-like behavior (Bezier mouse trajectories, realistic typing jitter, random hesitation, scrolling).
Eliminates any automation detection fingerprints on TikTok and Facebook/Meta.
"""

from __future__ import annotations
import math
import random
import time
import sys
from typing import Any
from playwright.sync_api import Page, Locator

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

STEALTH_INJECT_JS = """
// 1. Xóa bỏ cờ navigator.webdriver an toàn
try {
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
} catch (e) {}

// 2. Fake Chrome Runtime giống trình duyệt thật 100%
try {
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
            PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformNaclArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
            onMessage: { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
            connect: function() { return { onMessage: { addListener: function() {} }, postMessage: function() {} }; }
        };
    }
} catch (e) {}

// 3. Fake permissions query
try {
    if (window.navigator && window.navigator.permissions) {
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    }
} catch (e) {}

// 4. Fake Languages
try {
    Object.defineProperty(navigator, 'languages', {
        get: () => ['vi-VN', 'vi', 'en-US', 'en']
    });
} catch (e) {}
"""

def apply_stealth_evasions(page: Page):
    """Áp dụng bộ script xóa sạch mọi dấu vết tự động hóa trên trang."""
    try:
        page.add_init_script(STEALTH_INJECT_JS)
        page.evaluate(STEALTH_INJECT_JS)
    except Exception:
        pass

def human_delay(min_sec: float = 1.0, max_sec: float = 2.5):
    """Nghỉ ngơi ngẫu nhiên như người thật đang quan sát màn hình."""
    duration = random.uniform(min_sec, max_sec)
    time.sleep(duration)

def _generate_bezier_curve(x1: float, y1: float, x2: float, y2: float, num_points: int = 25) -> list[tuple[float, float]]:
    """Tạo đường cong Bézier tự nhiên mô phỏng chuyển động tay cầm chuột của người thật."""
    cx1 = x1 + (x2 - x1) * random.uniform(0.2, 0.4) + random.uniform(-40, 40)
    cy1 = y1 + (y2 - y1) * random.uniform(0.2, 0.4) + random.uniform(-40, 40)
    cx2 = x1 + (x2 - x1) * random.uniform(0.6, 0.8) + random.uniform(-40, 40)
    cy2 = y1 + (y2 - y1) * random.uniform(0.6, 0.8) + random.uniform(-40, 40)

    points = []
    for i in range(num_points + 1):
        t = i / float(num_points)
        xt = (1-t)**3 * x1 + 3*(1-t)**2 * t * cx1 + 3*(1-t) * t**2 * cx2 + t**3 * x2
        yt = (1-t)**3 * y1 + 3*(1-t)**2 * t * cy1 + 3*(1-t) * t**2 * cy2 + t**3 * y2
        points.append((xt, yt))
    return points

def human_move_mouse(page: Page, target_x: float, target_y: float):
    """Di chuyển chuột theo đường cong ngẫu nhiên và tốc độ thay đổi dần."""
    start_x = getattr(page, "_last_mouse_x", random.uniform(100, 300))
    start_y = getattr(page, "_last_mouse_y", random.uniform(100, 300))

    steps = random.randint(18, 28)
    curve = _generate_bezier_curve(start_x, start_y, target_x, target_y, steps)

    for pt_x, pt_y in curve:
        page.mouse.move(pt_x, pt_y)
        time.sleep(random.uniform(0.005, 0.018))

    setattr(page, "_last_mouse_x", target_x)
    setattr(page, "_last_mouse_y", target_y)

def human_click(page: Page, locator: Locator, timeout_ms: int = 5000):
    """Click chuẩn người thật có độ trễ mousedown/mouseup."""
    box = locator.bounding_box(timeout=timeout_ms)
    if not box:
        locator.click()
        return

    target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
    target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)

    human_move_mouse(page, target_x, target_y)
    time.sleep(random.uniform(0.15, 0.35))

    page.mouse.down()
    time.sleep(random.uniform(0.06, 0.14))
    page.mouse.up()
    time.sleep(random.uniform(0.2, 0.5))

def human_type(page: Page, locator: Locator | None, text: str, mistake_chance: float = 0.02):
    """Gõ phím mô phỏng người thật có keystroke jitter."""
    if locator:
        try:
            locator.click()
            time.sleep(random.uniform(0.2, 0.4))
        except Exception:
            pass

    for char in text:
        if mistake_chance > 0 and random.random() < mistake_chance and char.isalpha():
            typo = random.choice("abcdefghijklmnopqrstuvwxyz")
            page.keyboard.type(typo, delay=random.randint(60, 140))
            time.sleep(random.uniform(0.18, 0.35))
            page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.12, 0.25))

        delay = random.randint(45, 135)
        page.keyboard.type(char, delay=delay)

        if char in (" ", ",", ".", "!", "?", "\n"):
            time.sleep(random.uniform(0.15, 0.40))
        elif random.random() < 0.08:
            time.sleep(random.uniform(0.25, 0.55))

def human_scroll(page: Page, delta_y: int = 300):
    """Lăn chuột từ từ có gia tốc."""
    direction = 1 if delta_y > 0 else -1
    remaining = abs(delta_y)
    while remaining > 0:
        step = min(remaining, random.randint(40, 110))
        page.mouse.wheel(0, step * direction)
        remaining -= step
        time.sleep(random.uniform(0.04, 0.09))
    time.sleep(random.uniform(0.3, 0.8))
