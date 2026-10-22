"""Durable render-to-UPVIDEO handoff; the existing sync daemon owns uploads."""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

SHEET_ID = '1SjckP4y6sbKw1b_YGyUhX8gyYHxEvMJnX-Y6exXDTIE'
SHEET_URL = 'https://docs.google.com/spreadsheets/d/' + SHEET_ID + '/edit#gid=1724102601'
STATE = Path(__file__).resolve().parents[1] / 'outputs/upvideo_handoff'


def state_path(video):
    key = hashlib.sha256(str(Path(video).resolve()).casefold().encode()).hexdigest()
    return STATE / (key + '.json')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as f:
        temp = Path(f.name)
        f.write(json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def enqueue(video):
    video = Path(video).resolve()
    if video.parent.name != '02_MOI_RENDER_CHO_XAC_NHAN' or not video.is_file():
        raise ValueError('FINISHED_REVIEW_VIDEO_REQUIRED')
    path = state_path(video)
    if path.exists():
        prior = json.loads(path.read_text(encoding='utf-8'))
        if prior.get('size') == video.stat().st_size:
            return path
    write(path, {'status': 'PENDING_SYNC', 'path': str(video), 'size': video.stat().st_size,
                 'sheet_id': SHEET_ID, 'sheet_url': SHEET_URL, 'created': time.time(),
                 'approved': False, 'publish_permission': 'NONE'})
    return path


def acknowledge(video, url, row):
    """Called only after the daemon has re-read the destination row successfully."""
    path = state_path(video)
    value = {'status': 'SYNCED', 'path': str(Path(video).resolve()),
             'size': Path(video).stat().st_size, 'drive_url': url, 'row': row,
             'sheet_id': SHEET_ID, 'sheet_url': SHEET_URL + '&range=A' + str(row) + ':L' + str(row),
             'approved': False, 'publish_permission': 'NONE'}
    if path.exists():
        prior = json.loads(path.read_text(encoding='utf-8'))
        if all(prior.get(k) == v for k, v in value.items()):
            return
    value['verified_at'] = time.time()
    write(path, value)
