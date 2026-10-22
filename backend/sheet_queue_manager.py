import os
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union
try:
    from . import render_storage
except ImportError:
    import render_storage

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


BASE_DIR = Path(__file__).resolve().parent.parent
CREDS_FILE = Path(r"D:/02_CONG_CU/youtube-reup-pipeline\secrets\sheet_service_account.json")
SPREADSHEET_ID = "13U7eHfquutyBfrjtEtsqAFSXHrwxW9aqBSXjFnjUccs"
TAB_NAME = "TIKTOK_RENDER_QUEUE"

_LOCK = threading.Lock()
_CLIENT = None
_WORKSHEET = None


def _get_worksheet():
    """Khởi tạo hoặc tái sử dụng worksheet gspread."""
    global _CLIENT, _WORKSHEET
    if _WORKSHEET is not None:
        return _WORKSHEET

    if not CREDS_FILE.exists():
        print(f"[SheetQueue] CẢNH BÁO: Không tìm thấy file credentials tại {CREDS_FILE}")
        return None

    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(CREDS_FILE), scopes)
        _CLIENT = gspread.authorize(creds)
        sheet = _CLIENT.open_by_key(SPREADSHEET_ID)

        # Kiểm tra hoặc tạo tab
        existing = [ws.title for ws in sheet.worksheets()]
        if TAB_NAME not in existing:
            ws = sheet.add_worksheet(title=TAB_NAME, rows=500, cols=15)
            headers = [
                "Mã Job", "Thời gian nhận", "Link gốc đã gửi", "Cấu hình", 
                "File đã tải về", "Trạng thái", "Tiến độ", "File Render xong", 
                "Đường dẫn Google Drive", "Chat ID", "Ghi chú"
            ]
            ws.append_row(headers)
            _WORKSHEET = ws
        else:
            _WORKSHEET = sheet.worksheet(TAB_NAME)

        return _WORKSHEET
    except Exception as e:
        print(f"[SheetQueue] Lỗi kết nối Google Sheets: {e}")
        return None


def _get_column_map(ws) -> Dict[str, int]:
    """Lấy bản đồ tên cột -> chỉ số cột (1-indexed) từ dòng tiêu đề."""
    try:
        headers = ws.row_values(1)
        col_map = {}
        for idx, h in enumerate(headers, start=1):
            h_clean = h.strip().lower()
            if "mã job" in h_clean or "job_id" in h_clean:
                col_map["job_id"] = idx
            elif "thời gian" in h_clean or "created_at" in h_clean:
                col_map["created_at"] = idx
            elif "link gốc" in h_clean or "source_url" in h_clean or "link" in h_clean:
                col_map["source_url"] = idx
            elif "cấu hình" in h_clean or "config" in h_clean:
                col_map["config"] = idx
            elif "file đã tải" in h_clean or "downloaded" in h_clean:
                col_map["downloaded"] = idx
            elif "trạng thái" in h_clean or "status" in h_clean:
                col_map["status"] = idx
            elif "đánh giá" in h_clean or "review" in h_clean:
                col_map["user_review"] = idx
            elif "tiến độ" in h_clean or "progress" in h_clean:
                col_map["progress"] = idx
            elif "file render xong" in h_clean or "rendered" in h_clean:
                col_map["rendered"] = idx
            elif "đường dẫn google drive" in h_clean or "drive" in h_clean:
                col_map["drive"] = idx
            elif "chat id" in h_clean:
                col_map["chat_id"] = idx
            elif "ghi chú" in h_clean or "note" in h_clean:
                col_map["note"] = idx
        return col_map
    except Exception as e:
        print(f"[SheetQueue] Lỗi đọc header sheet: {e}")
        return {}


def _col_idx_to_letter(col_idx: int) -> str:
    """Chuyển đổi chỉ số cột 1-based thành chữ cái A, B, ..., Z, AA,..."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def add_job_to_sheet(job_id: str, source_url: str, chat_id: Any) -> Optional[int]:
    """Thêm một job mới vào hàng đợi Google Sheet ngay khi người dùng gửi link."""
    with _LOCK:
        ws = _get_worksheet()
        if ws is None:
            return None

        try:
            col_map = _get_column_map(ws)
            num_cols = max(col_map.values()) if col_map else 12
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")

            row_data = [""] * num_cols

            def set_val(key, val, default_idx):
                idx = col_map.get(key, default_idx)
                if 1 <= idx <= len(row_data):
                    row_data[idx - 1] = str(val)

            set_val("job_id", job_id, 1)
            set_val("created_at", now_str, 2)
            set_val("source_url", source_url, 3)
            set_val("config", "Chờ chọn cấu hình", 4)
            set_val("downloaded", "", 5)
            set_val("status", "⏳ Chờ chọn cấu hình", 6)
            set_val("user_review", "", 7)
            set_val("progress", "10%", 8)
            set_val("rendered", "", 9)
            set_val("drive", "", 10)
            set_val("chat_id", str(chat_id), 11)
            set_val("note", "", 12)

            ws.append_row(row_data)
            total_rows = len(ws.col_values(1))
            print(f"[SheetQueue] Đã lưu link vào Google Sheet: Job {job_id} -> Dòng {total_rows}")
            return total_rows
        except Exception as e:
            print(f"[SheetQueue] Lỗi khi thêm job vào Sheet: {e}")
            return None


def update_job_status(
    job_id: str,
    row_idx: Optional[int] = None,
    config_name: Optional[str] = None,
    downloaded_file: Optional[str] = None,
    status: Optional[str] = None,
    user_review: Optional[str] = None,
    progress: Optional[str] = None,
    rendered_file: Optional[str] = None,
    drive_path: Optional[str] = None,
    note: Optional[str] = None,
):
    """Cập nhật tiến trình của job trong hàng đợi Google Sheet với mapping cột động."""
    with _LOCK:
        ws = _get_worksheet()
        if ws is None:
            return

        try:
            col_map = _get_column_map(ws)
            job_col = col_map.get("job_id", 1)

            # Nếu không truyền row_idx, tìm kiếm theo job_id
            if not row_idx or row_idx <= 1:
                col_jobs = ws.col_values(job_col)
                if job_id in col_jobs:
                    row_idx = col_jobs.index(job_id) + 1
                else:
                    return

            cells_to_update = []

            def queue_update(field_key, default_col_idx, val):
                if val is not None:
                    c_idx = col_map.get(field_key, default_col_idx)
                    letter = _col_idx_to_letter(c_idx)
                    cells_to_update.append({"range": f"{letter}{row_idx}", "values": [[val]]})

            queue_update("config", 4, config_name)
            queue_update("downloaded", 5, downloaded_file)
            queue_update("status", 6, status)
            queue_update("user_review", 7, user_review)
            queue_update("progress", 8, progress)
            queue_update("rendered", 9, rendered_file)
            queue_update("drive", 10, drive_path)
            queue_update("note", 12, note)

            for cu in cells_to_update:
                ws.update(cu["range"], cu["values"])

            print(f"[SheetQueue] Đã cập nhật dòng {row_idx} ({job_id}): {status or ''} - {progress or ''}")
        except Exception as e:
            print(f"[SheetQueue] Lỗi cập nhật job {job_id}: {e}")


def get_all_jobs_from_sheet() -> list:
    """Đọc toàn bộ danh sách các job trong Google Sheet kèm metadata."""
    ws = _get_worksheet()
    if ws is None:
        return []

    try:
        rows = ws.get_all_values()
        if not rows or len(rows) <= 1:
            return []

        col_map = _get_column_map(ws)
        jobs = []

        for r_idx, row in enumerate(rows[1:], start=2):
            def get_val(key, default_idx):
                idx = col_map.get(key, default_idx)
                if 1 <= idx <= len(row):
                    return row[idx - 1].strip()
                return ""

            job_id = get_val("job_id", 1)
            if not job_id:
                continue

            jobs.append({
                "row_idx": r_idx,
                "job_id": job_id,
                "created_at": get_val("created_at", 2),
                "source_url": get_val("source_url", 3),
                "config": get_val("config", 4),
                "downloaded_file": get_val("downloaded", 5),
                "status": get_val("status", 6),
                "user_review": get_val("user_review", 7),
                "progress": get_val("progress", 8),
                "rendered_file": get_val("rendered", 9),
                "drive_path": get_val("drive", 10),
                "chat_id": get_val("chat_id", 11),
                "note": get_val("note", 12),
            })
        return jobs
    except Exception as e:
        print(f"[SheetQueue] Lỗi đọc toàn bộ job từ Sheet: {e}")
        return []


def delete_rendered_files_for_job(job_data: Union[dict, str], google_drive_base: Optional[Path] = None) -> list:
    """Xóa các video và subtitle đã render của job trên Google Drive và workspace."""
    deleted_files = []
    if google_drive_base is None:
        google_drive_base = Path(os.getenv("GOOGLE_DRIVE_DIR", "G:/My Drive/Video titok Trinh"))

    if isinstance(job_data, str):
        # Fetch job from sheet or create minimal dict
        job_id = job_data
        jobs = get_all_jobs_from_sheet()
        found = next((j for j in jobs if j.get("job_id") == job_id), None)
        if found:
            job_data = found
        else:
            job_data = {"job_id": job_id}

    rendered_file = job_data.get("rendered_file", "")
    drive_path = job_data.get("drive_path", "")

    paths_to_check = render_storage.review_files_for_job(google_drive_base, rendered_file, drive_path)

    # Workspace files
    workspace_dir = BASE_DIR / "workspace"
    if rendered_file and Path(rendered_file).name == rendered_file:
        paths_to_check.append(workspace_dir / rendered_file)
    if job_data.get("downloaded_file"):
        clean_stem = Path(job_data["downloaded_file"]).stem.replace("_raw", "")
        paths_to_check.extend(list(workspace_dir.glob(f"{clean_stem}_vi.mp4")))
        paths_to_check.extend(list(workspace_dir.glob(f"{clean_stem}_vi.srt")))

    for p in paths_to_check:
        try:
            if p.exists() and p.is_file():
                p.unlink()
                deleted_files.append(str(p))
                print(f"[SheetQueue] Đã xóa file: {p}")
        except Exception as e:
            print(f"[SheetQueue] Cảnh báo lỗi xóa file {p}: {e}")

    return deleted_files


def reset_failed_job_in_sheet(job_id: str, row_idx: int, note_suffix: str = ""):
    """Reset trạng thái job trên Sheet khi đánh giá chưa đạt để chuẩn bị render lại."""
    now_str = time.strftime("%H:%M %d/%m")
    new_note = f"Đã xóa video cũ ({now_str})"
    if note_suffix:
        new_note += f" - {note_suffix}"

    update_job_status(
        job_id=job_id,
        row_idx=row_idx,
        status="⏳ Đã xóa video cũ - Sẵn sàng render lại",
        progress="10%",
        rendered_file="",
        drive_path="",
        note=new_note
    )

