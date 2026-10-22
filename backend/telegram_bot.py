import sys
import os
import re
import time
import requests
import json
import shutil
import threading
import psutil
import html
from typing import Any, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

# Load environment
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = str(BASE_DIR.parent)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Auto resolve venv site-packages for gspread, yt_dlp, oauth2client (as fallback only)
for venv_path in [r"D:/02_CONG_CU/youtube-reup-pipeline\venv\Lib\site-packages", r"D:/02_CONG_CU/DUONG_DAN_CU/03_youtube\youtube_reup_pipeline\venv\Lib\site-packages"]:
    if Path(venv_path).exists() and venv_path not in sys.path:
        sys.path.append(venv_path)

load_dotenv(dotenv_path=BASE_DIR / ".env")

import downloader
import sub_processor
import video_merger
import channel_manager
import pitch_voice_selector
import movie_voice_matcher
import wuby_preflight
import sheet_queue_manager
import drive_link_manager
import render_storage
from telegram_control import control_chat_id

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROUP_ID = str(os.getenv("TELEGRAM_GROUP_ID", "-1004439918026,-5579042871")).strip()
GOOGLE_DRIVE_DIR = Path(os.getenv("GOOGLE_DRIVE_DIR", "G:/My Drive/Video titok Trinh"))
WORKSPACE_DIR = BASE_DIR.parent / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
START_TIME = time.time()

def update_heartbeat(status="running", extra=None):
    """Ghi file nhịp tim định kỳ để supervisor/watchdog nhận biết bot đang online 24/7."""
    try:
        hb_file = BASE_DIR.parent / "logs" / "bot_heartbeat.json"
        hb_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "status": status,
            "uptime_seconds": int(time.time() - START_TIME),
            "extra": extra or {}
        }
        hb_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def ensure_single_instance():
    """Đảm bảo duy nhất 1 tiến trình telegram_bot chạy cùng lúc để triệt tiêu lỗi Telegram 409 Conflict."""
    lock_file = BASE_DIR / "bot.pid"
    current_pid = os.getpid()

    # 1. Đọc PID cũ từ bot.pid nếu còn tồn tại
    if lock_file.exists():
        try:
            old_pid = int(lock_file.read_text().strip())
            if old_pid != current_pid and psutil.pid_exists(old_pid):
                p = psutil.Process(old_pid)
                cmd = " ".join(p.cmdline() or [])
                if "telegram_bot.py" in cmd:
                    print(f"[Bot] Dừng tiến trình telegram_bot cũ từ PID file ({old_pid})...")
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except Exception:
                        p.kill()
        except Exception as e:
            print(f"[Bot] Cảnh báo kiểm tra PID cũ: {e}")

    # 2. Quét toàn bộ tiến trình python trong hệ thống thuộc telegram_bot
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
        try:
            pid = proc.info['pid']
            if pid == current_pid:
                continue
            name = (proc.info['name'] or "").lower()
            if 'python' not in name:
                continue
            cmdline = " ".join(proc.info['cmdline'] or [])
            if "telegram_bot.py" in cmdline:
                print(f"[Bot] Phát hiện và dừng tiến trình bot cũ PID {pid}...")
                p = psutil.Process(pid)
                p.terminate()
                try:
                    p.wait(timeout=3)
                except Exception:
                    p.kill()
        except Exception:
            pass

    lock_file.write_text(str(current_pid))

# Dynamic set of allowed chat IDs
ALLOWED_CHAT_IDS = set()
for gid in GROUP_ID.split(","):
    clean = gid.strip()
    if clean:
        ALLOWED_CHAT_IDS.add(clean)

def is_allowed_chat(chat_id) -> bool:
    """Checks if message is from the configured group or matches group ID."""
    if not ALLOWED_CHAT_IDS:
        return True
    chat_str = str(chat_id)
    if chat_str in ALLOWED_CHAT_IDS:
        return True
    # Strip supergroup -100 prefix for flexible matching
    clean_chat = chat_str.replace("-100", "").replace("-", "")
    for gid in ALLOWED_CHAT_IDS:
        clean_g = gid.replace("-100", "").replace("-", "")
        if clean_g and clean_g == clean_chat:
            return True
    return False

def add_allowed_chat(chat_id):
    ALLOWED_CHAT_IDS.add(str(chat_id))

_last_edit_times = {}

def send_message(chat_id, text, reply_to_message_id=None, message_thread_id=None, reply_markup=None):
    """Sends text message to Telegram chat with auto supergroup migration retry, HTML parse fallback, and rate limit handling."""
    try:
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        if reply_markup:
            data["reply_markup"] = reply_markup

        res = requests.post(f"{API_BASE}/sendMessage", json=data, timeout=20)
        res_data = res.json()
        if not res_data.get("ok"):
            desc = res_data.get("description", "")
            # Rate limited 429
            if res_data.get("error_code") == 429:
                retry_after = res_data.get("parameters", {}).get("retry_after", 3)
                print(f"[Bot] Rate limit 429 on sendMessage, waiting {retry_after}s...")
                time.sleep(min(retry_after, 5))
                res = requests.post(f"{API_BASE}/sendMessage", json=data, timeout=20)
                res_data = res.json()

            # HTML entity parse error or message too long fallback
            if "can't parse entities" in desc.lower() or "bad request" in desc.lower():
                data["text"] = text[:4000]
                data.pop("parse_mode", None)
                res = requests.post(f"{API_BASE}/sendMessage", json=data, timeout=20)
                res_data = res.json()

            migrate_to = res_data.get("parameters", {}).get("migrate_to_chat_id")
            if migrate_to:
                print(f"[Bot] Nhóm đã nâng cấp lên supergroup: {migrate_to}. Đang thử lại...")
                add_allowed_chat(migrate_to)
                data["chat_id"] = migrate_to
                res = requests.post(f"{API_BASE}/sendMessage", json=data, timeout=20)
                return res.json()
        return res_data
    except Exception as e:
        print(f"[Bot] Error sending message: {e}")
        return None

def _send_media(chat_id, path, kind, caption=None, reply_to_message_id=None,
                message_thread_id=None, reply_markup=None):
    """Upload media; photos retry once without HTML when the caption is invalid."""
    try:
        if kind != "photo" and not os.path.exists(path):
            return None
        if kind == "video" and os.path.getsize(path) >= 49 * 1024 * 1024:
            return None
        data = {"chat_id": chat_id}
        if caption or kind == "photo":
            data.update(caption=caption, parse_mode="HTML")
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup) if isinstance(reply_markup, dict) else reply_markup

        timeout = {"photo": 45, "video": 180, "document": 60}[kind]
        for attempt in range(2):
            with open(path, "rb") as media:
                res = requests.post(f"{API_BASE}/send{kind.title()}", data=data,
                                    files={kind: media}, timeout=timeout)
            if kind != "photo":
                return None
            result = res.json()
            if attempt or result.get("ok") or "can't parse entities" not in result.get("description", "").lower():
                return result
            data.pop("parse_mode", None)
    except Exception as e:
        print(f"[Bot] Error sending {kind}: {e}")
        return None


def send_photo(chat_id, photo_path, caption="", reply_to_message_id=None, message_thread_id=None, reply_markup=None):
    return _send_media(chat_id, photo_path, "photo", caption, reply_to_message_id,
                       message_thread_id, reply_markup)

def edit_message(chat_id, message_id, text, reply_markup=None, force=False):
    """Edits an existing Telegram message with debouncing for progress updates and HTML parse fallback."""
    key = (str(chat_id), str(message_id))
    now = time.time()
    last_time = _last_edit_times.get(key, 0)
    
    # Debounce: if not force and edited less than 1.5s ago, skip progress update to prevent 429
    if not force and (now - last_time) < 1.5:
        return None
    _last_edit_times[key] = now

    try:
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        res = requests.post(f"{API_BASE}/editMessageText", json=data, timeout=20)
        res_json = res.json()
        if not res_json.get("ok"):
            desc = res_json.get("description", "")
            # Telegram: message is not modified is completely normal, ignore
            if "message is not modified" in desc.lower():
                return res_json
            # 429 Too Many Requests
            if res_json.get("error_code") == 429:
                retry_after = res_json.get("parameters", {}).get("retry_after", 3)
                _last_edit_times[key] = now + retry_after
                if force:
                    time.sleep(min(retry_after, 4))
                    res = requests.post(f"{API_BASE}/editMessageText", json=data, timeout=20)
                    return res.json()
                return res_json
            if "can't parse entities" in desc.lower() or "message is too long" in desc.lower():
                data["text"] = text[:3800]
                data.pop("parse_mode", None)
                res = requests.post(f"{API_BASE}/editMessageText", json=data, timeout=20)
                res_json = res.json()
        return res_json
    except Exception as e:
        print(f"[Bot] Error editing message: {e}")
        return None

def answer_callback_query(callback_query_id, text=None):
    """Acknowledges an incoming callback query from inline button tap."""
    try:
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        requests.post(f"{API_BASE}/answerCallbackQuery", json=data, timeout=10)
    except Exception as e:
        print(f"[Bot] Error answering callback query: {e}")

def send_video(chat_id, video_path, caption=None, reply_to_message_id=None, message_thread_id=None):
    """Sends video file to Telegram chat (if < 50MB)."""
    _send_media(chat_id, video_path, "video", caption, reply_to_message_id, message_thread_id)

def send_document(chat_id, doc_path, caption=None, reply_to_message_id=None, message_thread_id=None):
    """Sends document file (e.g. .srt) to Telegram chat."""
    _send_media(chat_id, doc_path, "document", caption, reply_to_message_id, message_thread_id)

# Set tracking active processing files to prevent race conditions
CURRENTLY_PROCESSING = set()
PENDING_JOBS = {}
PENDING_INTRO_JOBS = {}
WAITING_CUSTOM_TITLE = {}

def handle_video_download(
    chat_id, message_id, text, message_thread_id=None, status_msg_id=None,
    override_workflow=None, override_voice=None, job_id=None, sheet_row=None,
    logo_choice=None, intro_action=None, intro_title=None, trim_start_sec=None,
    intro_banner_png=None, intro_banner_box=None, intro_sticker_box=None
):
    """Processes video download, mutes audio, blurs Chinese sub, burns Vietnamese sub, and saves to Drive."""
    url = downloader.extract_url(text)
    if not url:
        return

    item_id, resolved = downloader.extract_item_id(url)
    video_id_str = item_id if item_id else str(int(time.time()))
    video_file_name = f"{video_id_str}.mp4"
    
    # Chặn ngay lập tức nếu video đang được xử lý ở luồng khác
    if video_file_name in CURRENTLY_PROCESSING:
        print(f"[Bot] Video {video_file_name} đang được xử lý, bỏ qua yêu cầu trùng lặp.")
        return
    CURRENTLY_PROCESSING.add(video_file_name)
    
    # 0. Lấy cấu hình kênh tương ứng cho nhóm hoặc hashtag chỉ định
    ch_key, ch_cfg = channel_manager.get_channel_config(chat_id, text=text)

    ch_cfg = channel_manager.apply_job_preset(ch_cfg, override_workflow, logo_choice)

    channel_name = ch_cfg.get("name", ch_key)
    tts_enabled = bool(ch_cfg.get("tts_enabled", True))
    voice = ch_cfg.get("voice", "wuby_clone" if ch_cfg.get("workflow") == "wuby" else "nu_tre") if tts_enabled else None
    speed = float(ch_cfg.get("speed", 1.0 if ch_cfg.get("workflow") == "wuby" else 1.7))
    mask_mode = ch_cfg.get("mask_mode", "in_video_overlay" if ch_cfg.get("workflow") == "wuby" else "blur_sub_black")
    burn_sub = bool(ch_cfg.get("burn_sub", True))
    show_title_card = bool(ch_cfg.get("show_title_card", False if ch_cfg.get("workflow") in ["wuby", "movie_clone", "gaidep_cauca"] else True))
    bg_volume_val = float(ch_cfg.get("bg_volume", 1.0 if not tts_enabled else (0.40 if ch_cfg.get("workflow") == "wuby" else 0.10)))
    drive_folder = str(ch_cfg.get("drive_folder", "KENH_006_TieuWuby/02_MOI_RENDER_CHO_XAC_NHAN" if ch_cfg.get("workflow") == "wuby" else "KENH_005_VuTruCayPhim/02_MOI_RENDER_CHO_XAC_NHAN"))

    if not tts_enabled:
        voice_label = "Âm thanh gốc (không thuyết minh)"
    else:
        voice_label = channel_manager.get_supported_voices().get(voice, voice or "Không rõ")
    mask_label = "Đè sub hoạt hình (xóa chữ in-place)" if mask_mode == "in_video_overlay" else channel_manager.SUPPORTED_MASKS.get(mask_mode, mask_mode)

    # 1. Send / Reuse status message
    sent_msg_id = status_msg_id
    if not tts_enabled:
        status_text = (
            f"⏳ <b>Đang tải video...</b>\n"
            f"📺 Kênh: <b>{channel_name}</b>\n"
            f"🎙 Âm thanh: <code>Giữ nguyên 100% âm gốc</code> | 🔲 Che: <code>{mask_label}</code>\n"
            f"Đang kết nối TikHub bóc tách luồng HD không logo..."
        )
    else:
        status_text = (
            f"⏳ <b>Đang tải video...</b>\n"
            f"📺 Kênh: <b>{channel_name}</b>\n"
            f"🎙 Giọng: <code>{voice_label} ({speed}x)</code> | 🔲 Che: <code>{mask_label}</code>\n"
            f"Đang kết nối TikHub bóc tách luồng HD không logo..."
        )
    if not sent_msg_id:
        status_msg = send_message(
            chat_id=chat_id,
            text=status_text,
            reply_to_message_id=message_id,
            message_thread_id=message_thread_id
        )
        sent_msg_id = status_msg.get("result", {}).get("message_id") if status_msg else None
    else:
        edit_message(chat_id, sent_msg_id, status_text)

    raw_file = WORKSPACE_DIR / f"{video_id_str}_raw.mp4"
    srt_file = WORKSPACE_DIR / f"{video_id_str}_vi.srt"
    processed_file = WORKSPACE_DIR / f"{video_id_str}_vi.mp4"

    try:
        target_drive_dir = render_storage.review_directory(GOOGLE_DRIVE_DIR, drive_folder)
        # 2. Download via downloader
        downloaded, raw_title = downloader.download_video_with_title(url, str(raw_file))
        
        if not downloaded or not os.path.exists(downloaded):
            if sent_msg_id:
                edit_message(chat_id, sent_msg_id, "❌ <b>Lỗi:</b> Không thể tải được luồng video từ liên kết này.")
            if job_id or sheet_row:
                sheet_queue_manager.update_job_status(job_id=job_id, row_idx=sheet_row, status="🔴 Lỗi tải video", progress="ERROR")
            return

        # Cập nhật Google Sheet: đã tải video về
        if job_id or sheet_row:
            sheet_queue_manager.update_job_status(
                job_id=job_id,
                row_idx=sheet_row,
                downloaded_file=Path(downloaded).name,
                status="🎙 Đang tách thoại & Lồng tiếng AI",
                progress="40%"
            )

        # Lưu bản video gốc chưa render ra ngoài thư mục gốc Google Drive
        # CURRENTLY_PROCESSING prevents duplicate work until delivery succeeds.
        try:
            if not GOOGLE_DRIVE_DIR.exists():
                GOOGLE_DRIVE_DIR.mkdir(parents=True, exist_ok=True)
            raw_drive_path = GOOGLE_DRIVE_DIR / video_file_name
            if not render_storage.managed_channel_roots(GOOGLE_DRIVE_DIR) and not raw_drive_path.exists():
                shutil.copy2(downloaded, raw_drive_path)
                print(f"[Bot] Đã lưu video chưa render ở ngoài thư mục Drive: {raw_drive_path}")
        except Exception as raw_e:
            print(f"[Bot] Lưu video chưa render ra ngoài Drive cảnh báo: {raw_e}")

        # 3. Transcribe with Whisper GPU & Translate with DeepSeek (chỉ chạy khi cần thuyết minh hoặc burn sub)
        if tts_enabled or burn_sub:
            if sent_msg_id:
                edit_message(chat_id, sent_msg_id, "⏳ <b>[Bước 1/3] Đang bóc tách phụ đề gốc (Whisper GPU)...</b>\nĐang nhận diện từng câu thoại từ video...")
                
            def sub_progress(stage, extra=None):
                if sent_msg_id:
                    if stage == "extract_audio":
                        edit_message(chat_id, sent_msg_id, "⏳ <b>[Bước 1/3] Đang trích xuất âm thanh từ video...</b>")
                    elif stage == "transcribing":
                        edit_message(chat_id, sent_msg_id, "⏳ <b>[Bước 1/3] Đang bóc tách phụ đề gốc (Whisper GPU)...</b>")
                    elif stage == "translating":
                        progress_info = f" ({extra})" if extra else ""
                        edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 2/3] Đang dịch phụ đề sang tiếng Việt (DeepSeek AI){progress_info}...</b>\nDịch tự nhiên, chính xác theo từng câu thoại...")
                    elif stage == "tts_dubbing":
                        edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 3/3] Đang tạo giọng lồng tiếng ({extra} câu)...</b>\nĐang khớp giọng đọc chuẩn xác theo từng câu...")

            try:
                srt_path, vi_segments = sub_processor.generate_vietnamese_subtitles(
                    video_path=downloaded,
                    output_srt_path=str(srt_file),
                    progress_callback=sub_progress,
                    dubbing_speed=ch_cfg.get('speed') if ch_cfg.get('synthesis_speed') else None
                )
            except RuntimeError as sub_err:
                if any(k in str(sub_err).lower() for k in ["no_speech_detected", "không có lời thoại", "trống hoặc không tồn tại"]):
                    print(f"[Bot] Video không có lời thoại (chỉ có nhạc nền/âm thanh): {sub_err}")
                    srt_path, vi_segments = str(srt_file), []
                else:
                    raise
        else:
            srt_path, vi_segments = str(srt_file), []
            if sent_msg_id:
                edit_message(chat_id, sent_msg_id, "⏳ <b>[Bước 1/2] Đang phân tích vị trí chữ để che...</b>\nGiữ nguyên 100% âm thanh gốc, không thuyết minh AI.")

        # 4. Đặt tên phim tiếng Việt và tạo tên file không dấu cách nhau dấu _
        movie_title_vi, movie_slug = sub_processor.generate_movie_title(
            raw_title=raw_title or "",
            segments=vi_segments
        )
        if not movie_slug:
            movie_slug = f"video_{video_id_str}"
        from render_review_policy import review_filename
        final_filename = review_filename(movie_title_vi, video_id_str if re.fullmatch(r'\d{10,24}',video_id_str) else None)
        final_srt_name = Path(final_filename).with_suffix('.srt').name

        # 5A. Wuby preflight: phân tích KHUNG HÌNH + scene + OCR + giọng trước khi TTS/render.
        # Kết quả được tái sử dụng ở renderer, vì vậy OCR không cần quét lại lần hai.
        wuby_assignments = None
        wuby_profile_map = {}
        wuby_duration_match = {}
        wuby_preflight_cfg = ch_cfg.get("wuby_preflight") if isinstance(ch_cfg.get("wuby_preflight"), dict) else {}
        if ch_cfg.get("workflow") == "wuby" and wuby_preflight_cfg.get("enabled", True):
            try:
                if sent_msg_id:
                    edit_message(
                        chat_id, sent_msg_id,
                        "🔎 <b>[Wuby Preflight] Đang phân tích video trước render...</b>\n"
                        "🎞 Đo khung hình/FPS/chuyển động/scene + OCR + Character ID; Light-ASD chỉ kiểm tra đoạn mơ hồ..."
                    )
                orig_srt = Path(srt_path).with_suffix(".orig.srt")
                orig_segments = sub_processor.parse_srt_to_segments(str(orig_srt)) if orig_srt.exists() else []
                cfg_data = channel_manager.load_channels_config()
                wuby_report_path = WORKSPACE_DIR / f"{video_id_str}_wuby_preflight.json"
                wuby_report = wuby_preflight.analyze_wuby_preflight(
                    video_path=downloaded,
                    source_segments=orig_segments,
                    target_segments=vi_segments,
                    srt_path=str(srt_file) if os.path.exists(srt_file) else None,
                    movie_title=movie_title_vi,
                    config_data=cfg_data,
                    cfg=wuby_preflight_cfg,
                    report_path=str(wuby_report_path),
                )
                plan = wuby_report.get("render_plan") or {}
                ocr_data = wuby_report.get("ocr") or {}
                ch_cfg["_wuby_preflight"] = {
                    "ocr_events": ocr_data.get("events") or [],
                    "scene_ranges": (wuby_report.get("scenes") or {}).get("ranges") or [],
                    "render_plan": plan,
                    "ocr_matched": True,
                    "report_path": str(wuby_report_path),
                }
                ch_cfg["ocr_fps"] = float(plan.get("ocr_sample_fps") or ch_cfg.get("ocr_fps", 24.0))

                # Hybrid frame chỉ an toàn với portrait/square. Landscape giữ nguyên khung gốc.
                if not bool(plan.get("hybrid_frame_allowed", True)):
                    ch_cfg.setdefault("wuby_studio", {}).setdefault("hybrid_frame", {})["enabled"] = False

                voice_match = (wuby_report.get("voice") or {}).get("match") or {}
                wuby_assignments = voice_match.get("target_assignments") or None
                if wuby_assignments:
                    unique_profiles = sorted({str(a.get("profile")) for a in wuby_assignments if a.get("profile")})
                    for key in unique_profiles:
                        wuby_profile_map[key] = channel_manager._resolve_voice_profile(key, cfg_data, ch_cfg)
                    wuby_duration_match = (wuby_preflight_cfg.get("voice_match") or {}).get("duration_match") or {}
                    voice_label = f"Wuby Character ID ({len(unique_profiles)} giọng khóa)"

                visual = wuby_report.get("visual") or {}
                ocr_summary = ocr_data.get("summary") or {}
                voice_summary = (wuby_report.get("voice") or {}).get("summary") or {}
                if sent_msg_id:
                    edit_message(
                        chat_id, sent_msg_id,
                        f"✅ <b>Wuby Preflight xong.</b>\n"
                        f"🎞 {visual.get('width')}×{visual.get('height')} @ {visual.get('fps')}fps | "
                        f"{visual.get('orientation')} | motion: <b>{visual.get('motion_class')}</b>\n"
                        f"🧩 Scene: <b>{(wuby_report.get('scenes') or {}).get('count', 0)}</b> | "
                        f"OCR track: <b>{ocr_summary.get('track_count', 0)}</b> | "
                        f"khớp sub: <b>{float(ocr_summary.get('segment_coverage', 0))*100:.1f}%</b>\n"
                        f"🧑 Character: <b>{voice_summary.get('character_count', 0)}</b> | "
                        f"giọng khóa: <b>{voice_summary.get('unique_voice_count', 0)}</b> | "
                        f"ASD verify: <b>{voice_summary.get('light_asd_verified', 0)}</b>\n"
                        "Đang dựng voice track theo kế hoạch đã đo..."
                    )
            except Exception as wuby_pf_err:
                # Fail-soft: giữ pipeline Wuby cũ nếu preflight thiếu model/OCR hoặc gặp clip dị thường.
                print(f"[WubyPreflight] Cảnh báo, fallback pipeline Wuby cũ: {wuby_pf_err}")
                wuby_assignments = None
                wuby_profile_map = {}
                ch_cfg.pop("_wuby_preflight", None)

        # 5B. Phân tích giọng Clone phim sau Whisper.
        # Cấu hình 2 mới: khóa Character ID trước; F0 không còn quyết định ai đang nói.
        movie_match_cfg = ch_cfg.get("movie_voice_match") if isinstance(ch_cfg.get("movie_voice_match"), dict) else {}
        movie_assignments = None
        movie_profile_map = {}
        if vi_segments and movie_match_cfg.get("enabled", False):
            try:
                if sent_msg_id:
                    edit_message(
                        chat_id, sent_msg_id,
                        "🎬 <b>[Phân tích phim] Whisper đã tách câu.</b>\n"
                        "🧑 Đang khóa Character ID bằng speaker diarization; Light-ASD chỉ chạy đoạn mơ hồ..."
                    )
                orig_srt = Path(srt_path).with_suffix(".orig.srt")
                orig_segments = sub_processor.parse_srt_to_segments(str(orig_srt))
                if not orig_segments:
                    raise RuntimeError(f"MOVIE_ORIGINAL_SRT_EMPTY:{orig_srt}")
                cfg_data = channel_manager.load_channels_config()
                movie_report_path = WORKSPACE_DIR / f"{video_id_str}_movie_voice_match.json"
                movie_match = movie_voice_matcher.match_whisper_segments(
                    video_path=downloaded,
                    source_segments=orig_segments,
                    target_segments=vi_segments,
                    config_data=cfg_data,
                    cfg=movie_match_cfg,
                    report_path=str(movie_report_path),
                )
                movie_assignments = movie_match.get("target_assignments") or []
                unique_profiles = sorted({str(a.get("profile")) for a in movie_assignments if a.get("profile")})
                for key in unique_profiles:
                    movie_profile_map[key] = channel_manager._resolve_voice_profile(key, cfg_data, ch_cfg)
                voice_label = f"Character ID đa giọng ({len(unique_profiles)} giọng khóa)"
                stats = movie_match.get("stats") or {}
                coverage = float(stats.get("f0_coverage", 0.0)) * 100.0
                print(f"[MovieVoiceMatch] {len(orig_segments)} Whisper segments -> {len(unique_profiles)} locked voices; Character ID backend={stats.get('identity_backend')}")
                if sent_msg_id:
                    edit_message(
                        chat_id, sent_msg_id,
                        f"✅ <b>Đã phân tích {len(orig_segments)} đoạn Whisper.</b>\n"
                        f"🧑 Character: <b>{stats.get('character_count', 0)}</b> | 🎙 Giọng khóa: <b>{len(unique_profiles)}</b>\n"
                        f"🔎 Backend: <code>{stats.get('identity_backend') or 'fallback'}</code> | "
                        f"ASD verify: <b>{((stats.get('light_asd') or {}).get('verified', 0))}</b>\n"
                        "Đang tạo từng câu thoại Việt theo Character ID..."
                    )
            except Exception as movie_match_err:
                # Fail-soft về một giọng fallback để job không chết chỉ vì một đoạn quá ngắn/noisy.
                print(f"[MovieVoiceMatch] Lỗi phân tích đa giọng, dùng fallback: {movie_match_err}")
                movie_assignments = None
                fallback_voice = str(movie_match_cfg.get("fallback_voice") or voice or "omni_nam_review")
                voice = fallback_voice
                ch_cfg["voice"] = fallback_voice
                cfg_data = channel_manager.load_channels_config()
                ch_cfg["_voice_profile"] = channel_manager._resolve_voice_profile(fallback_voice, cfg_data, ch_cfg)
                voice_label = channel_manager.get_supported_voices().get(fallback_voice, fallback_voice)

        # Legacy single-F0 path is kept for non-movie presets only.
        pitch_cfg = ch_cfg.get("pitch_match") if isinstance(ch_cfg.get("pitch_match"), dict) else {}
        if vi_segments and not movie_assignments and not wuby_assignments and pitch_cfg.get("enabled", False):
            try:
                bank = pitch_cfg.get("voice_bank") or []
                pitch_report_path = WORKSPACE_DIR / f"{video_id_str}_pitch_match.json"
                cfg_for_selector = dict(pitch_cfg)
                cfg_for_selector["report_path"] = str(pitch_report_path)
                match = pitch_voice_selector.select_voice_by_pitch(
                    video_path=downloaded,
                    voice_bank=bank,
                    segments=vi_segments,
                    cfg=cfg_for_selector,
                )
                selected_voice = str(match["selected"]["profile"])
                cfg_data = channel_manager.load_channels_config()
                voice = selected_voice
                ch_cfg["voice"] = selected_voice
                ch_cfg["_voice_profile"] = channel_manager._resolve_voice_profile(selected_voice, cfg_data, ch_cfg)
                voice_label = channel_manager.get_supported_voices().get(selected_voice, selected_voice)
                src_f0 = match["source"]["median_f0_hz"]
                ref_f0 = match["selected"]["reference_hz"]
                print(f"[PitchMatch] F0 gốc ~{src_f0} Hz -> {selected_voice} (~{ref_f0} Hz)")
            except Exception as pitch_err:
                fallback_voice = str(pitch_cfg.get("fallback_voice") or voice)
                print(f"[PitchMatch] Không đo/chọn được giọng, dùng fallback {fallback_voice}: {pitch_err}")
                voice = fallback_voice
                ch_cfg["voice"] = fallback_voice
                cfg_data = channel_manager.load_channels_config()
                ch_cfg["_voice_profile"] = channel_manager._resolve_voice_profile(fallback_voice, cfg_data, ch_cfg)
                voice_label = channel_manager.get_supported_voices().get(fallback_voice, fallback_voice)

        # 6. Dựng voice track sau khi việc phân tích/matching đã xong.
        voice_file = WORKSPACE_DIR / f"{video_id_str}_voice.wav"
        if vi_segments and tts_enabled:
            if sent_msg_id:
                edit_message(chat_id, sent_msg_id, f"⏳ <b>Đang dựng voice track ({voice_label}, tốc độ {speed}x)...</b>\nKhớp từng câu vào đúng timeline Whisper...")
            try:
                video_dur = video_merger.get_video_duration(downloaded)
                active_assignments = wuby_assignments or movie_assignments
                active_profile_map = wuby_profile_map if wuby_assignments else movie_profile_map
                active_duration_match = wuby_duration_match if wuby_assignments else (movie_match_cfg.get("duration_match") or {})
                if active_assignments:
                    sub_processor.generate_dubbed_audio_multivoice(
                        segments=vi_segments,
                        assignments=active_assignments,
                        output_audio_path=str(voice_file),
                        profile_map=active_profile_map,
                        speed=speed,
                        total_duration_sec=video_dur if video_dur > 0 else None,
                        duration_match=active_duration_match,
                        progress_callback=sub_progress,
                    )
                    from render_review_policy import validate_voice_assignments
                    validate_voice_assignments(active_assignments, json.loads(
                        voice_file.with_suffix('.multivoice.json').read_text(encoding='utf-8')))
                else:
                    sub_processor.generate_dubbed_audio(
                        segments=vi_segments,
                        output_audio_path=str(voice_file),
                        voice=voice,
                        speed=speed,
                        total_duration_sec=video_dur if video_dur > 0 else None,
                        voice_profile=ch_cfg.get("_voice_profile"),
                        progress_callback=sub_progress
                    )
            except Exception as voice_err:
                print(f"[Bot] Lỗi tạo voice audio: {voice_err}")
                if ch_cfg.get("_voice_profile", {}).get("require_clone") and not (wuby_assignments or movie_assignments):
                    if sent_msg_id:
                        edit_message(
                            chat_id,
                            sent_msg_id,
                            f"❌ <b>Lỗi Voice Clone Wuby:</b>\n<code>{voice_err}</code>\n\n<i>Cấu hình yêu cầu bắt buộc clone nên hệ thống dừng.</i>"
                        )
                # Never continue with a stale voice file after a failed clone.
                raise
        # 6B. Check trước mỗi video đối với Cấu hình 4 Chị Đẹp Đi Câu (Pre-render Preview)
        if ch_cfg.get("require_intro_preview") and intro_action is None:
            try:
                import intro_banner_service
                preview_img = WORKSPACE_DIR / f"{video_id_str}_prerender_preview.jpg"

                suggested_title = intro_title or movie_title_vi or "SĂN CÁ KHỦNG CÙNG CHỊ ĐẸP"
                if re.search(r'[\u4e00-\u9fff]', str(suggested_title)):
                    suggested_title = "SĂN CÁ KHỦNG CÙNG CHỊ ĐẸP"

                preview_data = intro_banner_service.generate_prerender_preview(
                    video_path=downloaded,
                    title_text=suggested_title,
                    brand_text="CHỊ ĐẸP ĐI CÂU",
                    out_preview_path=str(preview_img)
                )

                preview_token = f"intro_{video_id_str[:12]}"
                PENDING_INTRO_JOBS[preview_token] = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "message_thread_id": message_thread_id,
                    "text": text,
                    "downloaded": downloaded,
                    "raw_title": raw_title,
                    "suggested_title": suggested_title,
                    "override_workflow": override_workflow,
                    "override_voice": override_voice,
                    "job_id": job_id,
                    "sheet_row": sheet_row,
                    "logo_choice": logo_choice,
                    "status_msg_id": sent_msg_id,
                    "banner_png": preview_data["banner_png"],
                    "banner_box": preview_data.get("banner_box"),
                    "sticker_box": preview_data.get("sticker_box"),
                    "cut_ts": preview_data["cut_ts"],
                    "video_file_name": video_file_name
                }

                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ A. Dùng Banner Tiêu Đề", "callback_data": f"intro:banner:{preview_token}"},
                            {"text": "✂️ B. Làm Mờ Chữ Trung (Sạch)", "callback_data": f"intro:trim:{preview_token}"}
                        ],
                        [
                            {"text": "✏️ Đổi Tiêu Đề Khác", "callback_data": f"intro:edit:{preview_token}"},
                            {"text": "⏭ Render Thường (Bỏ qua)", "callback_data": f"intro:skip:{preview_token}"}
                        ]
                    ]
                }

                caption = (
                    f"🎬 <b>[XÁC NHẬN TRƯỚC KHI RENDER - {channel_name}]</b>\n\n"
                    f"📌 <b>Tiêu đề dự kiến:</b> <code>{suggested_title}</code>\n"
                    f"🔍 <i>Ảnh trên so sánh 2 phương án (A: Dùng Banner sang trọng che chữ Trung, B: Làm mờ sạch chữ Trung Quốc).</i>\n\n"
                    f"👉 <b>Vui lòng bấm chọn phương án bên dưới để bắt đầu Render:</b>"
                )

                send_photo(
                    chat_id=chat_id,
                    photo_path=str(preview_img),
                    caption=caption,
                    reply_to_message_id=message_id,
                    message_thread_id=message_thread_id,
                    reply_markup=keyboard
                )

                # Giải phóng lock để có thể resume khi user bấm nút
                CURRENTLY_PROCESSING.discard(video_file_name)
                return
            except Exception as preview_err:
                print(f"[Bot] Lỗi tạo ảnh xem trước pre-render: {preview_err}")

        # Cập nhật các tuỳ chọn intro vào ch_cfg trước khi render
        if intro_action:
            ch_cfg["intro_action"] = intro_action
        if intro_banner_png:
            ch_cfg["intro_banner_png"] = intro_banner_png
        if intro_banner_box:
            ch_cfg["intro_banner_box"] = intro_banner_box
        if intro_sticker_box:
            ch_cfg["intro_sticker_box"] = intro_sticker_box
        if trim_start_sec:
            ch_cfg["trim_start_sec"] = trim_start_sec

        # 7. Render video: che chữ + sub tiếng Việt (nếu có) + lồng tiếng (nếu có)
        if sent_msg_id:
            if not tts_enabled:
                edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 2/2] Đang làm mờ vùng chữ & xuất video...</b>\nChế độ che: <code>{mask_label}</code> | Giữ nguyên 100% âm thanh gốc...")
            else:
                edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 3/3] Đang ghép video & chèn tiêu đề ({movie_title_vi})...</b>\nChế độ che: <code>{mask_label}</code> | Đang xuất video chất lượng cao...")

        if job_id or sheet_row:
            sheet_queue_manager.update_job_status(
                job_id=job_id,
                row_idx=sheet_row,
                status="⚙️ Đang Render video & Subtitle",
                progress="75%"
            )

        video_merger.process_video_sub_and_mute(
            input_video=downloaded,
            output_video=str(processed_file),
            srt_path=str(srt_file) if (burn_sub and os.path.exists(srt_file)) else None,
            voice_audio=str(voice_file) if (tts_enabled and os.path.exists(voice_file)) else None,
            keep_bg_audio=ch_cfg.get("keep_bg_audio", True),
            bg_volume=bg_volume_val,
            blur_sub=(mask_mode in ["blur", "black_bar", "blur_sub_black"]),
            use_nvenc=True,
            segments=vi_segments,
            movie_title=movie_title_vi if (show_title_card or mask_mode == "in_video_overlay") else None,
            mask_mode=mask_mode,
            channel_cfg=ch_cfg
        )

        from wuby_studio.hybrid import frame_finished_wuby
        render_storage.require_rendered_video(processed_file)
        final_video = str(render_storage.require_rendered_video(
            frame_finished_wuby(processed_file, movie_title_vi, ch_cfg)
        ))
        file_size_mb = round(os.path.getsize(final_video) / (1024 * 1024), 2)
        
        # 7. Lưu file vào Google Drive theo thư mục cấu hình của kênh
        gd_saved = False
        gd_dest_path = ""
        gd_web_link = ""
        try:
            dest_video = render_storage.save_to_review(
                final_video, target_drive_dir, final_filename, srt_file
            )
            final_filename = dest_video.name
            final_srt_name = dest_video.with_suffix(".srt").name
                
            gd_saved = True
            mark_drive_file_processed(video_file_name)
            gd_dest_path = str(dest_video)
            print(f"[Bot] Đã lưu video hoàn thành vào thư mục Google Drive của kênh: {dest_video}")
            if render_storage.cloud_upload_enabled(GOOGLE_DRIVE_DIR):
                try:
                    gd_web_link = drive_link_manager.wait_for_link(dest_video, drive_folder, attempts=3)
                    print(f"[Bot] Link Google Drive: {gd_web_link}")
                except Exception as link_err:
                    print(f"[Bot] Chưa tạo được link Google Drive, dùng đường dẫn cục bộ: {link_err}")
            if job_id or sheet_row:
                sheet_queue_manager.update_job_status(
                    job_id=job_id,
                    row_idx=sheet_row,
                    status="🟢 Render thành công",
                    user_review="Đã render" if job_id in RERENDERING_JOBS else None,
                    progress="100%",
                    rendered_file=final_filename,
                    drive_path=gd_web_link or f"{drive_folder}/{final_filename}",
                    note=f"{file_size_mb} MB | Tốc độ {speed}x | {channel_name}"
                )
        except Exception as gd_e:
            raise RuntimeError(f"Không lưu được video vào thư mục chờ duyệt: {gd_e}") from gd_e

        # 8. Gửi thông báo hoàn thành lên Telegram
        is_cauca_job = (
            ch_cfg.get("workflow") in {"gaidep_cauca", "chidepdicau"}
            or "cauca" in str(ch_cfg.get("workflow", "")).lower()
            or "chidep" in str(ch_cfg.get("name", "")).lower()
        )
        caption_post = sub_processor.generate_movie_caption(
            movie_title=movie_title_vi,
            raw_title=raw_title or "",
            segments=vi_segments,
            workflow=ch_cfg.get("workflow", "wuby" if mask_mode == "in_video_overlay" else "film_review_black"),
            logo_type=ch_cfg.get("_logo_type")
        )

        from caption_handoff import save_caption
        save_caption(dest_video, caption_post)

        from upvideo_handoff import SHEET_URL
        upvideo_notice = ('\n📋 <b>UPVIDEO:</b> Đã chuyển sang hàng chờ đồng bộ Drive/Sheet. '
                          f'<a href="{SHEET_URL}">Mở bảng Đăng Facebook</a> '
                          '(Chưa đăng, chưa duyệt nội dung).')

        title_status = "Bật" if show_title_card else "Tắt"
        title_label = "TIÊU ĐỀ VIDEO" if is_cauca_job else "TÊN PHIM"
        main_header = "🎣 <b>RENDER VIDEO CÂU CÁ THÀNH CÔNG!</b> 🚀" if is_cauca_job else "✅ <b>XỬ LÝ VIDEO & LỒNG TIẾNG THÀNH CÔNG!</b> 🚀"
        audio_line = (
            "🎙 <b>Âm thanh:</b> Giữ 100% âm gốc & giọng nói tự nhiên\n"
            if not tts_enabled
            else f"🎙 <b>Lồng tiếng:</b> {voice_label} (Tốc độ {speed}x)\n"
        )
        success_text = (
            f"{main_header}\n\n"
            f"🎬 <b>{title_label}:</b> <code>{movie_title_vi}</code>\n"
            f"📁 <b>TÊN FILE:</b> <code>{final_filename}</code>\n"
            f"📊 <b>Dung lượng:</b> <code>{file_size_mb} MB</code>\n"
            f"📺 <b>Kênh áp dụng:</b> <b>{channel_name}</b>\n"
            f"{audio_line}"
            f"🎚 <b>Âm thanh:</b> {ch_cfg.get('audio_mode_label', 'Mặc định')}\n"
            f"🔲 <b>Che chữ:</b> {mask_label}\n"
            f"🎬 <b>Tiêu đề 6s:</b> {title_status}\n"
            f"📁 <b>Video chờ duyệt:</b> "
            + (f'<a href="{gd_web_link}">Mở video trên Drive</a>' if gd_web_link else f"<code>{html.escape(gd_dest_path)}</code>")
        )
        
        success_text += upvideo_notice
        if file_size_mb > 49:
            success_text += (
                f"\n\n⚠️ <i>Lưu ý: Video {file_size_mb} MB vượt giới hạn 50MB của Telegram "
                f"nên chỉ gửi đường dẫn thư mục chờ duyệt!</i>"
            )

        if sent_msg_id:
            edit_message(chat_id, sent_msg_id, success_text)
        else:
            send_message(chat_id, success_text, reply_to_message_id=message_id, message_thread_id=message_thread_id)

        # Gửi riêng tin nhắn chứa Caption bài đăng để người dùng chạm 1 lần là copy toàn bộ
        if caption_post:
            safe_caption = html.escape(caption_post)
            send_message(
                chat_id=chat_id,
                text=f"📋 <b>CAPTION BÀI ĐĂNG (Chạm vào khung dưới để copy):</b>\n\n<pre>{safe_caption}</pre>",
                reply_to_message_id=message_id,
                message_thread_id=message_thread_id
            )

        # 8. Send video and SRT to group (if < 50MB)
        if file_size_mb <= 49:
            send_video(
                chat_id=chat_id,
                video_path=final_video,
                caption=f"🎬 <b>{movie_title_vi}</b>\n📁 <code>{final_filename}</code> ({file_size_mb} MB)\n🎙 Lồng tiếng {voice_label} | 🇻🇳 Hardsub tiếng Việt",
                reply_to_message_id=message_id,
                message_thread_id=message_thread_id
            )
            if os.path.exists(srt_file):
                send_document(
                    chat_id=chat_id,
                    doc_path=str(srt_file),
                    caption=f"📄 Phụ đề tiếng Việt: <code>{final_srt_name}</code>",
                    reply_to_message_id=message_id,
                    message_thread_id=message_thread_id
                )

        control_chat = control_chat_id(ALLOWED_CHAT_IDS)
        if control_chat in ALLOWED_CHAT_IDS and str(chat_id) != control_chat:
            try:
                send_message(control_chat, f"🔔 <b>[Báo cáo từ kênh {channel_name}]</b>\n{success_text}")
            except Exception:
                pass

        # 9. Clean up temp files in workspace
        for p in [raw_file, srt_file, voice_file, processed_file, final_video]:
            try:
                if os.path.exists(p) and gd_saved:
                    os.remove(p)
            except Exception:
                pass

    except Exception as err:
        err_str = str(err)
        print(f"[Bot] Processing error: {err_str}")
        if job_id or sheet_row:
            sheet_queue_manager.update_job_status(
                job_id=job_id,
                row_idx=sheet_row,
                status="🔴 Thất bại",
                progress="ERROR",
                note=err_str[:150]
            )
        if sent_msg_id:
            short_err = err_str[:400] + "..." if len(err_str) > 400 else err_str
            edit_message(chat_id, sent_msg_id, f"❌ <b>Lỗi khi xử lý video:</b>\n<code>{html.escape(short_err)}</code>")
    finally:
        CURRENTLY_PROCESSING.discard(video_file_name)

PROCESSED_DRIVE_TRACKER = WORKSPACE_DIR / "drive_processed.txt"

def is_drive_file_processed(file_name: str) -> bool:
    key = render_storage.source_key(file_name, GOOGLE_DRIVE_DIR)
    if PROCESSED_DRIVE_TRACKER.exists():
        try:
            processed = {line.casefold() for line in PROCESSED_DRIVE_TRACKER.read_text(encoding='utf-8').splitlines()}
            return key in processed
        except Exception:
            pass
    return False

def mark_drive_file_processed(file_name: str):
    try:
        with open(PROCESSED_DRIVE_TRACKER, "a", encoding="utf-8") as f:
            f.write(f"{render_storage.source_key(file_name, GOOGLE_DRIVE_DIR)}\n")
    except Exception:
        pass

def process_local_drive_video(video_path: Path):
    """
    Processes an unrendered video placed directly in the Google Drive root folder.
    Rendered output is saved to the configured channel's review folder.
    """
    stem = video_path.stem
    processing_key = render_storage.source_key(video_path, GOOGLE_DRIVE_DIR)
    if processing_key in CURRENTLY_PROCESSING or is_drive_file_processed(video_path):
        return
    CURRENTLY_PROCESSING.add(processing_key)

    control_chat = control_chat_id(ALLOWED_CHAT_IDS)
    chat_id = control_chat if control_chat in ALLOWED_CHAT_IDS else (list(ALLOWED_CHAT_IDS)[0] if ALLOWED_CHAT_IDS else None)
    sent_msg_id = None
    
    # Lấy cấu hình kênh tương ứng (nếu video nằm trong thư mục KENH_xxx/01_CHUA_RENDER)
    channel_hint = None
    if video_path.parent.name == "01_CHUA_RENDER" and video_path.parent.parent.name.startswith("KENH_"):
        channel_hint = video_path.parent.parent.name
    ch_key, ch_cfg = channel_manager.get_channel_config(channel_hint or chat_id or "default", text=video_path.name)
    channel_name = ch_cfg.get("name", ch_key)
    tts_enabled = bool(ch_cfg.get("tts_enabled", True))
    voice = ch_cfg.get("voice", "nu_tre") if tts_enabled else None
    speed = float(ch_cfg.get("speed", 1.5))
    mask_mode = ch_cfg.get("mask_mode", "blur_sub_black")
    burn_sub = bool(ch_cfg.get("burn_sub", True))
    show_title_card = bool(ch_cfg.get("show_title_card", True))
    bg_volume_val = float(ch_cfg.get("bg_volume", 0.10))
    drive_folder = str(ch_cfg.get("drive_folder", "KENH_005_VuTruCayPhim/02_MOI_RENDER_CHO_XAC_NHAN"))

    voice_label = channel_manager.get_supported_voices().get(voice, voice) if tts_enabled else "Âm thanh gốc"
    mask_label = channel_manager.SUPPORTED_MASKS.get(mask_mode, mask_mode)

    if chat_id:
        status_msg = send_message(
            chat_id=chat_id,
            text=f"📁 <b>Phát hiện video mới chưa render trong Google Drive:</b>\n"
                 f"<code>{video_path.name}</code>\n"
                 f"📺 Kênh: <b>{channel_name}</b>\n"
                 f"⏳ Đang tự động xử lý ({voice_label} {speed}x, che: {mask_mode})..."
        )
        sent_msg_id = status_msg.get("result", {}).get("message_id") if status_msg else None

    srt_file = WORKSPACE_DIR / f"{stem}_vi.srt"
    voice_file = WORKSPACE_DIR / f"{stem}_voice.wav"
    processed_file = WORKSPACE_DIR / f"{stem}_vi.mp4"

    try:
        target_drive_dir = render_storage.review_directory(GOOGLE_DRIVE_DIR, drive_folder)
        if sent_msg_id and chat_id:
            edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 1/3] Đang bóc tách phụ đề gốc (Whisper GPU)...</b>\nVideo: <code>{video_path.name}</code>")

        def drive_sub_progress(stage, extra=None):
            if sent_msg_id and chat_id:
                if stage == "extract_audio":
                    edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 1/3] Đang trích xuất âm thanh...</b>\nVideo: <code>{video_path.name}</code>")
                elif stage == "transcribing":
                    edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 1/3] Đang bóc tách phụ đề gốc (Whisper GPU)...</b>\nVideo: <code>{video_path.name}</code>")
                elif stage == "translating":
                    progress_info = f" ({extra})" if extra else ""
                    edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 2/3] Đang dịch phụ đề tiếng Việt (DeepSeek AI){progress_info}...</b>\nVideo: <code>{video_path.name}</code>")
                elif stage == "tts_dubbing":
                    edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 3/3] Đang tạo giọng lồng tiếng ({extra} câu)...</b>\nVideo: <code>{video_path.name}</code>")

        try:
            if tts_enabled or burn_sub:
                srt_path, vi_segments = sub_processor.generate_vietnamese_subtitles(
                    video_path=str(video_path),
                    output_srt_path=str(srt_file),
                    progress_callback=drive_sub_progress,
                    dubbing_speed=ch_cfg.get('speed') if ch_cfg.get('synthesis_speed') else None
                )
            else:
                srt_path, vi_segments = str(srt_file), []
        except RuntimeError as sub_err:
            if "NO_SPEECH_DETECTED" in str(sub_err):
                print(f"[Bot] Drive Video không có lời thoại (chỉ có nhạc nền/âm thanh): {sub_err}")
                srt_path, vi_segments = str(srt_file), []
            else:
                raise

        # Đặt tên phim tiếng Việt và tạo tên file không dấu cách nhau dấu _
        movie_title_vi, movie_slug = sub_processor.generate_movie_title(
            raw_title=stem,
            segments=vi_segments
        )
        if not movie_slug:
            movie_slug = f"{stem}_vi"
        from render_review_policy import review_filename
        final_filename = review_filename(movie_title_vi, stem if re.fullmatch(r'\d{10,24}',stem) else None)
        final_srt_name = Path(final_filename).with_suffix('.srt').name
        dest_video = target_drive_dir / final_filename
        dest_srt = target_drive_dir / final_srt_name

        # Wuby Drive watcher dùng cùng preflight với luồng Telegram: phân tích trước rồi mới TTS/render.
        wuby_assignments = None
        wuby_profile_map = {}
        wuby_duration_match = {}
        wuby_preflight_cfg = ch_cfg.get("wuby_preflight") if isinstance(ch_cfg.get("wuby_preflight"), dict) else {}
        if ch_cfg.get("workflow") == "wuby" and wuby_preflight_cfg.get("enabled", True):
            try:
                if sent_msg_id and chat_id:
                    edit_message(chat_id, sent_msg_id, "🔎 <b>[Wuby Preflight] Đang đo khung hình, scene, OCR và Character ID trước render...</b>")
                orig_srt = Path(srt_path).with_suffix(".orig.srt")
                orig_segments = sub_processor.parse_srt_to_segments(str(orig_srt)) if orig_srt.exists() else []
                cfg_data = channel_manager.load_channels_config()
                wuby_report_path = WORKSPACE_DIR / f"{stem}_wuby_preflight.json"
                wuby_report = wuby_preflight.analyze_wuby_preflight(
                    video_path=str(video_path),
                    source_segments=orig_segments,
                    target_segments=vi_segments,
                    srt_path=str(srt_file) if os.path.exists(srt_file) else None,
                    movie_title=movie_title_vi,
                    config_data=cfg_data,
                    cfg=wuby_preflight_cfg,
                    report_path=str(wuby_report_path),
                )
                plan = wuby_report.get("render_plan") or {}
                ocr_data = wuby_report.get("ocr") or {}
                ch_cfg["_wuby_preflight"] = {
                    "ocr_events": ocr_data.get("events") or [],
                    "scene_ranges": (wuby_report.get("scenes") or {}).get("ranges") or [],
                    "render_plan": plan,
                    "ocr_matched": True,
                    "report_path": str(wuby_report_path),
                }
                ch_cfg["ocr_fps"] = float(plan.get("ocr_sample_fps") or ch_cfg.get("ocr_fps", 24.0))
                if not bool(plan.get("hybrid_frame_allowed", True)):
                    ch_cfg.setdefault("wuby_studio", {}).setdefault("hybrid_frame", {})["enabled"] = False
                voice_match = (wuby_report.get("voice") or {}).get("match") or {}
                wuby_assignments = voice_match.get("target_assignments") or None
                if wuby_assignments:
                    unique_profiles = sorted({str(a.get("profile")) for a in wuby_assignments if a.get("profile")})
                    for key in unique_profiles:
                        wuby_profile_map[key] = channel_manager._resolve_voice_profile(key, cfg_data, ch_cfg)
                    wuby_duration_match = (wuby_preflight_cfg.get("voice_match") or {}).get("duration_match") or {}
                    voice_label = f"Wuby Character ID ({len(unique_profiles)} giọng khóa)"
            except Exception as wuby_pf_err:
                print(f"[WubyPreflight/Drive] Cảnh báo, fallback pipeline cũ: {wuby_pf_err}")
                wuby_assignments = None
                ch_cfg.pop("_wuby_preflight", None)

        if tts_enabled and vi_segments:
            if sent_msg_id and chat_id:
                edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 3/3] Đang tạo giọng lồng tiếng ({voice_label}, tốc độ {speed}x)...</b>\nĐang khớp giọng đọc chuẩn xác...")
            try:
                if wuby_assignments:
                    video_dur = video_merger.get_video_duration(str(video_path))
                    sub_processor.generate_dubbed_audio_multivoice(
                        segments=vi_segments,
                        assignments=wuby_assignments,
                        output_audio_path=str(voice_file),
                        profile_map=wuby_profile_map,
                        speed=speed,
                        total_duration_sec=video_dur if video_dur > 0 else None,
                        duration_match=wuby_duration_match,
                        progress_callback=drive_sub_progress,
                    )
                    from render_review_policy import validate_voice_assignments
                    validate_voice_assignments(wuby_assignments, json.loads(
                        voice_file.with_suffix('.multivoice.json').read_text(encoding='utf-8')))
                else:
                    sub_processor.generate_dubbed_audio(
                        segments=vi_segments,
                        output_audio_path=str(voice_file),
                        voice=voice,
                        speed=speed,
                        voice_profile=ch_cfg.get("_voice_profile"),
                        progress_callback=drive_sub_progress
                    )
            except Exception as voice_err:
                print(f"[DriveWatcher] Lỗi tạo voice audio: {voice_err}")
                if ch_cfg.get("_voice_profile", {}).get("require_clone") and not wuby_assignments and sent_msg_id and chat_id:
                    edit_message(
                        chat_id,
                        sent_msg_id,
                        f"❌ <b>Lỗi Voice Clone Wuby:</b>\n<code>{voice_err}</code>\n\n<i>Cấu hình yêu cầu bắt buộc clone nên hệ thống dừng, không tự đổi sang Hoài My.</i>"
                    )
                raise

        if sent_msg_id and chat_id:
            edit_message(chat_id, sent_msg_id, f"⏳ <b>[Bước 3/3] Đang ghép video & chèn tiêu đề phim ({movie_title_vi})...</b>\nChế độ che: <code>{mask_mode}</code> | Đang xuất video...")

        video_merger.process_video_sub_and_mute(
            input_video=str(video_path),
            output_video=str(processed_file),
            srt_path=str(srt_file) if (burn_sub and os.path.exists(srt_file)) else None,
            voice_audio=str(voice_file) if tts_enabled and os.path.exists(voice_file) else None,
            keep_bg_audio=ch_cfg.get("keep_bg_audio", False),
            bg_volume=bg_volume_val,
            blur_sub=(mask_mode in ["blur", "black_bar", "blur_sub_black"]),
            use_nvenc=True,
            segments=vi_segments,
            movie_title=movie_title_vi if show_title_card or mask_mode == "in_video_overlay" else None,
            mask_mode=mask_mode,
            channel_cfg=ch_cfg
        )

        from wuby_studio.hybrid import frame_finished_wuby
        render_storage.require_rendered_video(processed_file)
        finished_video = render_storage.require_rendered_video(
            frame_finished_wuby(processed_file, movie_title_vi, ch_cfg)
        )
        if finished_video.exists():
            dest_video = render_storage.save_to_review(finished_video, target_drive_dir, final_filename, srt_file)
            dest_srt = dest_video.with_suffix(".srt")
            final_filename, final_srt_name = dest_video.name, dest_srt.name
            mark_drive_file_processed(video_path)
                
            file_size_mb = round(os.path.getsize(str(dest_video)) / (1024 * 1024), 2)
            print(f"[DriveWatcher] Đã render và lưu vào thư mục Google Drive của kênh: {dest_video}")
            
            if chat_id:
                caption_post = sub_processor.generate_movie_caption(
                    movie_title=movie_title_vi,
                    raw_title=stem,
                    segments=vi_segments
                )

                from caption_handoff import save_caption
                save_caption(dest_video, caption_post)

                title_status = "Bật" if show_title_card else "Tắt"
                success_text = (
                    f"✅ <b>ĐÃ RENDER XONG VIDEO TỪ GOOGLE DRIVE!</b> 🚀\n\n"
                    f"🎬 <b>TÊN PHIM:</b> <code>{movie_title_vi}</code>\n"
                    f"📁 <b>TÊN FILE:</b> <code>{final_filename}</code>\n"
                    f"📹 <b>Video gốc:</b> <code>{video_path.name}</code>\n"
                    f"📺 <b>Kênh áp dụng:</b> <b>{channel_name}</b>\n"
                    f"📁 <b>Video chờ duyệt:</b> <code>{html.escape(str(dest_video))}</code>\n"
                    f"🎙 <b>Lồng tiếng:</b> {voice_label} (Tốc độ {speed}x)\n"
                    f"🔲 <b>Che chữ:</b> {mask_label}\n"
                    f"🎬 <b>Tiêu đề 6s:</b> {title_status}\n"
                    f"📊 <b>Dung lượng:</b> <code>{file_size_mb} MB</code>"
                )
                if sent_msg_id:
                    edit_message(chat_id, sent_msg_id, success_text)
                else:
                    send_message(chat_id, success_text)

                if control_chat in ALLOWED_CHAT_IDS and str(chat_id) != control_chat:
                    try:
                        send_message(control_chat, success_text)
                    except Exception:
                        pass

                # Gửi riêng tin nhắn chứa Caption bài đăng để người dùng chạm 1 lần là copy toàn bộ
                if caption_post:
                    safe_caption = html.escape(caption_post)
                    send_message(
                        chat_id=chat_id,
                        text=f"📋 <b>CAPTION BÀI ĐĂNG (Chạm vào khung dưới để copy):</b>\n\n<pre>{safe_caption}</pre>"
                    )

                if file_size_mb <= 49:
                    send_video(
                        chat_id=chat_id,
                        video_path=str(dest_video),
                        caption=f"🎬 <b>{movie_title_vi}</b>\n📁 <code>{final_filename}</code> ({file_size_mb} MB)\nĐã lưu vào: {drive_folder}"
                    )
                    if os.path.exists(dest_srt):
                        send_document(
                            chat_id=chat_id,
                            doc_path=str(dest_srt),
                            caption=f"📄 Phụ đề tiếng Việt: <code>{final_srt_name}</code>"
                        )
        
        # Clean workspace temp
        for p in [srt_file, voice_file, processed_file, finished_video]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    except Exception as e:
        err_str = str(e)
        print(f"[DriveWatcher] Lỗi xử lý {video_path.name}: {err_str}")
        if chat_id and sent_msg_id:
            short_e = err_str[:400] + "..." if len(err_str) > 400 else err_str
            edit_message(chat_id, sent_msg_id, f"❌ Lỗi xử lý {video_path.name}:\n<code>{html.escape(short_e)}</code>")
    finally:
        CURRENTLY_PROCESSING.discard(processing_key)

def drive_folder_watcher():
    """Background thread to monitor GOOGLE_DRIVE_DIR for any new unrendered videos."""
    time.sleep(5)
    while True:
        try:
            if GOOGLE_DRIVE_DIR.exists():
                for item in render_storage.watch_inputs(GOOGLE_DRIVE_DIR):
                    if render_storage.source_key(item, GOOGLE_DRIVE_DIR) in CURRENTLY_PROCESSING or is_drive_file_processed(item):
                        continue
                    
                    # Verify file size stability (ensure fully transferred / not currently writing)
                    try:
                        s1 = item.stat().st_size
                        time.sleep(3)
                        if not item.exists():
                            continue
                        s2 = item.stat().st_size
                        if s1 != s2 or s2 < 10000:
                            continue
                    except Exception:
                        continue

                    print(f"[DriveWatcher] Phát hiện video mới chưa render: {item.name}. Bắt đầu xử lý...")
                    process_local_drive_video(item)
        except Exception as exc:
            print(f"[DriveWatcher] Watcher error: {exc}")
        time.sleep(10)

RERENDERING_JOBS = set()

def _execute_rerender_job(job_id: str, row_idx: int, chat_id: Any, url: str, workflow: str):
    """Thực thi render lại một job khi được yêu cầu từ Google Sheet."""
    try:
        print(f"[SheetReviewWatcher] Bắt đầu render lại job {job_id} ({workflow})...")
        sheet_queue_manager.update_job_status(
            job_id=job_id,
            row_idx=row_idx,
            status="🔄 Đang bắt đầu render lại...",
            progress="15%"
        )
        handle_video_download(
            chat_id=chat_id,
            message_id=None,
            text=url,
            override_workflow=workflow,
            job_id=job_id,
            sheet_row=row_idx
        )
    except Exception as e:
        print(f"[SheetReviewWatcher] Lỗi khi render lại {job_id}: {e}")
        sheet_queue_manager.update_job_status(
            job_id=job_id,
            row_idx=row_idx,
            status="🔴 Lỗi khi render lại",
            progress="ERROR",
            note=str(e)[:100]
        )
    finally:
        RERENDERING_JOBS.discard(job_id)

def sheet_review_watcher():
    """Background thread to monitor Google Sheet 'Đánh giá của tôi' column.
    Khi phát hiện 'Chưa đạt xóa video render lại':
    - Xóa video và phụ đề cũ đã render
    - Tự động kích hoạt render lại
    """
    time.sleep(15)
    while True:
        try:
            jobs = sheet_queue_manager.get_all_jobs_from_sheet()
            for j in jobs:
                job_id = j.get("job_id", "")
                rev = j.get("user_review", "").lower()
                status = j.get("status", "")

                # Điều kiện kích hoạt: user đánh giá Chưa đạt / render lại và chưa trong tiến trình render lại
                if ("chưa đạt" in rev or "render lại" in rev) and job_id not in RERENDERING_JOBS:
                    if "đang render" in status.lower() or "đang tách" in status.lower() or "đang xử lý" in status.lower() or "đang bắt đầu" in status.lower():
                        continue

                    print(f"[SheetReviewWatcher] Phát hiện đánh giá 'Chưa đạt' cho Job {job_id} (Dòng {j['row_idx']}). Đang xử lý...")
                    RERENDERING_JOBS.add(job_id)

                    # 1. Xóa file render cũ trên Google Drive và workspace
                    del_files = sheet_queue_manager.delete_rendered_files_for_job(j, google_drive_base=GOOGLE_DRIVE_DIR)
                    print(f"[SheetReviewWatcher] Đã xóa {len(del_files)} file cũ của {job_id}")

                    # 2. Reset trạng thái trên Sheet
                    sheet_queue_manager.reset_failed_job_in_sheet(
                        job_id=job_id,
                        row_idx=j["row_idx"],
                        note_suffix="Chờ render lại"
                    )

                    # 3. Kích hoạt render lại
                    cfg_str = j.get("config", "").lower()
                    if "wuby" in cfg_str or "cấu hình 1" in cfg_str:
                        workflow = "wuby"
                    elif "cấu hình 3" in cfg_str or "cauhinh3" in cfg_str:
                        workflow = "cauhinh3"
                    elif "cấu hình 4" in cfg_str or "cauhinh4" in cfg_str:
                        workflow = "cauhinh4"
                    else:
                        workflow = "cauhinh2"

                    chat_id = j.get("chat_id") or GROUP_ID.split(",")[0]
                    url = j.get("source_url", "")

                    if url:
                        t = threading.Thread(
                            target=_execute_rerender_job,
                            args=(job_id, j["row_idx"], chat_id, url, workflow),
                            daemon=True
                        )
                        t.start()
        except Exception as e:
            print(f"[SheetReviewWatcher] Lỗi vòng lặp quét sheet: {e}")
        time.sleep(20)

def start_bot_polling():
    """Starts Telegram long-polling loop, Google Drive background folder watcher, and Sheet Review watcher."""
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN chưa được cấu hình trong backend/.env")
    ensure_single_instance()
    
    print("=" * 60)
    print("🤖 TELEGRAM BOT AUTO DOWNLOADER ĐANG HOẠT ĐỘNG")
    print(f"• Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"• Nhóm được cấp phép: {list(ALLOWED_CHAT_IDS)}")
    print(f"• Thư mục Google Drive: {GOOGLE_DRIVE_DIR}")
    print(f"• File cấu hình kênh: {channel_manager.CONFIG_FILE}")
    print(f"• Số kênh đã nạp: {len(channel_manager.get_channel_entries())} | Preset: {len(channel_manager.get_preset_entries())}")
    print("=" * 60)

    # Khởi động luồng giám sát thư mục Google Drive
    watcher_thread = threading.Thread(target=drive_folder_watcher, daemon=True, name="DriveWatcher")
    watcher_thread.start()
    print("[Bot] Đã kích hoạt giám sát tự động thư mục Google Drive.")

    # Khởi động luồng tự động quét đánh giá Chưa đạt trên Google Sheet
    review_thread = threading.Thread(target=sheet_review_watcher, daemon=True, name="SheetReviewWatcher")
    review_thread.start()
    print("[Bot] Đã kích hoạt tự động quét cột 'Đánh giá của tôi' trên Google Sheet.")

    # Kiểm tra trạng thái Webhook và tự động dọn dẹp nếu có webhook cũ cản trở polling
    try:
        wh_info = requests.get(f"{API_BASE}/getWebhookInfo", timeout=10).json()
        if wh_info.get("ok") and wh_info.get("result", {}).get("url"):
            wh_url = wh_info["result"]["url"]
            if os.getenv("USE_WEBHOOK", "false").lower() != "true":
                print(f"[Bot] Phát hiện webhook cũ ({wh_url}). Tự động xóa webhook để chạy local polling 24/7...")
                del_res = requests.post(f"{API_BASE}/deleteWebhook?drop_pending_updates=false", timeout=10).json()
                print(f"[Bot] Kết quả xóa webhook: {del_res}")
            else:
                print(f"[Bot] Webhook đang hoạt động tại {wh_url}. Bỏ qua polling cục bộ theo cấu hình USE_WEBHOOK=true.")
                return
    except Exception as e:
        print(f"[Bot] Không thể kiểm tra webhook: {e}")

    offset = 0
    update_heartbeat("started")
    while True:
        update_heartbeat("polling", {"offset": offset})
        try:
            url = f"{API_BASE}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # Xử lý sự kiện bấm nút chọn cấu hình (Inline Keyboard Callback)
                    callback_query = update.get("callback_query")
                    if callback_query:
                        cb_id = callback_query.get("id")
                        cb_data = callback_query.get("data", "")
                        cb_msg = callback_query.get("message", {})
                        cb_chat = cb_msg.get("chat", {})
                        cb_chat_id = cb_chat.get("id")
                        cb_msg_id = cb_msg.get("message_id")
                        cb_thread_id = cb_msg.get("message_thread_id")

                        if cb_data.startswith("cfg:"):
                            parts = cb_data.split(":")
                            if len(parts) >= 3:
                                choice = parts[1]  # wuby / cauhinh2 / cauhinh3 / cauhinh4
                                job_id = parts[2]

                                job = PENDING_JOBS.pop(job_id, None)

                                preset_key = "wuby" if choice in {"wuby", "cauhinh1"} else choice
                                live_presets = channel_manager.load_channels_config().get("presets", {})
                                choice_label = str(
                                    (live_presets.get(preset_key) or {}).get("name") or choice
                                )
                                
                                if job and choice in ["cauhinh3"]:
                                    PENDING_JOBS[job_id] = job
                                    reply_markup = {
                                        "inline_keyboard": [
                                            [{"text": "📺 Logo Bật Phim Lên", "callback_data": f"run:{choice}:batphimlen:{job_id}"}],
                                            [{"text": "🌌 Logo Vũ Trụ Cày Phim", "callback_data": f"run:{choice}:vutrucayphim:{job_id}"}]
                                        ]
                                    }
                                    edit_message(
                                        chat_id=cb_chat_id,
                                        message_id=cb_msg_id,
                                        text=f"Bạn đã chọn {choice_label}. Tiếp theo, hãy chọn Logo:",
                                        reply_markup=reply_markup
                                    )
                                    continue

                                answer_callback_query(cb_id, text=f"Đã chọn {choice_label}!")

                                if job:
                                    sheet_row = job.get("sheet_row")
                                    try:
                                        sheet_queue_manager.update_job_status(
                                            job_id=job_id,
                                            row_idx=sheet_row,
                                            config_name=choice_label,
                                            status="⏳ Đã chọn cấu hình - Đang tải video",
                                            progress="20%"
                                        )
                                    except Exception as sq_err:
                                        print(f"[Bot] Lỗi cập nhật Sheet khi chọn cấu hình: {sq_err}")

                                    edit_message(
                                        chat_id=cb_chat_id,
                                        message_id=cb_msg_id,
                                        text=f"⏳ <b>Đã chọn: {choice_label}</b>\nĐang tiến hành tải và xử lý video..."
                                    )
                                    t = threading.Thread(
                                        target=handle_video_download,
                                        args=(job["chat_id"], job["message_id"], job["text"]),
                                        kwargs={
                                            "message_thread_id": job["thread_id"],
                                            "status_msg_id": cb_msg_id,
                                            "override_workflow": choice,
                                            "job_id": job_id,
                                            "sheet_row": sheet_row
                                        },
                                        daemon=True
                                    )
                                    t.start()
                                else:
                                    edit_message(
                                        chat_id=cb_chat_id,
                                        message_id=cb_msg_id,
                                        text="⚠️ Yêu cầu đã được xử lý hoặc đã hết hạn. Vui lòng gửi lại link!"
                                    )
                            continue

                        if cb_data.startswith("run:"):
                            parts = cb_data.split(":")
                            if len(parts) >= 4:
                                choice = parts[1]
                                logo_choice = parts[2]
                                job_id = parts[3]
                                
                                job = PENDING_JOBS.pop(job_id, None)
                                preset_key = choice
                                live_presets = channel_manager.load_channels_config().get("presets", {})
                                choice_label = str((live_presets.get(preset_key) or {}).get("name") or choice)
                                
                                answer_callback_query(cb_id, text=f"Đã chọn Logo {logo_choice}!")
                                
                                if job:
                                    sheet_row = job.get("sheet_row")
                                    try:
                                        sheet_queue_manager.update_job_status(
                                            job_id=job_id,
                                            row_idx=sheet_row,
                                            config_name=choice_label,
                                            status="⏳ Đang tải video",
                                            progress="20%"
                                        )
                                    except Exception as sq_err:
                                        pass
                                    
                                    edit_message(
                                        chat_id=cb_chat_id,
                                        message_id=cb_msg_id,
                                        text=f"⏳ <b>Đã chọn: {choice_label}</b>\nLogo: {logo_choice}\nĐang tiến hành tải và xử lý video..."
                                    )
                                    t = threading.Thread(
                                        target=handle_video_download,
                                        args=(job["chat_id"], job["message_id"], job["text"]),
                                        kwargs={
                                            "message_thread_id": job["thread_id"],
                                            "status_msg_id": cb_msg_id,
                                            "override_workflow": choice,
                                            "job_id": job_id,
                                            "sheet_row": sheet_row,
                                            "logo_choice": logo_choice
                                        },
                                        daemon=True
                                    )
                                    t.start()
                                else:
                                    edit_message(chat_id=cb_chat_id, message_id=cb_msg_id, text="⚠️ Yêu cầu đã hết hạn.")
                            continue

                        if cb_data.startswith("intro:"):
                            parts = cb_data.split(":")
                            if len(parts) >= 3:
                                action = parts[1]
                                preview_token = parts[2]
                                job = PENDING_INTRO_JOBS.get(preview_token)

                                if not job:
                                    answer_callback_query(cb_id, text="⚠️ Yêu cầu đã hết hạn hoặc đã được xử lý.")
                                    continue

                                if action == "edit":
                                    answer_callback_query(cb_id, text="Vui lòng gửi tin nhắn tiêu đề mới...")
                                    WAITING_CUSTOM_TITLE[cb_chat_id] = preview_token
                                    send_message(
                                        chat_id=cb_chat_id,
                                        text="✏️ <b>Vui lòng gửi tin nhắn chứa Tiêu Đề Mới:</b>\n<i>(Ví dụ: CHỊ ĐẸP CÂU ĐÀI TẬP 5)</i>\nBot sẽ cập nhật lại ảnh xem trước ngay lập tức.",
                                        message_thread_id=job.get("message_thread_id")
                                    )
                                    continue

                                # Xóa job khỏi pending khi user đã duyệt hành động
                                PENDING_INTRO_JOBS.pop(preview_token, None)

                                intro_action = action
                                trim_sec = job.get("cut_ts", 0.15) if action == "trim" else 0.0
                                banner_png = job.get("banner_png") if action == "banner" else None
                                banner_box = job.get("banner_box")
                                sticker_box = job.get("sticker_box")

                                if action == "banner":
                                    action_desc = "Đã chọn: Dùng Banner Tiêu Đề 2.5s"
                                elif action == "trim":
                                    if sticker_box:
                                        action_desc = "Đã chọn: Làm mờ sạch chữ Trung Quốc"
                                    else:
                                        action_desc = "Đã chọn: Cắt bỏ 0.15s bìa đầu"
                                else:
                                    action_desc = "Đã chọn: Render thường (Bỏ qua xử lý bìa)"

                                answer_callback_query(cb_id, text=f"✅ {action_desc}")
                                send_message(
                                    chat_id=cb_chat_id,
                                    text=f"🚀 <b>Bắt đầu Render:</b> {action_desc}...\nĐang xuất video chất lượng cao...",
                                    message_thread_id=job.get("message_thread_id")
                                )

                                t = threading.Thread(
                                    target=handle_video_download,
                                    args=(job["chat_id"], job["message_id"], job["text"]),
                                    kwargs={
                                        "message_thread_id": job.get("message_thread_id"),
                                        "status_msg_id": job.get("status_msg_id"),
                                        "override_workflow": job.get("override_workflow"),
                                        "override_voice": job.get("override_voice"),
                                        "job_id": job.get("job_id"),
                                        "sheet_row": job.get("sheet_row"),
                                        "logo_choice": job.get("logo_choice"),
                                        "intro_action": intro_action,
                                        "trim_start_sec": trim_sec,
                                        "intro_banner_png": banner_png,
                                        "intro_banner_box": banner_box,
                                        "intro_sticker_box": sticker_box
                                    },
                                    daemon=True
                                )
                                t.start()
                            continue

                    message = update.get("message") or update.get("channel_post")
                    if not message:
                        continue

                    chat = message.get("chat", {})
                    chat_id = chat.get("id")
                    message_id = message.get("message_id")
                    thread_id = message.get("message_thread_id")
                    text = message.get("text") or message.get("caption") or ""

                    # Check for supergroup migration
                    migrate_to = message.get("migrate_to_chat_id")
                    if migrate_to:
                        print(f"[Bot] Phát hiện sự kiện nhóm chuyển sang supergroup: {migrate_to}")
                        add_allowed_chat(migrate_to)
                        continue

                    # Log received chat ID for easy verification
                    print(f"[Bot] Nhận tin nhắn từ Chat ID: {chat_id} (Type: {chat.get('type')}) | Nội dung: {text[:80]}")

                    if not text:
                        continue

                    text_strip = text.strip()

                    # Kiểm tra xem người dùng có đang gõ tiêu đề mới cho bản xem trước Pre-render không
                    from_user_id = (message.get("from") or {}).get("id")
                    check_keys = [chat_id, from_user_id]
                    matched_key = next((k for k in check_keys if k in WAITING_CUSTOM_TITLE), None)
                    if matched_key and text_strip and not text_strip.startswith("/"):
                        preview_token = WAITING_CUSTOM_TITLE.pop(matched_key)
                        job = PENDING_INTRO_JOBS.get(preview_token)
                        if job:
                            new_title = text_strip
                            import intro_banner_service
                            preview_img = WORKSPACE_DIR / f"preview_{preview_token}.jpg"
                            preview_data = intro_banner_service.generate_prerender_preview(
                                video_path=job["downloaded"],
                                title_text=new_title,
                                brand_text="CHỊ ĐẸP ĐI CÂU",
                                out_preview_path=str(preview_img)
                            )
                            job["suggested_title"] = new_title
                            job["banner_png"] = preview_data["banner_png"]
                            job["banner_box"] = preview_data.get("banner_box")
                            job["sticker_box"] = preview_data.get("sticker_box")

                            keyboard = {
                                "inline_keyboard": [
                                    [
                                        {"text": "✅ A. Dùng Banner Tiêu Đề", "callback_data": f"intro:banner:{preview_token}"},
                                        {"text": "✂️ B. Làm Mờ Chữ Trung (Sạch)", "callback_data": f"intro:trim:{preview_token}"}
                                    ],
                                    [
                                        {"text": "✏️ Đổi Lại Tiêu Đề Khác", "callback_data": f"intro:edit:{preview_token}"},
                                        {"text": "⏭ Render Thường (Bỏ qua)", "callback_data": f"intro:skip:{preview_token}"}
                                    ]
                                ]
                            }
                            caption = (
                                f"🎬 <b>[ĐÃ CẬP NHẬT TIÊU ĐỀ MỚI]</b>\n\n"
                                f"📌 <b>Tiêu đề mới:</b> <code>{new_title}</code>\n\n"
                                f"👉 <b>Bấm nút bên dưới để bắt đầu Render:</b>"
                            )
                            send_photo(
                                chat_id=chat_id,
                                photo_path=str(preview_img),
                                caption=caption,
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id,
                                reply_markup=keyboard
                            )
                            continue

                    # Chuẩn hóa tên lệnh và tham số (hỗ trợ cả dạng /lenh@bot_name)
                    parts = text_strip.split()
                    raw_cmd = parts[0] if parts else ""
                    clean_cmd = raw_cmd.lower().split("@")[0] if raw_cmd.startswith("/") else ""

                    # Commands /start, /help
                    if clean_cmd in ["/start", "/help"]:
                        send_message(
                            chat_id=chat_id,
                            text=(
                                f"🤖 <b>Bot Tải Video TikTok / Douyin & Lồng Tiếng AI (24/7 Online)</b>\n\n"
                                f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
                                f"📁 <b>Google Drive:</b> <code>{GOOGLE_DRIVE_DIR}</code>\n\n"
                                f"<b>📊 LỆNH HỆ THỐNG & TRẠNG THÁI:</b>\n"
                                f"• <code>/ping</code> : Kiểm tra bot phản hồi (Uptime, RAM, Drive)\n"
                                f"• <code>/status</code> : Chi tiết trạng thái hệ thống & hàng đợi\n"
                                f"• <code>/id</code> : Kiểm tra Chat ID & quyền truy cập nhóm\n"
                                f"• <code>/jobs</code> hoặc <code>/queue</code> : Xem danh sách job đang xử lý\n"
                                f"• <code>/retry [dòng]</code> : Render lại job theo số dòng Google Sheet\n\n"
                                f"<b>📋 LỆNH CẤU HÌNH KÊNH:</b>\n"
                                f"• <code>/kenh</code> : Xem cấu hình kênh nhóm này\n"
                                f"• <code>/set_voice [tên]</code> : Đổi giọng đọc AI\n"
                                f"• <code>/set_speed [số]</code> : Đổi tốc độ đọc (0.8 - 2.0)\n"
                                f"• <code>/set_mask [kiểu]</code> : Đổi kiểu che chữ (blur, black_bar, none)\n"
                                f"• <code>/set_title [on/off]</code> : Bật/tắt tiêu đề mở đầu\n"
                                f"• <code>/set_workflow [tên]</code> : Đổi workflow kênh\n"
                                f"• <code>/reload_config</code> : Nạp lại channels_config.json\n\n"
                                f"👉 <b>Cách dùng:</b> Chỉ cần dán link Douyin/TikTok vào nhóm, bot sẽ tự động hiện 4 cấu hình để bạn chọn bấm nút!"
                            ),
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Command /ping: Phản hồi tức thì kiểm tra sống/chết
                    if clean_cmd == "/ping":
                        now_uptime = int(time.time() - START_TIME)
                        hrs = now_uptime // 3600
                        mins = (now_uptime % 3600) // 60
                        secs = now_uptime % 60
                        uptime_str = f"{hrs}h {mins}m {secs}s" if hrs else f"{mins}m {secs}s"
                        
                        try:
                            ram_used = psutil.virtual_memory().percent
                            cpu_used = psutil.cpu_percent(interval=0.05)
                        except Exception:
                            ram_used, cpu_used = "N/A", "N/A"
                        
                        drive_ok = GOOGLE_DRIVE_DIR.exists()
                        drive_status = "🟢 Đã kết nối" if drive_ok else "🔴 Không tìm thấy"
                        active_count = len(CURRENTLY_PROCESSING)
                        pending_count = len(PENDING_JOBS)
                        
                        send_message(
                            chat_id=chat_id,
                            text=(
                                f"🏓 <b>PONG! Bot đang online 24/7!</b>\n\n"
                                f"⏱ <b>Thời gian chạy (Uptime):</b> <code>{uptime_str}</code>\n"
                                f"🆔 <b>Process PID:</b> <code>{os.getpid()}</code>\n"
                                f"💻 <b>RAM:</b> <code>{ram_used}%</code> | <b>CPU:</b> <code>{cpu_used}%</code>\n"
                                f"📁 <b>Google Drive:</b> {drive_status}\n"
                                f"⚙️ <b>Job đang render:</b> <code>{active_count}</code>\n"
                                f"⏳ <b>Job chờ chọn nút:</b> <code>{pending_count}</code>\n\n"
                                f"✅ <i>Hệ thống tự động giám sát và phục hồi liên tục 24/7.</i>"
                            ),
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Command /status: Báo cáo trạng thái chi tiết
                    if clean_cmd == "/status":
                        now_uptime = int(time.time() - START_TIME)
                        hrs = now_uptime // 3600
                        mins = (now_uptime % 3600) // 60
                        uptime_str = f"{hrs}h {mins}m"
                        
                        active_jobs_desc = ", ".join(list(CURRENTLY_PROCESSING)[:5]) or "Không có"
                        allowed_status = "✅ Nhóm hợp lệ" if is_allowed_chat(chat_id) else "⚠️ Chưa cấp phép"
                        
                        send_message(
                            chat_id=chat_id,
                            text=(
                                f"📊 <b>TRẠNG THÁI HỆ THỐNG TIKTOK DUBBER (24/7)</b>\n\n"
                                f"• <b>Bot PID:</b> <code>{os.getpid()}</code> (Uptime: {uptime_str})\n"
                                f"• <b>Quyền nhóm này:</b> {allowed_status} (ID: <code>{chat_id}</code>)\n"
                                f"• <b>Google Drive:</b> <code>{GOOGLE_DRIVE_DIR}</code> ({'OK' if GOOGLE_DRIVE_DIR.exists() else 'LỖI'})\n"
                                f"• <b>Preset nạp:</b> <code>{len(channel_manager.get_preset_entries())}</code>\n"
                                f"• <b>Job đang xử lý:</b> <code>{len(CURRENTLY_PROCESSING)}</code> ({active_jobs_desc})\n"
                                f"• <b>Job chờ bấm nút:</b> <code>{len(PENDING_JOBS)}</code>\n"
                                f"• <b>Watcher Google Sheet:</b> 🟢 Đang chạy (tự quét Chưa đạt)\n"
                                f"• <b>Watcher Google Drive:</b> 🟢 Đang chạy (tự phát hiện file mới)"
                            ),
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Command /id: Xem Chat ID và quyền
                    if clean_cmd == "/id":
                        allowed = is_allowed_chat(chat_id)
                        allowed_text = "✅ <b>ĐÃ CẤP PHÉP</b> (Nhận link & render tự động)" if allowed else "⚠️ <b>CHƯA CẤP PHÉP</b> (Thêm vào backend/.env để nhận link)"
                        send_message(
                            chat_id=chat_id,
                            text=(
                                f"🆔 <b>THÔNG TIN CHAT / NHÓM:</b>\n\n"
                                f"• <b>Chat ID:</b> <code>{chat_id}</code>\n"
                                f"• <b>Loại:</b> <code>{chat.get('type')}</code>\n"
                                f"• <b>Tên nhóm:</b> {html.escape(str(chat.get('title', 'Cá nhân')))}\n"
                                f"• <b>Trạng thái:</b> {allowed_text}\n\n"
                                f"<i>Danh sách nhóm cấp phép: {list(ALLOWED_CHAT_IDS)}</i>"
                            ),
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Command /jobs hoặc /queue: Xem danh sách job
                    if clean_cmd in ["/jobs", "/queue"]:
                        active_list = list(CURRENTLY_PROCESSING)
                        pending_list = list(PENDING_JOBS.keys())
                        lines = ["📋 <b>DANH SÁCH JOB HIỆN TẠI:</b>\n"]
                        if active_list:
                            lines.append(f"⚙️ <b>Đang render ({len(active_list)}):</b>")
                            for j in active_list[:10]:
                                lines.append(f"  • <code>{html.escape(j)}</code>")
                        else:
                            lines.append("⚙️ <b>Đang render:</b> Không có job nào đang chạy.")
                        
                        if pending_list:
                            lines.append(f"\n⏳ <b>Chờ chọn nút ({len(pending_list)}):</b>")
                            for pj in pending_list[:10]:
                                lines.append(f"  • <code>{pj}</code>")
                        else:
                            lines.append("\n⏳ <b>Chờ chọn nút:</b> Không có.")
                        
                        send_message(
                            chat_id=chat_id,
                            text="\n".join(lines),
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Command /retry [số_dòng hoặc job_id]: Kích hoạt render lại thủ công
                    if clean_cmd == "/retry":
                        if len(parts) < 2:
                            send_message(
                                chat_id=chat_id,
                                text="ℹ️ <b>Cú pháp:</b> <code>/retry [số_dòng_hoặc_job_id]</code>\nVí dụ: <code>/retry 64</code> hoặc <code>/retry job_1791383062420</code>",
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id
                            )
                        else:
                            target_arg = parts[1].strip()
                            all_jobs = sheet_queue_manager.get_all_jobs_from_sheet()
                            found = None
                            for j in all_jobs:
                                if str(j.get("row_idx")) == target_arg or j.get("job_id") == target_arg:
                                    found = j
                                    break
                            if found:
                                job_id = found.get("job_id")
                                row_idx = found.get("row_idx")
                                send_message(
                                    chat_id=chat_id,
                                    text=f"🔄 <b>Đang kích hoạt render lại Job {job_id} (Dòng {row_idx})...</b>",
                                    reply_to_message_id=message_id,
                                    message_thread_id=thread_id
                                )
                                cfg_str = found.get("config", "").lower()
                                workflow = "wuby" if "wuby" in cfg_str else ("cauhinh3" if "cauhinh3" in cfg_str else ("cauhinh4" if "cauhinh4" in cfg_str else "cauhinh2"))
                                t = threading.Thread(
                                    target=_execute_rerender_job,
                                    args=(job_id, row_idx, chat_id, found.get("source_url", ""), workflow),
                                    daemon=True
                                )
                                t.start()
                            else:
                                send_message(
                                    chat_id=chat_id,
                                    text=f"❌ Không tìm thấy job hoặc dòng <code>{target_arg}</code> trên Google Sheet.",
                                    reply_to_message_id=message_id,
                                    message_thread_id=thread_id
                                )
                        continue

                    # Command /restart: Khởi động lại bot an toàn
                    if clean_cmd == "/restart":
                        send_message(
                            chat_id=chat_id,
                            text="🔄 <b>Đang khởi động lại Bot...</b>\nSupervisor sẽ tự động bật lại bot sau 3 giây.",
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        time.sleep(1)
                        os._exit(0)

                    # Command /kenh hoặc /channel: Xem cấu hình kênh hiện tại
                    if clean_cmd in ["/kenh", "/channel"]:
                        ch_key, ch_cfg = channel_manager.get_channel_config(chat_id)
                        info = channel_manager.format_channel_info(ch_key, ch_cfg)
                        presets = channel_manager.get_preset_entries()
                        presets_list = "\n".join([f"• <code>#{k}</code>: {v.get('name', k)}" for k, v in presets.items()]) or "• Chưa có preset"
                        
                        msg = (
                            f"{info}\n\n"
                            f"<b>📋 Preset có sẵn:</b>\n{presets_list}\n\n"
                            f"💡 <i>Có thể gửi hashtag hoặc inline <code>voice=...</code>, <code>speed=...</code>, <code>mask=...</code>, <code>workflow=...</code> cho riêng 1 video.</i>"
                        )
                        send_message(chat_id=chat_id, text=msg, reply_to_message_id=message_id, message_thread_id=thread_id)
                        continue

                    # Command /set_voice
                    if clean_cmd == "/set_voice":
                        if len(parts) < 2:
                            voices_help = "\n".join([f"• <code>{k}</code>: {v}" for k, v in channel_manager.get_supported_voices().items()])
                            send_message(
                                chat_id=chat_id,
                                text=f"🎙 <b>Danh sách giọng đọc hỗ trợ:</b>\n{voices_help}\n\nCú pháp: <code>/set_voice [tên_giọng]</code>\nVí dụ: <code>/set_voice nam_minh</code>",
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id
                            )
                        else:
                            v_choice = parts[1].strip().lower()
                            ch_key, _ = channel_manager.get_channel_config(chat_id)
                            target_key = ch_key if ch_key != "default" else str(chat_id)
                            ok, res_msg = channel_manager.update_channel_setting(target_key, "voice", v_choice)
                            send_message(chat_id=chat_id, text=res_msg, reply_to_message_id=message_id, message_thread_id=thread_id)
                        continue

                    # Command /set_speed
                    if clean_cmd == "/set_speed":
                        if len(parts) < 2:
                            send_message(
                                chat_id=chat_id,
                                text="⚡ <b>Vui lòng nhập tốc độ đọc (0.8 - 2.0):</b>\nCú pháp: <code>/set_speed [tốc_độ]</code>\nVí dụ: <code>/set_speed 1.4</code> hoặc <code>/set_speed 1.5</code>",
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id
                            )
                        else:
                            s_choice = parts[1].strip()
                            ch_key, _ = channel_manager.get_channel_config(chat_id)
                            target_key = ch_key if ch_key != "default" else str(chat_id)
                            ok, res_msg = channel_manager.update_channel_setting(target_key, "speed", s_choice)
                            send_message(chat_id=chat_id, text=res_msg, reply_to_message_id=message_id, message_thread_id=thread_id)
                        continue

                    # Command /set_mask
                    if clean_cmd == "/set_mask":
                        if len(parts) < 2:
                            masks_help = "\n".join([f"• <code>{k}</code>: {v}" for k, v in channel_manager.SUPPORTED_MASKS.items()])
                            send_message(
                                chat_id=chat_id,
                                text=f"🔲 <b>Danh sách chế độ che chữ:</b>\n{masks_help}\n\nCú pháp: <code>/set_mask [kiểu]</code>\nVí dụ: <code>/set_mask blur</code> hoặc <code>/set_mask black_bar</code>",
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id
                            )
                        else:
                            m_choice = parts[1].strip().lower()
                            ch_key, _ = channel_manager.get_channel_config(chat_id)
                            target_key = ch_key if ch_key != "default" else str(chat_id)
                            ok, res_msg = channel_manager.update_channel_setting(target_key, "mask_mode", m_choice)
                            send_message(chat_id=chat_id, text=res_msg, reply_to_message_id=message_id, message_thread_id=thread_id)
                        continue

                    # Command /set_title
                    if clean_cmd == "/set_title":
                        if len(parts) < 2:
                            send_message(
                                chat_id=chat_id,
                                text="🎬 <b>Vui lòng nhập on hoặc off:</b>\nVí dụ: <code>/set_title off</code> để tắt tiêu đề phim mở đầu.",
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id
                            )
                        else:
                            t_choice = parts[1].strip().lower()
                            ch_key, _ = channel_manager.get_channel_config(chat_id)
                            target_key = ch_key if ch_key != "default" else str(chat_id)
                            ok, res_msg = channel_manager.update_channel_setting(target_key, "show_title_card", t_choice)
                            send_message(chat_id=chat_id, text=res_msg, reply_to_message_id=message_id, message_thread_id=thread_id)
                        continue

                    # Command /set_workflow
                    if clean_cmd == "/set_workflow":
                        workflows = channel_manager.load_channels_config().get("workflows", {})
                        if len(parts) < 2:
                            wf_help = "\n".join([f"• <code>{k}</code>: {v.get('name', k)}" for k, v in workflows.items()])
                            send_message(
                                chat_id=chat_id,
                                text=f"🧩 <b>Workflow có sẵn:</b>\n{wf_help}\n\nCú pháp: <code>/set_workflow film_review_black</code>",
                                reply_to_message_id=message_id,
                                message_thread_id=thread_id
                            )
                        else:
                            wf_choice = parts[1].strip()
                            ch_key, _ = channel_manager.get_channel_config(chat_id)
                            target_key = ch_key if ch_key != "default" else str(chat_id)
                            ok, res_msg = channel_manager.update_channel_setting(target_key, "workflow", wf_choice)
                            send_message(chat_id=chat_id, text=res_msg, reply_to_message_id=message_id, message_thread_id=thread_id)
                        continue

                    # Command /reload_config
                    if clean_cmd == "/reload_config":
                        channel_manager.load_channels_config(force_reload=True)
                        send_message(
                            chat_id=chat_id,
                            text="🔄 <b>Đã nạp lại file cấu hình channels_config.json thành công!</b>",
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Phản hồi lệnh không xác định nếu tin nhắn bắt đầu bằng /
                    if clean_cmd and clean_cmd.startswith("/"):
                        send_message(
                            chat_id=chat_id,
                            text=f"⚠️ Lệnh <code>{html.escape(clean_cmd)}</code> chưa được hỗ trợ.\n👉 Gõ <code>/help</code> hoặc <code>/ping</code> để xem danh sách lệnh!",
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )
                        continue

                    # Kiểm tra liên kết video (Douyin / TikTok)
                    has_link = any(k in text for k in ["http://", "https://", "douyin.com", "tiktok.com", "v.douyin", "vt.tiktok"])
                    if is_allowed_chat(chat_id) or chat.get("type") == "private":
                        if has_link:
                            url = downloader.extract_url(text)
                            if url:
                                job_id = f"job_{int(time.time() * 1000)}"
                                sheet_row = None
                                try:
                                    sheet_row = sheet_queue_manager.add_job_to_sheet(
                                        job_id=job_id,
                                        source_url=url,
                                        chat_id=chat_id
                                    )
                                except Exception as sq_err:
                                    print(f"[Bot] Lỗi ghi Google Sheet: {sq_err}")

                                PENDING_JOBS[job_id] = {
                                    "chat_id": chat_id,
                                    "message_id": message_id,
                                    "thread_id": thread_id,
                                    "text": text,
                                    "url": url,
                                    "sheet_row": sheet_row,
                                }
                                reply_markup = {
                                    "inline_keyboard": [
                                        [
                                            {"text": "🐱 1️⃣ Cấu hình 1 (Wuby Hoạt Hình - AI Giữ Nền & 5.1 Smart)", "callback_data": f"cfg:wuby:{job_id}"}
                                        ],
                                        [
                                            {"text": "🎬 2️⃣ Cấu hình 2 (Review Phim - Dải Đen Chuẩn Điện Ảnh)", "callback_data": f"cfg:cauhinh2:{job_id}"}
                                        ],
                                        [
                                            {"text": "🎙 3️⃣ Cấu hình 3 (1 Giọng Nữ Chính - Nền 70% / Giọng +15%)", "callback_data": f"cfg:cauhinh3:{job_id}"}
                                        ],
                                        [
                                            {"text": "🎣 4️⃣ Cấu hình 4 (Chị Đẹp Đi Câu - Giọng Nữ Cute & Sub Karaoke)", "callback_data": f"cfg:chidepdicau:{job_id}"}
                                        ],
                                        [
                                            {"text": "🌸 5️⃣ Cấu hình 5 (Sống 1 mình có gì vui - @Song1MinhCoGiVui)", "callback_data": f"cfg:song1minhcogivui:{job_id}"}
                                        ]
                                    ]
                                }
                                send_message(
                                    chat_id=chat_id,
                                    text=(
                                        "🎬 <b>ĐÃ NHẬN LINK VIDEO!</b>\n\n"
                                        "👉 <b>Vui lòng chạm nút bên dưới để chọn cấu hình xử lý:</b>\n\n"
                                        "• <b>1️⃣ Cấu hình 1 (Wuby Hoạt Hình):</b>\n"
                                        "  ├ Preflight hình/scene/OCR đè chữ hoạt hình Wuby.\n"
                                        "  └ Tự động lọc 5.1 & AI bóc tách thoại sạch sẽ, bảo toàn 100% nhạc nền và SFX.\n\n"
                                        "• <b>2️⃣ Cấu hình 2 (Review Phim - Dải Đen):</b>\n"
                                        "  ├ Dải đen chuẩn điện ảnh che trọn chữ Trung gốc, ôm sát toạ độ subtitle_regions.\n"
                                        "  ├ Sub tiếng Việt căn tâm chuẩn xác trong dải đen (\\an5\\pos), font cố định không giật.\n"
                                        "  ├ Tiêu đề phim 6 giây mở đầu tự biến mất + Logo (Bật Phim Lên / Vũ Trụ Cày Phim).\n"
                                        "  └ Giọng Nữ Trẻ tốc độ 1.3x (tự nén tối đa 1.8x cho câu dài, không cắt từ), True Peak limiter.\n\n"
                                        "• <b>3️⃣ Cấu hình 3 (Clone Phim 1 Giọng Nữ Chính):</b>\n"
                                        "  ├ Dùng cố định giọng Hoài My từ đầu đến cuối, tốc độ 1.3x.\n"
                                        "  ├ Nền 70%, giọng đọc +15%, không chạy nhận diện đa giọng.\n"
                                        "  └ Làm mờ phụ đề gốc và thay thoại theo timeline Whisper.\n\n"
                                        "• <b>4️⃣ Cấu hình 4 (Chị Đẹp Đi Câu @chidepdicau):</b>\n"
                                        "  ├ Giọng nữ Cute tự chỉnh tốc độ; kiểm tra lời đọc >95%, nền sạch 50%.\n"
                                        "  ├ Phụ đề trò chuyện kiểu Karaoke Trắng - Vàng, font 38px vừa vặn đọc trên điện thoại.\n"
                                        "  ├ Gaussian Blur tinh tế che chữ Trung (không mờ lẹm vào người/cá).\n"
                                        "  ├ Check trước mỗi video (Pre-render Preview: chọn dùng Banner 2.5s hoặc Cắt 0.15s bìa).\n"
                                        "  └ Tự động chèn Logo Chị Đẹp Đi Câu (@ChiDepDiCau).\n\n"
                                        "• <b>5️⃣ Cấu hình 5 (Sống 1 mình có gì vui):</b>\n"
                                        "  ├ Video đời sống một mình, nhẹ nhàng, bình yên.\n"
                                        "  └ Tự động chèn Logo Sống 1 mình có gì vui (@Song1MinhCoGiVui)."
                                    ),
                                    reply_to_message_id=message_id,
                                    message_thread_id=thread_id,
                                    reply_markup=reply_markup
                                )
                    elif has_link:
                        # Thông báo khi nhóm chưa được cấp phép trong .env
                        send_message(
                            chat_id=chat_id,
                            text=(
                                f"⚠️ <b>Nhóm này chưa được kích hoạt nhận link tự động!</b>\n\n"
                                f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
                                f"📌 <b>Tiêu đề nhóm:</b> {html.escape(str(chat.get('title', 'Group')))}\n\n"
                                f"👉 <i>Để kích hoạt, vui lòng thêm Chat ID <code>{chat_id}</code> vào cấu hình <code>TELEGRAM_GROUP_ID</code> trong file <code>backend/.env</code>.</i>"
                            ),
                            reply_to_message_id=message_id,
                            message_thread_id=thread_id
                        )

            elif resp.status_code == 409:
                print(f"[Bot] Phát hiện xung đột 409 (có tiến trình bot khác đang chạy). Đang tự động dọn dẹp...")
                ensure_single_instance()
                time.sleep(5)
            else:
                print(f"[Bot] getUpdates error {resp.status_code}: {resp.text}")
                time.sleep(3)
            
            update_heartbeat("polling", {"offset": offset})
        except Exception as e:
            print(f"[Bot] Polling loop error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    start_bot_polling()
