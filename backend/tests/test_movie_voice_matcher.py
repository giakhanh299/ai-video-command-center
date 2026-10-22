import json
from pathlib import Path

import movie_voice_matcher
from sub_processor import SubtitleSegment

ROOT = Path(__file__).resolve().parents[2]


def load_cfg():
    return json.loads((ROOT / 'backend' / 'channels_config.json').read_text(encoding='utf-8'))


def test_numbered_configs_keep_facebook_single_narrator_routes():
    presets = load_cfg()['presets']
    assert presets['cauhinh2']['workflow'] == 'film_review_black'
    assert presets['cauhinh2']['mask_mode'] == 'black_bar'
    assert presets['cauhinh3']['workflow'] == 'movie_clone'
    assert presets['cauhinh3']['mask_mode'] == 'blur_sub_black'
    for name in ('cauhinh2', 'cauhinh3'):
        assert not presets[name].get('movie_voice_match', {}).get('enabled', False)
    for name in ('cauhinh3_wuby', 'cauhinh4'):
        assert presets[name]['workflow'] == 'wuby'
        assert presets[name]['movie_voice_match']['enabled'] is True
        assert len(presets[name]['movie_voice_match']['voice_bank']) >= 6


def test_existing_wuby_cue_matches_bundled_pitch_bank():
    cfg = load_cfg()
    mc = cfg['presets']['cauhinh3_wuby']['movie_voice_match']
    src = ROOT / 'tests' / 'c2_wuby_raw.wav'
    if not src.exists():
        return
    seg = [SubtitleSegment(0.0, 2.57, 'Em gái dễ thương đang nói chuyện vui vẻ')]
    report = movie_voice_matcher.match_whisper_segments(
        str(src), seg, seg, config_data=cfg, cfg=mc
    )
    row = report['source_segments'][0]
    assert abs(row['source_f0']['median_f0_hz'] - 238.81) < 5
    assert row['profile'] == 'omni_nu_cute'


def test_octave_correction_prefers_stable_cluster_pitch():
    v = movie_voice_matcher._canonical_cluster_f0([120.0, 240.0, 125.0], 70.0, 420.0, True)
    assert v is not None
    assert 115.0 <= v <= 135.0
