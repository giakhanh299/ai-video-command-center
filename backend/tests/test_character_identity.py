import json
from pathlib import Path

import character_identity
import movie_voice_matcher

ROOT = Path(__file__).resolve().parents[2]


def load_cfg():
    return json.loads((ROOT / "backend" / "channels_config.json").read_text(encoding="utf-8"))


def test_movie_workflow_and_wuby_enable_character_id_and_ambiguity_only_asd():
    cfg = load_cfg()
    c2 = cfg["workflows"]["movie_clone"]["settings"]["movie_voice_match"]["character_identity"]
    wuby = cfg["presets"]["wuby"]["wuby_preflight"]["voice_match"]["character_identity"]
    for ci in (c2, wuby):
        assert ci["enabled"] is True
        assert ci["backend"] == "wespeaker"
        assert ci["model"] == "chinese"
        assert ci["light_asd"]["enabled"] is True
        assert ci["light_asd"]["ambiguity_only"] is True


def test_diarization_keeps_same_character_across_separated_lines():
    segments = [
        {"start": 0.00, "end": 1.00, "text": "A normal"},
        {"start": 1.10, "end": 2.00, "text": "B"},
        {"start": 5.00, "end": 6.00, "text": "A shouting later"},
    ]
    diar = [
        {"start": 0.00, "end": 1.00, "label": "spk_A"},
        {"start": 1.10, "end": 2.00, "label": "spk_B"},
        {"start": 5.00, "end": 6.00, "label": "spk_A"},
    ]
    rows = character_identity._speaker_rows_from_diarization(segments, diar, {})
    assert rows[0]["speaker_id"] == rows[2]["speaker_id"]
    assert rows[0]["speaker_id"] != rows[1]["speaker_id"]
    assert rows[0]["identity_method"] == "wespeaker_overlap"
    assert rows[2]["identity_method"] == "wespeaker_overlap"


def test_character_grouping_is_independent_from_f0_changes():
    # Same Character ID, deliberately extreme F0 difference. It must remain one group.
    records = [
        {
            "index": 0,
            "speaker_id": 7,
            "source_f0": {"median_f0_hz": 95.0},
            "identity_method": "wespeaker_overlap",
            "ambiguous": False,
        },
        {
            "index": 1,
            "speaker_id": 7,
            "source_f0": {"median_f0_hz": 285.0},
            "identity_method": "wespeaker_overlap",
            "ambiguous": False,
        },
    ]
    groups = movie_voice_matcher._clusters_from_locked_identity(records)
    assert len(groups) == 1
    assert groups[0]["id"] == 7
    assert groups[0]["indices"] == [0, 1]
    assert groups[0]["f0s"] == [95.0, 285.0]


def test_light_asd_chunks_only_wrap_ambiguous_rows():
    rows = [
        {"start": 0.0, "end": 1.0, "ambiguous": False},
        {"start": 10.0, "end": 11.0, "ambiguous": True},
        {"start": 30.0, "end": 31.0, "ambiguous": False},
    ]
    chunks = character_identity._ambiguous_chunks(
        rows,
        {"window_padding_sec": 1.0, "merge_gap_sec": 1.0, "max_chunk_sec": 20.0, "max_chunks": 10},
    )
    assert chunks == [(9.0, 12.0)]


def test_first_appearance_renumbering_is_stable():
    rows = [
        {"index": 0, "start": 0.0, "speaker_id": 9},
        {"index": 1, "start": 1.0, "speaker_id": 4},
        {"index": 2, "start": 2.0, "speaker_id": 9},
    ]
    character_identity._renumber_by_first_appearance(rows)
    assert [r["speaker_id"] for r in rows] == [0, 1, 0]
    assert [r["speaker_label"] for r in rows] == ["CHAR_01", "CHAR_02", "CHAR_01"]
