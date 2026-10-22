import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_cfg():
    return json.loads((ROOT / 'backend' / 'channels_config.json').read_text(encoding='utf-8'))


def test_legacy_config3_wuby_has_ai_audio_hard_replace():
    cfg = load_cfg()
    c3 = cfg['presets']['cauhinh3_wuby']
    assert c3['workflow'] == 'wuby'
    assert c3['render_profile'] == 'wuby_overlay'
    assert c3['mask_mode'] == 'in_video_overlay'
    assert c3['dialogue_replace']['strategy'] == 'ai_first'
    assert c3['dialogue_replace']['mute_original_speech'] is True


def test_config3_matches_facebook_movie_clone_route():
    c3 = load_cfg()['presets']['cauhinh3']
    assert c3['workflow'] == 'movie_clone'
    assert c3['render_profile'] == 'movie_clone_blur'
    assert c3['mask_mode'] == 'blur_sub_black'
    assert c3['_logo_type'] == 'kenh_005_vutrucayphim'
    assert c3['dialogue_replace']['mute_original_speech'] is True


def test_config4_is_wuby_visual_with_surround_two_stage_hard_replace():
    cfg = load_cfg()
    c4 = cfg['presets']['cauhinh4']
    assert c4['workflow'] == 'wuby'
    assert c4['render_profile'] == 'wuby_overlay'
    assert c4['mask_mode'] == 'in_video_overlay'
    assert c4['dialogue_replace']['strategy'] == 'surround_first'
    assert c4['dialogue_replace']['mute_original_speech'] is True
    assert c4['dialogue_replace']['speech_cleanup'] is True
    assert c4['dialogue_replace']['mask_source'] == 'whisper_segments'


def test_wuby_overlay_text_is_smaller_than_previous_build():
    cfg = load_cfg()
    sub = cfg['render_profiles']['wuby_overlay']['subtitle']
    assert sub['min_font_size'] <= 26
    assert sub['max_font_size'] <= 44
