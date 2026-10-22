"""Run one already-requested scan cycle after its durable six-hour deadline.

This is a bounded invocation, not a recurring scheduler. It never retries render
jobs and the existing renderer owns the shared GPU lock.
"""
import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from scan_followed_douyin import RUNTIME, CrossProcessFileLock


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def main(tag):
    if not tag.replace('_', '').isalnum():
        raise ValueError('INVALID_CYCLE_TAG')
    prefix = RUNTIME / ('scheduled_' + tag)
    journal_path = Path(str(prefix) + '_completion.json')
    with CrossProcessFileLock(RUNTIME / 'scheduled_cycle.lock', timeout_seconds=0):
        if journal_path.exists():
            raise RuntimeError('CYCLE_ALREADY_RECORDED_RECONCILE_FIRST')
        with sqlite3.connect(RUNTIME / 'history.sqlite') as db:
            scans = db.execute('SELECT last_scan FROM runs').fetchall()
        deadline = max([stamp + 6 * 3600 for (stamp,) in scans] or [time.time()]) + 1
        if deadline - time.time() > 600:
            raise RuntimeError('CYCLE_NOT_WITHIN_DUE_WINDOW')
        proc = psutil.Process()
        journal = dict(status='WAITING_UNTIL_DUE', pid=proc.pid, created=proc.create_time(),
                       due_at=deadline, started=time.time(), publish_permission='NONE')
        save(journal_path, journal)
        while time.time() < deadline:
            time.sleep(min(30, max(0, deadline - time.time())))
        for stage, script, extra in [
            ('SCAN', 'scan_followed_douyin.py', []),
            ('RETRY_DOWNLOADS', 'scan_followed_douyin.py', ['--retry-failed']),
            ('RENDER', 'render_douyin_intake.py', []),
        ]:
            journal.update(status=stage, updated=time.time())
            save(journal_path, journal)
            log_path = Path(str(prefix) + '_' + stage.lower() + '.log')
            with log_path.open('xb') as log:
                child = subprocess.Popen([sys.executable, '-X', 'utf8',
                                          str(ROOT / 'tools' / script), *extra],
                                         cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                journal.update(child_pid=child.pid, child_created=psutil.Process(child.pid).create_time())
                save(journal_path, journal)
                code = child.wait()
            if code:
                journal.update(status='FAILED_REVIEW_LOG', failed_stage=stage,
                               exit_code=code, finished=time.time())
                save(journal_path, journal)
                return
            if stage != 'RENDER':
                result = json.loads((RUNTIME / 'latest_report.json').read_text(encoding='utf-8'))
                save(Path(str(prefix) + '_' + stage.lower() + '_report.json'), result)
                if result.get('status') == 'BUSY_ANOTHER_SCAN':
                    journal.update(status='DEFERRED_ANOTHER_SCAN', finished=time.time())
                    save(journal_path, journal)
                    return
            else:
                journal['renderer_result'] = ('GPU_BUSY' if '"GPU_BUSY"' in log_path.read_text(encoding='utf-8')
                                               else 'FINISHED_PENDING_ARTIFACT_VERIFICATION')
        journal.update(status='FINISHED_PENDING_VERIFICATION', finished=time.time())
        save(journal_path, journal)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    main(parser.parse_args().tag)
