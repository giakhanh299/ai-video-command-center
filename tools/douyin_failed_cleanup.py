"""Conservative media-only cleanup; caller must hold the shared GPU lock."""
import json
import stat
import time
from pathlib import Path

import psutil


def remember_tree(child, identities):
    """Sample ownership while the worker is alive; persist PID creation times."""
    try:
        parent = psutil.Process(child.pid)
        for process in [parent, *parent.children(recursive=True)]:
            identities[str(process.pid)] = process.create_time()
        return True
    except (psutil.Error, AttributeError):
        return False


def processes_stopped(evidence, work):
    if not evidence.get('worker_observed') or not evidence.get('worker_exited'):
        return False
    try:
        for pid, created in evidence['identities'].items():
            try:
                p = psutil.Process(int(pid))
                if abs(p.create_time() - created) < .01 and p.is_running():
                    return False
            except psutil.NoSuchProcess:
                pass
        # Orphan encoders may outlive their parent between samples. Do not clean
        # while any encoder or worker referencing this job is still present.
        for p in psutil.process_iter():
            try:
                name = p.name().lower()
                if name in ('ffmpeg', 'ffmpeg.exe'):
                    return False
                if name in ('python', 'python.exe', 'pythonw.exe'):
                    command = ' '.join(p.cmdline()).lower()
                    if str(work).lower() in command:
                        return False
            except psutil.NoSuchProcess:
                continue
        return True
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False


def cleanup_failed(db, work_root, work):
    """No recursive deletion, no sources/delivery paths, no ambiguous receipts."""
    work_root, work = Path(work_root).resolve(), Path(work)
    report = {'work': str(work), 'deleted': [], 'bytes': 0, 'status': 'SKIPPED'}
    try:
        if work.is_symlink() or work.resolve().parent != work_root:
            return report
        work = work.resolve()
        if any(p.is_symlink() or bool(getattr(p.stat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
               for p in (work_root, work)):
            return report
        job = json.loads((work / 'job.json').read_text(encoding='utf-8'))
        row = db.execute('SELECT state,channel,input_sha,config_sha,path FROM renders WHERE id=?',
                         (job['id'],)).fetchone()
        if (not row or row[0] != 'FAILED' or row[1:4] !=
                (job['channel'], job['input_sha256'], job['config_sha256']) or row[4]):
            return report
        if work.name != job['channel'] + '_' + job['id'] + '_' + job['config_sha256'][:12]:
            return report
        if Path(job['work']).resolve() != work or (work / 'result.json').exists():
            return report
        evidence = json.loads((work / 'process_evidence.json').read_text(encoding='utf-8'))
        if not processes_stopped(evidence, work):
            return report
        candidates = []
        for p in work.iterdir():
            if p.suffix.lower() not in ('.mp4', '.wav'):
                continue
            if (p.is_symlink() or not p.is_file() or p.resolve().parent != work
                    or bool(getattr(p.stat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                    or p.stat().st_nlink != 1 or p.with_suffix('.render.json').exists()):
                continue
            candidates.append(p)
        report['status'] = 'COMPLETED'
        for p in candidates:
            # Check durable state again immediately before every deletion.
            if db.execute('SELECT state FROM renders WHERE id=?', (job['id'],)).fetchone() != ('FAILED',):
                report['status'] = 'STATE_CHANGED'
                break
            size = p.stat().st_size
            p.unlink()
            report['deleted'].append(str(p))
            report['bytes'] += size
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report['status'] = 'DEFERRED'
        report['error'] = type(exc).__name__
    if report['status'] != 'SKIPPED':
        audit = work / 'cleanup_history.jsonl'
        with audit.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(report, time=time.time()), ensure_ascii=False) + '\n')
    return report
