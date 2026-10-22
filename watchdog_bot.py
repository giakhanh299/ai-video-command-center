"""TikTok Dubber 24/7 Watchdog & Auto-Healer
Giám sát toàn diện hệ thống:
1. Supervisor (run_bot.py)
2. Telegram Bot (telegram_bot.py & heartbeat)
3. FastAPI Backend (Port 8005)
4. Cloudflare Tunnel (cloudflared)
Tự động hồi sinh mọi tiến trình bị tắt, crash, hoặc treo mạng.
"""

import os
import sys
import time
import json
import psutil
import requests
import subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
WATCHDOG_LOG = LOGS_DIR / "watchdog.log"
BOT_HEARTBEAT = LOGS_DIR / "bot_heartbeat.json"
SUPERVISOR_HEARTBEAT = LOGS_DIR / "supervisor_heartbeat.json"

def log_event(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [Watchdog] {msg}\n"
    print(line, end="")
    try:
        with open(WATCHDOG_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

def is_process_running(keyword: str) -> list[psutil.Process]:
    """Tìm tất cả tiến trình python có commandline chứa keyword."""
    matching = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info['name'] or "").lower()
            if 'python' not in name:
                continue
            cmd = " ".join(proc.info['cmdline'] or [])
            if keyword in cmd:
                matching.append(proc)
        except Exception:
            pass
    return matching

def check_and_heal_bot():
    """Đảm bảo run_bot.py và telegram_bot.py luôn sống và phản hồi."""
    supervisors = is_process_running("run_bot.py")
    bots = is_process_running("telegram_bot.py")

    need_restart = False

    # 1. Kiểm tra supervisor
    if not supervisors:
        log_event("Không tìm thấy tiến trình run_bot.py! Đang kích hoạt khởi động...")
        need_restart = True
    else:
        # Kiểm tra supervisor heartbeat
        if SUPERVISOR_HEARTBEAT.exists():
            try:
                hb = json.loads(SUPERVISOR_HEARTBEAT.read_text(encoding="utf-8"))
                hb_age = time.time() - float(hb.get("timestamp", 0))
                if hb_age > 180:
                    log_event(f"Supervisor mất nhịp tim {int(hb_age)}s! Cưỡng chế khởi động lại...")
                    for s in supervisors:
                        try:
                            s.kill()
                        except Exception:
                            pass
                    need_restart = True
            except Exception:
                pass

    # 2. Kiểm tra telegram_bot heartbeat
    if not need_restart and bots:
        if BOT_HEARTBEAT.exists():
            try:
                bot_hb = json.loads(BOT_HEARTBEAT.read_text(encoding="utf-8"))
                bot_age = time.time() - float(bot_hb.get("timestamp", 0))
                if bot_age > 180:
                    log_event(f"Telegram Bot mất nhịp tim {int(bot_age)}s (nghi treo socket/deadlock)! Đang khởi động lại...")
                    for b in bots:
                        try:
                            b.kill()
                        except Exception:
                            pass
                    need_restart = True
            except Exception:
                pass
    elif not need_restart and not bots:
        log_event("Supervisor đang chạy nhưng không thấy telegram_bot.py con. Đang khởi động lại...")
        need_restart = True

    if need_restart:
        # Dọn dẹp tiến trình cũ nếu còn sót
        for p in is_process_running("telegram_bot.py") + is_process_running("run_bot.py"):
            try:
                p.kill()
            except Exception:
                pass
        time.sleep(1)

        # Khởi động supervisor hoàn toàn độc lập (Detached Process)
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        python_exe = sys.executable
        subprocess.Popen(
            [python_exe, "-u", "run_bot.py"],
            cwd=str(ROOT_DIR),
            creationflags=flags,
            close_fds=True
        )
        log_event("Đã khởi chạy Supervisor run_bot.py mới thành công!")
    else:
        log_event("Telegram Bot & Supervisor: 🟢 HOẠT ĐỘNG TỐT")

def check_and_heal_backend():
    """Đảm bảo FastAPI backend port 8005 luôn online."""
    try:
        r = requests.get("http://127.0.0.1:8005/docs", timeout=5)
        if r.status_code == 200:
            log_event("Backend 8005: 🟢 HOẠT ĐỘNG TỐT")
            return
    except Exception:
        pass

    log_event("Backend 8005 không phản hồi! Đang khởi động lại...")
    # Dọn dẹp tiến trình uvicorn 8005 cũ
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.info['cmdline'] or [])
            if "8005" in cmd and "uvicorn" in cmd:
                proc.kill()
        except Exception:
            pass

    time.sleep(1)
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT_DIR / "run_backend.ps1")],
        cwd=str(ROOT_DIR),
        creationflags=flags,
        close_fds=True
    )
    log_event("Đã khởi chạy Backend 8005 thành công!")

def check_and_heal_tunnel():
    """Đảm bảo Cloudflare Tunnel tiktok-dubber đang kết nối."""
    cloudflared_running = False
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = (proc.info['name'] or "").lower()
            if 'cloudflared' in name:
                cmd = " ".join(proc.info['cmdline'] or [])
                if "tiktok-dubber" in cmd:
                    cloudflared_running = True
                    break
        except Exception:
            pass

    if cloudflared_running:
        log_event("Cloudflare Tunnel: 🟢 HOẠT ĐỘNG TỐT")
    else:
        log_event("Cloudflare Tunnel không chạy! Đang khởi động lại...")
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT_DIR / "run_tunnel.ps1")],
            cwd=str(ROOT_DIR),
            creationflags=flags,
            close_fds=True
        )
        log_event("Đã khởi chạy Cloudflare Tunnel thành công!")

def main_once():
    log_event("=== Bắt đầu quét kiểm tra sức khỏe hệ thống 24/7 ===")
    check_and_heal_bot()
    check_and_heal_backend()
    check_and_heal_tunnel()
    log_event("=== Hoàn tất kiểm tra ===\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        log_event("Watchdog khởi động ở chế độ nền (Daemon lặp lại mỗi 60s)...")
        while True:
            try:
                main_once()
            except Exception as e:
                log_event(f"Lỗi kiểm tra Watchdog: {e}")
            time.sleep(60)
    else:
        main_once()
