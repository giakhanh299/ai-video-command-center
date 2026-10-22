import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _cfg():
    return json.loads((ROOT / "backend" / "channels_config.json").read_text(encoding="utf-8"))

def test_legacy_config3_wuby_ai_background_strategy():
    p = _cfg()["presets"]["cauhinh3_wuby"]
    assert p["workflow"] == "wuby"
    assert p["dialogue_replace"]["strategy"] == "ai_first"
    assert p["dialogue_replace"]["mask_source"] == "whisper_segments"
    assert p["keep_bg_audio"] is True
    assert p["dialogue_replace"]["mute_original_speech"] is True


def test_config3_movie_background_strategy():
    p = _cfg()["presets"]["cauhinh3"]
    assert p["workflow"] == "movie_clone"
    assert p["bg_volume"] == 0.7
    assert p["dialogue_replace"]["strategy"] == "surround_first"
    assert p["dialogue_replace"]["mute_original_speech"] is True

def test_config4_surround_first_strategy():
    p = _cfg()["presets"]["cauhinh4"]
    assert p["workflow"] == "wuby"
    assert p["dialogue_replace"]["strategy"] == "surround_first"
    assert p["dialogue_replace"]["surround_min_channels"] == 6
    assert p["dialogue_replace"]["mask_source"] == "whisper_segments"
    assert p["dialogue_replace"]["mute_original_speech"] is True
    assert p["dialogue_replace"]["speech_cleanup"] is True

def test_audio_switch_has_probe_and_segment_mask():
    text = (ROOT / "backend" / "audio_voice_switch.py").read_text(encoding="utf-8")
    assert "def probe_audio_stream" in text
    assert "def build_segment_activity_masks" in text
    assert "surround_center_omit" in text
