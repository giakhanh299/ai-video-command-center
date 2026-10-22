"""Consolidate verified Douyin sidecars; never touch original/published videos."""
import json
import os
import sqlite3
import stat
from pathlib import Path

from render_douyin_intake import FB, RUNTIME, atomic, digest, probe
from autopilot.locks import CrossProcessFileLock
from backend.render_storage import render_receipt_path


def safe(path):
    return not (path.is_symlink() or (path.exists() and
        getattr(path.stat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def move_verified(source, target):
    if not source.is_file() or not safe(source) or not safe(target):
        raise ValueError('UNSAFE_SIDECAR')
    content = source.read_bytes()
    if target.exists():
        if target.read_bytes() != content:
            raise ValueError('SIDECAR_CONFLICT')
    else:
        with target.open('xb') as stream:
            stream.write(content)
    if target.read_bytes() != content or source.read_bytes() != content:
        raise ValueError('SIDECAR_CHANGED')
    source.unlink()


def tidy_one(video, vid, channel, input_sha, config_sha):
    video = Path(video)
    if not video.is_file() or video.parent.name != '02_MOI_RENDER_CHO_XAC_NHAN':
        raise ValueError('NOT_IN_REVIEW')
    grouped = video.parent / '.render_metadata'
    if not all(safe(p) for p in (video, video.parent, video.parent.parent, grouped)):
        raise ValueError('UNSAFE_PATH')
    receipt_path = render_receipt_path(video)
    if not safe(receipt_path):
        raise ValueError('UNSAFE_RECEIPT')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if (receipt.get('id') != vid or receipt.get('channel') != channel
            or receipt.get('input_sha256') != input_sha
            or receipt.get('config_sha256') != config_sha
            or receipt.get('publish_permission') != 'NONE'
            or receipt.get('status') != 'RENDERED_PENDING_REVIEW'
            or Path(receipt.get('path', '')).resolve() != video.resolve()
            or receipt.get('output_sha256') != digest(video) or probe(video) <= 0):
        raise ValueError('RECEIPT_VERIFICATION_FAILED')
    grouped.mkdir(exist_ok=True)
    moved = []
    for source in (video.with_suffix('.render.json'), video.with_suffix('.srt')):
        if source.exists():
            target = grouped / source.name
            move_verified(source, target)
            moved.append({'from': str(source), 'to': str(target)})
    return moved


def main():
    report = {'moved': [], 'skipped': [], 'videos_deleted': 0}
    channels = json.loads((FB / 'config/channels.json').read_text(encoding='utf-8-sig'))
    roots = {c['channel_id']: Path(c['workspace_root']).resolve() for c in channels}
    with CrossProcessFileLock(FB / 'runtime/locks/gpu_renderer.lock', timeout_seconds=0):
        with sqlite3.connect('file:' + str(RUNTIME / 'renders.sqlite') + '?mode=ro', uri=True) as db:
            for vid, ch, path, sha, config in db.execute(
                    "SELECT id,channel,path,input_sha,config_sha FROM renders WHERE state='COMPLETED'"):
                try:
                    if Path(path).parent.resolve() != roots[ch] / '02_MOI_RENDER_CHO_XAC_NHAN':
                        raise ValueError('CHANNEL_PATH_MISMATCH')
                    report['moved'].extend(tidy_one(path, vid, ch, sha, config))
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    report['skipped'].append({'id': vid, 'reason': str(exc)[:150]})
        atomic(RUNTIME / 'review_tidy_report.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
