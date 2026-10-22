import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'backend'))
import upvideo_handoff as handoff


@pytest.fixture
def video(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, 'STATE', tmp_path / 'state')
    p = tmp_path / 'channel' / '02_MOI_RENDER_CHO_XAC_NHAN' / 'video.mp4'
    p.parent.mkdir(parents=True)
    p.write_bytes(b'complete video')
    return p


def test_render_enqueued_without_approval_or_publishing(video):
    path = handoff.enqueue(video)
    r = json.loads(path.read_text(encoding='utf-8'))
    assert r['status'] == 'PENDING_SYNC'
    assert r['sheet_id'] == '1SjckP4y6sbKw1b_YGyUhX8gyYHxEvMJnX-Y6exXDTIE'
    assert r['approved'] is False and r['publish_permission'] == 'NONE'


def test_queue_and_confirmation_are_idempotent(video):
    path = handoff.enqueue(video)
    handoff.acknowledge(video, 'https://drive.google.com/file/d/test/view', 110)
    before = path.read_bytes()
    handoff.enqueue(video)
    handoff.acknowledge(video, 'https://drive.google.com/file/d/test/view', 110)
    assert path.read_bytes() == before
    assert json.loads(before)['status'] == 'SYNCED'


def test_source_video_cannot_be_enqueued(video):
    source = video.parent.parent / '01_CHUA_RENDER' / 'video.mp4'
    source.parent.mkdir()
    source.write_bytes(b'source')
    with pytest.raises(ValueError):
        handoff.enqueue(source)


def test_caption_handoff_queues_finished_video(video):
    from caption_handoff import save_caption
    save_caption(video, 'Caption nháp')
    assert json.loads(handoff.state_path(video).read_text(encoding='utf-8'))['status'] == 'PENDING_SYNC'
