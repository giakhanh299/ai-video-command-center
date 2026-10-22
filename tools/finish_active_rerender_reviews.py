"""Finish reviews for jobs already running in the pre-fix bot, without restarting it."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import sheet_queue_manager as queue

MARKER = "Đang thực hiện yêu cầu"

def main():
    pending = {}
    for job in queue.get_all_jobs_from_sheet():
        review = job['user_review'].lower()
        status = job['status'].lower()
        if ('chưa đạt' in review or 'render lại' in review) and 'đang' in status:
            pending[job['job_id']] = job['row_idx']
            queue.update_job_status(job['job_id'], row_idx=job['row_idx'], user_review=MARKER)
    print(f"Tracking {len(pending)} active requests", flush=True)
    while pending:
        for job in queue.get_all_jobs_from_sheet():
            job_id = job['job_id']
            if job_id not in pending:
                continue
            if job['user_review'] != MARKER:
                pending.pop(job_id)
                continue
            status = job['status'].lower()
            if 'thành công' in status and job['progress'] == '100%' and job['rendered_file']:
                queue.update_job_status(job_id, row_idx=job['row_idx'], user_review="Đã render")
                print(f"Completed {job_id}", flush=True)
                pending.pop(job_id)
            elif 'thất bại' in status or 'lỗi' in status:
                queue.update_job_status(job_id, row_idx=job['row_idx'], user_review="Render lỗi — cần kiểm tra")
                pending.pop(job_id)
        if pending:
            time.sleep(20)

if __name__ == '__main__':
    main()
