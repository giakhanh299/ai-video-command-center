"""
Render lai 3 job cu - cap nhat sheet chinh xac
"""
import sys, io, os, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.chdir(str(__import__('pathlib').Path(__file__).resolve().parent.parent))

import sheet_queue_manager
import telegram_bot

FORCE_WORKFLOW = "cauhinh3"

# Doc lai sheet de lay dung row_idx hien tai
print("Doc sheet lay row index moi nhat...")
all_jobs = sheet_queue_manager.get_all_jobs_from_sheet()
print(f"Tong so jobs: {len(all_jobs)}")
for j in all_jobs:
    print(f"  Row {j['row_idx']}: {j['job_id']} | {j.get('status','')} | review={j.get('user_review','')[:30]}")

# Tim 3 jobs can render lai theo job_id
TARGET_JOB_IDS = [
    "job_1790676935260",  # row 2
    "job_1790679269319",  # row 3
    "job_1790679327312",  # row 4
]

jobs_to_do = [j for j in all_jobs if j.get('job_id') in TARGET_JOB_IDS]
print(f"\nTim thay {len(jobs_to_do)} jobs can render lai")

for j in jobs_to_do:
    job_id  = j["job_id"]
    row_idx = j["row_idx"]
    url     = j.get("source_url", "")
    chat_id = j.get("chat_id") or "-1004439918026"

    print(f"\n{'─'*50}")
    print(f"Job: {job_id} (Row {row_idx})")
    print(f"Link: {url}")

    # Cap nhat trang thai
    sheet_queue_manager.update_job_status(
        job_id=job_id,
        row_idx=row_idx,
        status="🔄 Render lại C3 (Hoài My)...",
        progress="10%",
        rendered_file="",
        drive_path="",
        note=f"Render lai C3 luc {time.strftime('%H:%M %d/%m')}"
    )
    print(f"  Sheet updated -> 10%")

    try:
        telegram_bot.handle_video_download(
            chat_id=chat_id,
            message_id=None,
            text=url,
            override_workflow=FORCE_WORKFLOW,
            job_id=job_id,
            sheet_row=row_idx
        )
        print(f"XONG: {job_id}")
    except Exception as e:
        print(f"LOI: {job_id} - {e}")
        sheet_queue_manager.update_job_status(
            job_id=job_id, row_idx=row_idx,
            status="🔴 Lỗi render lại", progress="ERROR",
            note=str(e)[:120]
        )

print("\n=== HOAN THANH 3 JOBS ===")
