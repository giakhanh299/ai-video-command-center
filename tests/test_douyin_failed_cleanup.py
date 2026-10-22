import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import douyin_failed_cleanup as cleanup


@pytest.fixture
def job(tmp_path, monkeypatch):
    root = tmp_path / 'work'
    work = root / 'KENH_001_123_abcdef123456'
    work.mkdir(parents=True)
    data = dict(id='123', channel='KENH_001', input_sha256='source',
                config_sha256='abcdef123456', work=str(work))
    (work / 'job.json').write_text(json.dumps(data))
    (work / 'process_evidence.json').write_text(json.dumps(dict(
        worker_observed=True, worker_exited=True, identities={'12345': 1})))
    for name in ('output.mp4', 'voice.wav', 'worker.log', 'translated.srt'):
        (work / name).write_bytes(b'test')
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE renders(id, state, channel, input_sha, config_sha, path)')
    db.execute('INSERT INTO renders VALUES(?,?,?,?,?,?)',
               ('123', 'FAILED', 'KENH_001', 'source', 'abcdef123456', None))
    monkeypatch.setattr(cleanup, 'processes_stopped', lambda *a: True)
    return db, root, work


def test_failed_media_removed_and_diagnostics_kept(job):
    db, root, work = job
    report = cleanup.cleanup_failed(db, root, work)
    assert len(report['deleted']) == 2 and report['bytes'] == 8
    assert (work / 'job.json').exists() and (work / 'worker.log').exists()
    assert (work / 'translated.srt').exists()
    assert (work / 'cleanup_history.jsonl').exists()


@pytest.mark.parametrize('state', ['RUNNING', 'COMPLETED', 'UNKNOWN'])
def test_only_failed_state_can_be_cleaned(job, state):
    db, root, work = job
    db.execute('UPDATE renders SET state=?', (state,))
    assert not cleanup.cleanup_failed(db, root, work)['deleted']
    assert (work / 'output.mp4').exists()


def test_live_child_blocks_cleanup(job, monkeypatch):
    db, root, work = job
    monkeypatch.setattr(cleanup, 'processes_stopped', lambda *a: False)
    assert not cleanup.cleanup_failed(db, root, work)['deleted']


def test_receipt_requires_reconciliation(job):
    db, root, work = job
    (work / 'result.json').write_text('{}')
    assert not cleanup.cleanup_failed(db, root, work)['deleted']


def test_outside_root_is_never_cleaned(job, tmp_path):
    db, root, work = job
    assert not cleanup.cleanup_failed(db, tmp_path / 'other', work)['deleted']


def test_missing_or_live_process_evidence_is_rejected(monkeypatch, tmp_path):
    assert not cleanup.processes_stopped({}, tmp_path)
    class Live:
        def create_time(self): return 10
        def is_running(self): return True
    monkeypatch.setattr(cleanup.psutil, 'Process', lambda _: Live())
    assert not cleanup.processes_stopped(dict(worker_observed=True,
        worker_exited=True, identities={'42': 10}), tmp_path)


def test_orphan_encoder_blocks_cleanup(monkeypatch, tmp_path):
    class Encoder:
        def name(self): return 'ffmpeg.exe'
    monkeypatch.setattr(cleanup.psutil, 'process_iter', lambda: [Encoder()])
    assert not cleanup.processes_stopped(dict(worker_observed=True,
        worker_exited=True, identities={}), tmp_path)


def test_permission_error_blocks_cleanup(monkeypatch, tmp_path):
    def denied(): raise cleanup.psutil.AccessDenied()
    monkeypatch.setattr(cleanup.psutil, 'process_iter', denied)
    assert not cleanup.processes_stopped(dict(worker_observed=True,
        worker_exited=True, identities={}), tmp_path)
