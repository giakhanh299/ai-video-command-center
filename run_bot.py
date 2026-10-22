import os
import sys
import time
import json
import signal
import subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "bot.log"
SUPERVISOR_PID_FILE = LOGS_DIR / "supervisor.pid"
HEARTBEAT_FILE = LOGS_DIR / "bot_heartbeat.json"
SUPERVISOR_HEARTBEAT_FILE = LOGS_DIR / "supervisor_heartbeat.json"

current_child_proc = None

def signal_handler(sig, frame):
    global current_child_proc
    print("[Supervisor] Nhận tín hiệu dừng, đang tắt bot con...")
    if current_child_proc and current_child_proc.poll() is None:
        try:
            current_child_proc.terminate()
            current_child_proc.wait(timeout=3)
        except Exception:
            try:
                current_child_proc.kill()
            except Exception:
                pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def ensure_single_supervisor():
    """Đảm bảo chỉ có 1 supervisor run_bot.py chạy trên máy."""
    my_pid = os.getpid()
    if SUPERVISOR_PID_FILE.exists():
        try:
            import psutil
            old_pid = int(SUPERVISOR_PID_FILE.read_text().strip())
            if old_pid != my_pid and psutil.pid_exists(old_pid):
                p = psutil.Process(old_pid)
                cmd = " ".join(p.cmdline() or [])
                if "run_bot.py" in cmd:
                    print(f"[*] Supervisor cũ (PID {old_pid}) đang chạy. Dừng để cập nhật mới...")
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except Exception:
                        p.kill()
        except Exception as e:
            print(f"[!] Lỗi kiểm tra supervisor cũ: {e}")
    
    SUPERVISOR_PID_FILE.write_text(str(my_pid))

def update_supervisor_heartbeat():
    """Ghi nhịp tim của Supervisor định kỳ."""
    try:
        data = {
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "child_pid": current_child_proc.pid if current_child_proc and current_child_proc.poll() is None else None
        }
        SUPERVISOR_HEARTBEAT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def is_child_heartbeat_healthy(max_silence_seconds=150) -> bool:
    """Kiểm tra xem telegram_bot có bị treo (deadlock / socket freeze) hay không."""
    if not HEARTBEAT_FILE.exists():
        # Chưa có file thì cho phép bot mới khởi động
        return True
    try:
        content = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        hb_ts = float(content.get("timestamp", 0))
        silence = time.time() - hb_ts
        if silence > max_silence_seconds:
            return False
        return True
    except Exception:
        return True

def rotate_log_if_needed(max_size_mb=25):
    """Tránh file bot.log phình to quá giới hạn."""
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > max_size_mb * 1024 * 1024:
            bak_file = LOGS_DIR / "bot_old.log"
            if bak_file.exists():
                bak_file.unlink(missing_ok=True)
            LOG_FILE.rename(bak_file)
    except Exception:
        pass

def main():
    global current_child_proc
    print(f"[*] Starting TikTok Telegram Bot 24/7 Supervisor (PID: {os.getpid()})")
    print(f"[*] Logs: {LOG_FILE}")
    ensure_single_supervisor()

    crash_timestamps = []

    while True:
        rotate_log_if_needed()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] --- [Supervisor] Khoi dong Telegram Bot (24/7 Auto-Heal) ---\n")
            f.flush()

        try:
            # Khởi động child process không blocking
            log_out = open(LOG_FILE, "a", encoding="utf-8")
            current_child_proc = subprocess.Popen(
                [sys.executable, "-u", "telegram_bot.py"],
                cwd=str(BACKEND_DIR),
                stdout=log_out,
                stderr=subprocess.STDOUT
            )
            start_proc_time = time.time()

            # Giám sát nhịp tim và trạng thái của child process
            while current_child_proc.poll() is None:
                time.sleep(5)
                update_supervisor_heartbeat()

                # Kiểm tra treo: nếu bot chạy hơn 60s nhưng không cập nhật heartbeat > 150s
                proc_running_time = time.time() - start_proc_time
                if proc_running_time > 60:
                    if not is_child_heartbeat_healthy(max_silence_seconds=150):
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        with open(LOG_FILE, "a", encoding="utf-8") as f:
                            f.write(f"\n[{ts}] [Supervisor CẢNH BÁO] Phát hiện telegram_bot bị treo/mất nhịp tim > 150s! Đang cưỡng chế khởi động lại...\n")
                            f.flush()
                        try:
                            current_child_proc.terminate()
                            current_child_proc.wait(timeout=5)
                        except Exception:
                            try:
                                current_child_proc.kill()
                            except Exception:
                                pass
                        break

            log_out.close()

        except Exception as e:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [Supervisor] Lỗi khởi chạy tiến trình con: {e}\n")
                f.flush()

        # Xử lý crash loop bảo vệ hệ thống
        now = time.time()
        crash_timestamps.append(now)
        crash_timestamps = [t for t in crash_timestamps if now - t < 60]

        wait_seconds = 3
        if len(crash_timestamps) >= 5:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [Supervisor] Cảnh báo crash lặp lại 5 lần/phút. Tạm dừng 15s để ổn định hệ thống...\n")
                f.flush()
            wait_seconds = 15

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [Supervisor] Bot đã dừng (exitcode: {current_child_proc.returncode if current_child_proc else 'N/A'}). Tự động bật lại sau {wait_seconds}s...\n")
            f.flush()

        time.sleep(wait_seconds)

if __name__ == "__main__":
    main()
