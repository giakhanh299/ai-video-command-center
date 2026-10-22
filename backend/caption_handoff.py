"""Persist the caption already generated for a finished video, without publishing."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def save_caption(video, caption):
    video = Path(video)
    if not isinstance(caption, str) or not caption.strip():
        return None
    if not video.is_file() or video.suffix.lower() != '.mp4':
        raise ValueError('CAPTION_REQUIRES_FINISHED_MP4')
    digest = hashlib.sha256()
    with video.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    payload = {'video_sha256': digest.hexdigest(), 'caption': caption.strip(),
               'caption_source': 'lay_video_tiktok.generate_movie_caption', 'approved': False}
    target = video.with_suffix(video.suffix + '.caption.json')
    if target.exists():
        if json.loads(target.read_text(encoding='utf-8')) != payload:
            raise ValueError('CAPTION_HANDOFF_CONFLICT')
        from upvideo_handoff import enqueue
        enqueue(video)
        return target
    with tempfile.NamedTemporaryFile(dir=video.parent, prefix='.caption-', suffix='.tmp', delete=False) as stream:
        staging = Path(stream.name)
        stream.write(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(staging, target)
    finally:
        staging.unlink(missing_ok=True)
    from upvideo_handoff import enqueue
    enqueue(video)
    return target
