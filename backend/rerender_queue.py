import os
import sys
import time
import shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = str(BASE_DIR.parent)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import sheet_queue_manager
import telegram_bot

def run_rerender_queue(job_id_filter: str = None):
    """Quét và render lại các job có đánh giá 'Chưa đạt xóa video render lại'."""
    print("=" * 60)
    print("🔄 HỆ THỐNG RENDER LẠI THEO ĐÁNH GIÁ GOOGLE SHEET")
    print("=" * 60)

    jobs = sheet_queue_manager.get_all_jobs_from_sheet()
    print(f"Tổng số job trên Sheet: {len(jobs)}")

    jobs_to_rerender = []
    for j in jobs:
        if job_id_filter:
            if j.get("job_id") == job_id_filter:
                jobs_to_rerender.append(j)
            continue
        rev = j.get("user_review", "").lower()
        if "chưa đạt" in rev or "render lại" in rev:
            jobs_to_rerender.append(j)

    if not jobs_to_rerender:
        print("Không có job nào cần render lại.")
        return

    print(f"Phát hiện {len(jobs_to_rerender)} job cần render lại:")
    for j in jobs_to_rerender:
        print(f"  • Row {j['row_idx']} | Job: {j['job_id']} | File: {j.get('rendered_file')} | Đánh giá: {j.get('user_review')}")

    for j in jobs_to_rerender:
        job_id = j["job_id"]
        row_idx = j["row_idx"]
        url = j.get("source_url", "")
        cfg_str = j.get("config", "").lower()
        chat_id = j.get("chat_id") or telegram_bot.GROUP_ID.split(",")[0]

        if "wuby" in cfg_str or "cấu hình 1" in cfg_str:
            workflow = "wuby"
        elif "cấu hình 3" in cfg_str or "cauhinh3" in cfg_str:
            workflow = "cauhinh3"
        elif "cấu hình 4" in cfg_str or "cauhinh4" in cfg_str:
            workflow = "cauhinh4"
        else:
            workflow = "cauhinh2"

        print(f"\n" + "-" * 50)
        print(f"🚀 BẮT ĐẦU XỬ LÝ JOB: {job_id} (Dòng {row_idx})")
        print(f"   Link: {url}")
        print(f"   Cấu hình: {workflow}")
        print("-" * 50)

        # 1. Xóa file cũ
        del_files = sheet_queue_manager.delete_rendered_files_for_job(j, google_drive_base=telegram_bot.GOOGLE_DRIVE_DIR)
        print(f"-> Đã xóa {len(del_files)} file cũ.")

        # 2. Cập nhật trạng thái
        sheet_queue_manager.update_job_status(
            job_id=job_id,
            row_idx=row_idx,
            status="🔄 Đang Render lại...",
            progress="15%",
            rendered_file="",
            drive_path="",
            note=f"Render lại lúc {time.strftime('%H:%M %d/%m')}"
        )

        # 3. Chạy render lại
        try:
            telegram_bot.handle_video_download(
                chat_id=chat_id,
                message_id=None,
                text=url,
                override_workflow=workflow,
                job_id=job_id,
                sheet_row=row_idx
            )
            print(f"✅ Hoàn thành render lại Job {job_id}!")
        except Exception as e:
            print(f"❌ Lỗi khi render lại Job {job_id}: {e}")
            sheet_queue_manager.update_job_status(
                job_id=job_id,
                row_idx=row_idx,
                status="🔴 Lỗi khi render lại",
                progress="ERROR",
                note=str(e)[:100]
            )

if __name__ == "__main__":
    filter_id = sys.argv[1] if len(sys.argv) > 1 else None
    run_rerender_queue(filter_id)
