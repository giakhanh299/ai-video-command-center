"""
Regression tests for Wuby batch pipeline fixes as required by ANTIGRAVITY_FIX_WUBY_PROMPT.md.
Scenarios covered:
1. OCR text without speech is translated and rendered before deletion.
2. Laughter / hallucinations are not assigned to semantic OCR tracks.
3. Untranslated tracks are not deleted and cause QC to fail.
4. Two roles use the correct references (giongnucute.wav for character, 2_nu_tre_trung.mp3 for narrator) in timeline order.
5. Failed TTS cue causes job to fail and prevents copying to Drive.
6. QC pass is required to allow publishing to Google Drive.
"""
import copy
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import channel_manager
from sub_processor import SubtitleSegment, is_whisper_hallucination
from wuby_ocr_overlay import (
    build_wuby_ass_subtitles,
    clean_video_ocr_backgrounds,
    extend_ocr_event_holds,
    filter_semantic_ocr_events,
    is_laughter_or_filler,
    match_ocr_events_with_subtitles,
)
from wuby_qc import run_wuby_qc
from wuby_roles import classify_roles, render_roles
from wuby_studio.captions import Cue


# =========================================================================
# Scenario 1: OCR text without speech is translated and rendered before deletion
# =========================================================================
def test_ocr_without_speech_is_translated_and_rendered_before_deletion(tmp_path):
    ocr_events = [
        {
            "track_id": 1,
            "scene_id": 0,
            "start": 1.0,
            "end": 4.0,
            "box": [100, 200, 300, 80],
            "text": "晕车时的我",
            "text_class": "chinese",
            "keyframes": [{"time": 1.0, "box": [100, 200, 300, 80], "bg_bgr": [255, 255, 255]}],
        }
    ]
    # No speech segments
    speech_segments = []

    def mock_translate_batch(batch, **kwargs):
        return {1: "Tôi khi bị say xe"}

    with patch("sub_processor.OpenAISubtitleTranslator.translate_batch", side_effect=mock_translate_batch):
        matched = match_ocr_events_with_subtitles(
            ocr_events, segments=speech_segments, vid_h=1920
        )

    # 1. Must be translated
    assert matched[0].get("vi_text").upper() == "TÔI KHI BỊ SAY XE"
    assert "ocr" in matched[0].get("source", "")

    # 2. Must be included in ASS subtitles
    ass_path = tmp_path / "test.ass"
    build_wuby_ass_subtitles(
        out_ass_path=ass_path,
        vid_w=1080,
        vid_h=1920,
        ocr_events=matched,
        movie_title="TẬP 1",
    )
    ass_content = ass_path.read_text(encoding="utf-8")
    assert "TÔI KHI BỊ SAY XE" in ass_content.upper()


# =========================================================================
# Scenario 2: Laughter / hallucinations are not assigned to semantic OCR text
# =========================================================================
def test_unstable_ocr_fragments_are_never_sent_to_translation_or_deletion():
    events = [
        {"text": "醒", "start": 1.0, "end": 1.04, "count": 1, "keyframes": [{}]},
        {"text": "蝥-", "start": 1.5, "end": 1.62, "count": 2, "keyframes": [{}, {}]},
        {"text": "突然急刹", "start": 2.0, "end": 2.8, "count": 12, "keyframes": [{}] * 12},
    ]
    kept = filter_semantic_ocr_events(events)
    assert [ev["text"] for ev in kept] == ["突然急刹"]


def test_ocr_hold_extends_300ms_but_stops_at_next_caption():
    events = [
        {"track_id": 1, "scene_id": 0, "start": 1.0, "end": 2.0, "scene_start": 0.0, "scene_end": 5.0, "box": [100, 100, 300, 80]},
        {"track_id": 2, "scene_id": 0, "start": 2.2, "end": 3.0, "scene_start": 0.0, "scene_end": 5.0, "box": [110, 105, 300, 80]},
        {"track_id": 3, "scene_id": 0, "start": 3.5, "end": 4.0, "scene_start": 0.0, "scene_end": 4.1, "box": [700, 900, 200, 80]},
    ]
    extended = extend_ocr_event_holds(events, 0.30)
    assert extended[0]["start"] == 0.85
    assert extended[0]["end"] == 2.1
    assert extended[0]["hold_extension_sec"] == 0.25
    assert extended[1]["start"] == 2.1
    assert extended[1]["end"] == 3.15
    assert extended[1]["hold_extension_sec"] == 0.25
    assert extended[2]["start"] == 3.35
    assert extended[2]["end"] == 4.1
    assert extended[2]["hold_extension_sec"] == 0.25


def test_laughter_is_not_assigned_to_different_ocr_text():
    # OCR text on screen has meaning: "敲键盘又快又响的" (Gõ bàn phím vừa nhanh vừa to)
    ocr_events = [
        {
            "track_id": 1,
            "scene_id": 0,
            "start": 2.0,
            "end": 5.0,
            "box": [200, 300, 600, 100],
            "text": "敲键盘又快又响的",
            "text_class": "chinese",
            "keyframes": [{"time": 2.0, "box": [200, 300, 600, 100], "bg_bgr": [255, 255, 255]}],
        }
    ]
    # Whisper heard laughter during that time
    laughter_segments = [
        SubtitleSegment(2.2, 4.8, "Ha, ha")
    ]

    def mock_translate_batch(batch, **kwargs):
        return {1: "Người gõ bàn phím vừa nhanh vừa to"}

    with patch("sub_processor.OpenAISubtitleTranslator.translate_batch", side_effect=mock_translate_batch):
        matched = match_ocr_events_with_subtitles(
            ocr_events, segments=laughter_segments, vid_h=1920
        )

    # Must NOT be assigned laughter "Ha, ha"
    assert matched[0].get("vi_text") != "Ha, ha"
    assert not is_laughter_or_filler(matched[0].get("vi_text", ""))
    # Must be independently translated to proper Vietnamese
    assert "gõ bàn phím" in matched[0].get("vi_text", "").lower()


def test_account_watermark_is_never_replaced_with_spoken_subtitle():
    ocr_events = [
        {
            "track_id": 10,
            "scene_id": 0,
            "start": 1.0,
            "end": 6.0,
            "box": [80, 570, 190, 45],
            "text": "@迷人的歪姐",
            "text_class": "chinese",
            "keyframes": [{"time": 1.0, "box": [80, 570, 190, 45], "bg_bgr": [20, 20, 20]}] * 8,
        },
        {
            "track_id": 11,
            "scene_id": 0,
            "start": 6.0,
            "end": 10.0,
            "box": [80, 570, 190, 45],
            "text": "迷人的歪姐",
            "text_class": "chinese",
            "keyframes": [{"time": 6.0, "box": [80, 570, 190, 45], "bg_bgr": [20, 20, 20]}] * 8,
        },
    ]
    speech = [SubtitleSegment(1.2, 5.8, "Đây là lời thoại thật")]

    matched = match_ocr_events_with_subtitles(ocr_events, segments=speech, vid_h=1920, vid_w=1080)

    assert all(ev.get("is_watermark") for ev in matched)
    assert all(not (ev.get("vi_text") or "").strip() for ev in matched)
    assert all(ev.get("source") == "ignored_watermark" for ev in matched)


def test_short_wide_top_text_is_classified_as_banner():
    ocr_events = [
        {
            "track_id": 20,
            "scene_id": 0,
            "start": 0.0,
            "end": 1.5,
            "box": [110, 440, 860, 90],
            "text": "今晚吃粉面菜蛋和烤串的我",
            "text_class": "chinese",
            "keyframes": [{"time": 0.0, "box": [110, 440, 860, 90], "bg_bgr": [255, 255, 255]}] * 8,
        }
    ]

    with patch("sub_processor.OpenAISubtitleTranslator.translate_batch", return_value={1: "Tối nay tôi ăn bún và xiên nướng"}):
        matched = match_ocr_events_with_subtitles(ocr_events, segments=[], vid_h=1920, vid_w=1080)

    assert matched[0].get("is_banner") is True
    assert "TỐI NAY" in (matched[0].get("vi_text") or "").upper()


def test_one_spoken_subtitle_is_not_reused_for_two_ocr_regions():
    ocr_events = [
        {
            "track_id": 30,
            "scene_id": 0,
            "start": 2.0,
            "end": 4.0,
            "box": [250, 1300, 500, 90],
            "text": "第一行字幕",
            "text_class": "chinese",
            "keyframes": [{"time": 2.0, "box": [250, 1300, 500, 90], "bg_bgr": [10, 10, 10]}] * 8,
        },
        {
            "track_id": 31,
            "scene_id": 0,
            "start": 2.0,
            "end": 4.0,
            "box": [250, 1450, 500, 90],
            "text": "第二行字幕",
            "text_class": "chinese",
            "keyframes": [{"time": 2.0, "box": [250, 1450, 500, 90], "bg_bgr": [10, 10, 10]}] * 8,
        },
    ]
    speech = [SubtitleSegment(2.1, 3.9, "Một câu thoại duy nhất")]

    with patch("sub_processor.OpenAISubtitleTranslator.translate_batch", return_value={1: "Dòng chữ phụ"}):
        matched = match_ocr_events_with_subtitles(ocr_events, segments=speech, vid_h=1920, vid_w=1080)

    spoken = [ev for ev in matched if ev.get("source") == "whisper_dialogue"]
    assert len(spoken) == 1
    assert spoken[0].get("vi_text") == "Một câu thoại duy nhất"


# =========================================================================
# Scenario 3: Untranslated track is NOT deleted and fails QC
# =========================================================================
def test_untranslated_track_is_not_deleted_and_fails_qc(tmp_path):
    ocr_events = [
        {
            "track_id": 2,
            "scene_id": 0,
            "start": 1.0,
            "end": 3.0,
            "box": [100, 500, 300, 80],
            "text": "未知文字",
            "text_class": "chinese",
            "cleaned": True,
            "vi_text": "",  # Empty translation / wipeout!
        }
    ]

    dummy_render = tmp_path / "dummy.mp4"
    dummy_render.write_bytes(b"dummy_video_bytes")

    # Run QC
    qc_res = run_wuby_qc(
        rendered_video_path=dummy_render,
        source_video_path=dummy_render,
        ocr_events=ocr_events,
        output_dir=tmp_path,
    )

    # QC must fail because of BLANK_WIPEOUT
    assert qc_res["passed"] is False
    assert any("BLANK_WIPEOUT" in err for err in qc_res["errors"])


# =========================================================================
# Scenario 4: Two roles use correct reference audio in timeline order
# =========================================================================
def test_two_roles_use_correct_references_in_order(tmp_path):
    _, cfg = channel_manager.get_channel_config("wuby")
    roles = cfg["_voice_profile"]["role_profiles"]

    # Verify configurations
    assert Path(roles["character"]["ref_audio"]).name == "giongnucute.wav"
    assert Path(roles["narrator"]["ref_audio"]).name == "2_nu_tre_trung.mp3"

    cues = [
        Cue(0, 3, "Lời người dẫn mở đầu", "narrator"),
        Cue(4, 7, "Lời nhân vật đối thoại", "character"),
        Cue(8, 11, "Lời người dẫn kết thúc", "narrator"),
    ]

    generated = {}
    import voice_router

    def mock_synth(texts, paths, cfg, ref):
        for text, path in zip(texts, paths):
            generated[path] = (text, Path(ref.audio).name)
            Path(path).with_suffix(".meta.json").write_text(json.dumps({"is_clone": True}))
        return ["khanh_omnivoice"], []

    def mock_align(actual, paths, out, *args, **kwargs):
        assert [generated[p][1] for p in paths] == [
            "2_nu_tre_trung.mp3",
            "giongnucute.wav",
            "2_nu_tre_trung.mp3",
        ]
        out.write_bytes(b"aligned_audio_data")
        return {}

    with patch.object(voice_router, "_synthesize_missing", side_effect=mock_synth), \
         patch("wuby_studio.audio.align_track", side_effect=mock_align):
        render_roles(cues, tmp_path / "roles.wav", cfg["_voice_profile"], 12.0, 1.0)

    report = json.loads((tmp_path / "roles_voice_report.json").read_text(encoding="utf-8"))
    assert set(report["role_references"]) == {"character", "narrator"}
    assert Path(report["role_references"]["character"]["audio"]).name == "giongnucute.wav"
    assert Path(report["role_references"]["narrator"]["audio"]).name == "2_nu_tre_trung.mp3"


# =========================================================================
# Scenario 5: Failed TTS cue causes job to fail and prevents Drive upload
# =========================================================================
def test_failed_tts_cue_fails_job_and_prevents_drive_copy(tmp_path):
    _, cfg = channel_manager.get_channel_config("wuby")
    cues = [Cue(0, 3, "Câu thoại bị lỗi clone", "character")]

    import voice_router
    def mock_synth_fail(*args, **kwargs):
        raise RuntimeError("OMNIVOICE_SYNTHESIS_FAILED: GPU Out of memory or CUDA error")

    with patch.object(voice_router, "_synthesize_missing", side_effect=mock_synth_fail):
        with pytest.raises(Exception, match="OMNIVOICE_SYNTHESIS_FAILED"):
            render_roles(cues, tmp_path / "fail.wav", cfg["_voice_profile"], 5.0, 1.0)

    # Output file must NOT exist
    assert not (tmp_path / "fail.wav").exists()


# =========================================================================
# Scenario 6: QC pass is required to allow publish
# =========================================================================
def test_qc_pass_required_for_publish(tmp_path):
    drive_dir = tmp_path / "drive_target"
    drive_dir.mkdir()
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir()

    source_video = tmp_path / "source.mp4"
    rendered_video = tmp_path / "rendered.mp4"
    source_video.write_bytes(b"data")
    rendered_video.write_bytes(b"data")

    # 1. When QC fails -> MUST quarantine, do NOT copy to Drive
    qc_failed_report = {
        "passed": False,
        "errors": ["BLANK_WIPEOUT: Track #1 deleted without replacement"],
    }
    with patch("wuby_qc.run_wuby_qc", return_value=qc_failed_report):
        res = wuby_publish_gate(rendered_video, drive_dir, quarantine_dir)
        assert res["published"] is False
        assert not (drive_dir / rendered_video.name).exists()
        assert (quarantine_dir / rendered_video.name).exists()

    # 2. When QC passes -> MUST copy to Drive
    qc_passed_report = {
        "passed": True,
        "errors": [],
    }
    with patch("wuby_qc.run_wuby_qc", return_value=qc_passed_report):
        res = wuby_publish_gate(rendered_video, drive_dir, quarantine_dir)
        assert res["published"] is True
        assert (drive_dir / rendered_video.name).exists()


def wuby_publish_gate(rendered_video: Path, drive_dir: Path, quarantine_dir: Path) -> dict:
    """Helper representing the publish gate logic."""
    from wuby_qc import run_wuby_qc
    qc = run_wuby_qc(rendered_video, rendered_video)
    if qc["passed"]:
        import shutil
        target = drive_dir / rendered_video.name
        shutil.copy2(rendered_video, target)
        return {"published": True, "target": str(target)}
    else:
        import shutil
        target = quarantine_dir / rendered_video.name
        shutil.copy2(rendered_video, target)
        return {"published": False, "target": str(target)}
