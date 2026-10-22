import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
import tidy_douyin_review as tidy
from backend.render_storage import render_receipt_path


@pytest.fixture
def review(tmp_path, monkeypatch):
    folder = tmp_path / 'KENH_001' / '02_MOI_RENDER_CHO_XAC_NHAN'
    folder.mkdir(parents=True)
    video = folder / 'title__123.mp4'
    video.write_bytes(b'video')
    video.with_suffix('.srt').write_text('subtitles')
    video.with_suffix('.render.json').write_text(json.dumps(dict(id='123', channel='KENH_001',
        input_sha256='source', config_sha256='config', publish_permission='NONE',
        status='RENDERED_PENDING_REVIEW', path=str(video), output_sha256=tidy.digest(video))))
    monkeypatch.setattr(tidy, 'probe', lambda _: 10)
    return video


def test_sidecars_consolidated_idempotently(review):
    assert len(tidy.tidy_one(review, '123', 'KENH_001', 'source', 'config')) == 2
    assert review.read_bytes() == b'video'
    assert not review.with_suffix('.srt').exists()
    assert render_receipt_path(review).is_file()
    assert (review.parent / '.render_metadata' / review.with_suffix('.srt').name).read_text() == 'subtitles'
    assert tidy.tidy_one(review, '123', 'KENH_001', 'source', 'config') == []


def test_changed_video_not_touched(review):
    review.write_bytes(b'changed')
    with pytest.raises(ValueError, match='VERIFICATION'):
        tidy.tidy_one(review, '123', 'KENH_001', 'source', 'config')
    assert review.with_suffix('.render.json').exists()
    assert review.with_suffix('.srt').exists()


def test_conflicting_metadata_never_overwritten(review):
    folder = review.parent / '.render_metadata'
    folder.mkdir()
    (folder / review.with_suffix('.srt').name).write_text('independent subtitles')
    with pytest.raises(ValueError, match='CONFLICT'):
        tidy.tidy_one(review, '123', 'KENH_001', 'source', 'config')
    assert review.with_suffix('.srt').read_text() == 'subtitles'


def test_legacy_receipt_reader_and_new_writer(review):
    assert render_receipt_path(review) == review.with_suffix('.render.json')
    assert render_receipt_path(review, for_write=True).parent.name == '.render_metadata'
