"""One bounded, audited rerender of the explicitly rejected Douyin artifact."""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from render_douyin_intake import FB, RUNTIME, WORK, atomic, digest, probe
from autopilot.locks import CrossProcessFileLock
from backend.render_storage import render_receipt_path

VID = '7696450506177634929'
CHANNEL = 'KENH_007'
REPORT = RUNTIME / 'qc_repair_run.json'


def renderer_processes():
    active = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if proc.pid == psutil.Process().pid:
                continue
            if (proc.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe'):
                continue
            args = proc.info['cmdline'] or []
            if any(Path(a).name in ('render_douyin_intake.py', 'finish_douyin_batch.py',
                                   'repair_douyin_qc_batch.py') for a in args):
                active.append({'pid': proc.pid, 'created': proc.info['create_time']})
        except (psutil.Error, OSError):
            continue
    return active


def main(attempt=1):
    report_path = REPORT if attempt == 1 else RUNTIME / 'qc_repair_run_02.json'
    requests_path = RUNTIME / 'qc_rerender_requests.json'
    requests = json.loads(requests_path.read_text(encoding='utf-8'))
    request = next(r for r in requests if r['id'] == VID and r['channel'] == CHANNEL)
    if request['status'] != 'QC_REJECTED_NEEDS_RERENDER':
        raise RuntimeError('QC_REQUEST_NOT_PENDING')
    if report_path.exists():
        raise RuntimeError('QC_ATTEMPT_ALREADY_RECORDED_RECONCILE_FIRST')
    active = renderer_processes()
    if active:
        raise RuntimeError('RENDERER_STILL_ACTIVE')
    with CrossProcessFileLock(FB / 'runtime/locks/gpu_renderer.lock', timeout_seconds=0):
        active = renderer_processes()
        if active:
            raise RuntimeError('RENDERER_STILL_ACTIVE')
        base_name = CHANNEL + '_' + VID + '_7fe18edb650d'
        old_work = WORK / (base_name if attempt == 1 else base_name + '_qc_fixed_01')
        job = json.loads((old_work / 'job.json').read_text(encoding='utf-8'))
        rejected = Path(request['rejected_output']).resolve()
        assert rejected.parent.name == '02_MOI_RENDER_CHO_XAC_NHAN'
        assert rejected.parent.parent.parent == Path(r'D:\0.1_FACE_BOOK\videos_upload').resolve()
        assert rejected.parent.parent.name.startswith(CHANNEL + '_')
        assert digest(rejected) == request['rejected_output_sha256']
        assert digest(Path(job['source'])) == job['input_sha256']
        assert job['id'] == VID and job['channel'] == CHANNEL
        with sqlite3.connect(RUNTIME / 'renders.sqlite') as db:
            prior = db.execute('SELECT state,path,input_sha,config_sha FROM renders WHERE id=?', (VID,)).fetchone()
        assert prior == ('COMPLETED', str(rejected), job['input_sha256'], job['config_sha256'])
        # Preserve the original work and all original outputs; use a fresh job directory.
        work = WORK / (base_name + '_qc_fixed_' + str(attempt).zfill(2))
        assert work.resolve().parent == WORK.resolve()
        work.mkdir(exist_ok=False)
        for name in ('translated.srt', 'translated.orig.srt', 'preflight.json', 'preflight_binding.json'):
            source = old_work / name
            if source.is_file():
                shutil.copy2(source, work / name)
        if (old_work / '.cache').is_dir():
            shutil.copytree(old_work / '.cache', work / '.cache')
        job['work'] = str(work)
        atomic(work / 'job.json', job)
        report = {'id': VID, 'channel': CHANNEL, 'status': 'RUNNING',
                  'pid': psutil.Process().pid, 'created': psutil.Process().create_time(),
                  'work': str(work), 'previous_output_sha256': request['rejected_output_sha256'],
                  'publish_permission': 'NONE', 'started': time.time()}
        atomic(report_path, report)
        with (work / 'worker.log').open('wb') as log:
            child = subprocess.Popen([sys.executable, '-X', 'utf8',
                                     str(ROOT / 'tools/render_douyin_intake.py'),
                                     '--job', str(work / 'job.json')], cwd=ROOT,
                                     stdout=log, stderr=subprocess.STDOUT)
            report.update(worker_pid=child.pid, worker_created=psutil.Process(child.pid).create_time())
            atomic(report_path, report)
            # One attempt only. The heartbeat observes this worker; no automatic replay.
            code = child.wait()
        if code:
            report.update(status='FAILED_REVIEW_LOG', exit_code=code, finished=time.time())
            atomic(report_path, report)
            return
        receipt = json.loads((work / 'result.json').read_text(encoding='utf-8'))
        final = Path(receipt['path']).resolve()
        assert final.parent == rejected.parent and final != rejected
        assert receipt['id'] == VID and receipt['channel'] == CHANNEL
        assert receipt['publish_permission'] == 'NONE'
        assert receipt['input_sha256'] == job['input_sha256']
        assert receipt['config_sha256'] == job['config_sha256']
        assert digest(final) == receipt['output_sha256']
        assert receipt['output_sha256'] != request['rejected_output_sha256']
        assert abs(probe(final) - receipt['duration']) < .1
        assert digest(Path(job['source'])) == job['input_sha256']
        assert digest(rejected) == request['rejected_output_sha256']
        # Quarantine only the positively identified rejected artifact and its sidecars.
        quarantine = rejected.parent.parent / '99_FAILED' / ('QC_REJECTED_' + VID + ('' if attempt == 1 else '_02'))
        assert quarantine.resolve().is_relative_to(rejected.parent.parent.resolve())
        quarantine.mkdir(parents=True, exist_ok=False)
        for source in (rejected, render_receipt_path(rejected), rejected.with_suffix('.srt')):
            if source.exists():
                source.rename(quarantine / source.name)
        with sqlite3.connect(RUNTIME / 'renders.sqlite') as db:
            cursor = db.execute("UPDATE renders SET path=?,updated=?,error=NULL WHERE id=? AND state='COMPLETED' AND path=?",
                                (str(final), time.time(), VID, str(rejected)))
            assert cursor.rowcount == 1
        request.update(status='RERENDERED_PENDING_VISUAL_REVIEW',
                       repaired_output=str(final), repaired_output_sha256=receipt['output_sha256'],
                       quarantine=str(quarantine), repaired_at=time.time())
        atomic(requests_path, requests)
        report.update(status='RERENDERED_PENDING_VISUAL_REVIEW', path=str(final),
                      output_sha256=receipt['output_sha256'], quarantine=str(quarantine), finished=time.time())
        atomic(report_path, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=int, choices=[1, 2], default=1)
    main(parser.parse_args().attempt)
