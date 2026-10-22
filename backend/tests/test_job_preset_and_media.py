"""Selection and upload contracts, without starting the bot or calling Telegram."""

import ast
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import channel_manager


@pytest.fixture
def presets(monkeypatch):
    config = {
        "presets": {
            "wuby": {"voice": "nu_tre", "wuby_studio": {"hybrid_frame": {"enabled": True}}},
            "cauhinh2": {"voice": "nam_minh", "render_profile": "movie"},
            "cauhinh3": {"voice": "nu_tre", "subtitle_detection": {"mode": "ocr"}},
            "chidepdicau": {"tts_enabled": False, "voice": None, "bg_volume": 1.0},
            "song1minhcogivui": {"voice": "nam_minh", "_logo_type": "kenh_007"},
        },
        "render_profiles": {"wuby_overlay": {"title": {"enabled": False}}, "movie": {}},
        "workflows": {"wuby": {"settings": {"wuby_preflight": {"required": True}}}},
    }
    monkeypatch.setattr(channel_manager, "load_channels_config", lambda: config)
    return config


@pytest.mark.parametrize("alias,target", [
    ("cauhinh4", "chidepdicau"), ("cauhinh5", "song1minhcogivui"),
])
def test_button_aliases_keep_preset_behavior(presets, alias, target):
    base = {"speed": 1.2, "render_profile": "movie"}
    assert channel_manager.apply_job_preset(base, alias) == channel_manager.apply_job_preset(base, target)


def test_missing_legacy_preset_uses_config2_defaults(presets):
    result = channel_manager.apply_job_preset({}, "cauhinh3_wuby")
    assert result["voice"] == "nam_minh"
    assert result["render_profile"] == "movie"
    assert result["name"] == "Cấu hình cauhinh3_wuby"


def test_switching_presets_clears_previous_ocr_settings(presets):
    cfg = channel_manager.apply_job_preset({}, "cauhinh3")
    assert cfg["subtitle_detection"] == {"mode": "ocr"}
    result = channel_manager.apply_job_preset(cfg, "cauhinh2")
    assert result["subtitle_detection"] == {}
    assert cfg["subtitle_detection"] == {"mode": "ocr"}


def test_wuby_keeps_frame_speed_and_preflight(presets):
    result = channel_manager.apply_job_preset({"speed": 1.2}, "cauhinh1")
    assert result["speed"] == 1.2
    assert result["workflow"] == "wuby"
    assert result["render_profile"] == "wuby_overlay"
    assert result["wuby_studio"]["hybrid_frame"] == {"enabled": True}
    assert result["wuby_preflight"] == {"required": True}
    assert result["dialogue_replace"]["mute_original_speech"] is True


def test_explicit_logo_wins_and_cache_stays_unchanged(presets):
    original = copy.deepcopy(presets)
    result = channel_manager.apply_job_preset({}, "wuby", "batphimlen")
    assert result["_logo_type"] == "batphimlen"
    result["render"]["title"]["enabled"] = True
    result["wuby_studio"]["hybrid_frame"]["enabled"] = False
    assert presets == original


def test_original_audio_preset_keeps_tts_disabled(presets):
    result = channel_manager.apply_job_preset({}, "cauhinh4")
    assert result["tts_enabled"] is False
    assert result["voice"] is None
    assert result["_voice_profile"] == {}
    assert result["bg_volume"] == 1.0


@pytest.mark.parametrize("choice", [None, "unknown"])
def test_unselected_or_unknown_workflow_keeps_job_settings(presets, choice):
    base = {"render": {"mask": "blur"}, "speed": 1.5}
    result = channel_manager.apply_job_preset(base, choice)
    assert result == base
    result["render"]["mask"] = "none"
    assert base["render"]["mask"] == "blur"


@pytest.mark.parametrize("alias,title,tag", [
    ("kenh_001_tienvadoi", "Tiền Và Đời", "@TienVaDoi"),
    ("cauhinh2", "Bật Phim Lên", "@BatPhimLen"),
    ("review_sach", "Review Sách Có Tâm", "@ReviewSachCoTam"),
    ("boxman", "Boxman Kể Chuyện", "@BoxmanKeChuyen"),
    ("cauhinh3", "Vũ Trụ Cày Phim", "@VuTruCayPhim"),
    ("cauhinh1", "Tiểu Wuby", "@TieuWuby"),
    ("k7", "Sống 1 mình có gì vui", "@Song1MinhCoGiVui"),
    ("gaidep_cauca", "Chị Đẹp Đi Câu", "@ChiDepDiCau"),
])
def test_logo_aliases_and_case(alias, title, tag):
    assert channel_manager.resolve_logo_text(f" {alias.upper()} ") == (title, tag)


def test_custom_logo_text_and_unknown_alias_fallback():
    assert channel_manager.resolve_logo_text("missing") == ("Vũ Trụ Cày Phim", "@VuTruCayPhim")
    assert channel_manager.resolve_logo_text("wuby", {"text": "Kênh riêng"}) == ("Kênh riêng", "@TieuWuby")


@pytest.fixture
def media_api():
    # Compile only the upload functions: importing telegram_bot also loads models/configuration.
    source = Path(__file__).resolve().parents[1] / "telegram_bot.py"
    names = {"_send_media", "send_photo", "send_video", "send_document"}
    nodes = [n for n in ast.parse(source.read_text(encoding="utf-8")).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    calls, replies = [], []

    def post(url, *, data, files, timeout):
        calls.append(dict(url=url, data=data.copy(), kind=next(iter(files)),
                          body=next(iter(files.values())).read(), timeout=timeout))
        result = replies.pop(0) if replies else {"ok": True}
        return SimpleNamespace(json=lambda: result)

    scope = dict(os=os, json=json, requests=SimpleNamespace(post=post), API_BASE="https://example.invalid")
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)
    return SimpleNamespace(functions=scope, calls=calls, replies=replies)


@pytest.mark.parametrize("kind,timeout", [("photo", 45), ("video", 180), ("document", 60)])
def test_media_upload_preserves_payload_and_timeout(media_api, tmp_path, kind, timeout):
    file = tmp_path / "media.bin"
    file.write_bytes(b"media bytes")
    result = media_api.functions[f"send_{kind}"](123, file, "Chào", 4, 5)
    call, = media_api.calls
    assert call == dict(url=f"https://example.invalid/send{kind.title()}",
                        data={"chat_id": 123, "caption": "Chào", "parse_mode": "HTML",
                              "reply_to_message_id": 4, "message_thread_id": 5},
                        kind=kind, body=b"media bytes", timeout=timeout)
    assert result == ({"ok": True} if kind == "photo" else None)


def test_photo_reopens_file_for_plain_caption_retry(media_api, tmp_path):
    file = tmp_path / "photo.png"
    file.write_bytes(b"image bytes")
    media_api.replies.extend([{"ok": False, "description": "Bad Request: can't parse entities"}, {"ok": True}])
    result = media_api.functions["send_photo"](123, file, "<broken", reply_markup={"inline_keyboard": []})
    assert result == {"ok": True}
    first, retry = media_api.calls
    assert first["body"] == retry["body"] == b"image bytes"
    assert first["data"]["parse_mode"] == "HTML"
    assert "parse_mode" not in retry["data"]
    assert json.loads(retry["data"]["reply_markup"]) == {"inline_keyboard": []}


@pytest.mark.parametrize("size,uploads", [(49 * 1024 * 1024 - 1, 1), (49 * 1024 * 1024, 0)])
def test_video_upload_size_boundary(media_api, tmp_path, monkeypatch, size, uploads):
    file = tmp_path / "video.mp4"
    file.write_bytes(b"video")
    monkeypatch.setattr(os.path, "getsize", lambda _: size)
    media_api.functions["send_video"](123, file)
    assert len(media_api.calls) == uploads


@pytest.mark.parametrize("kind", ["photo", "video", "document"])
def test_missing_media_does_not_send(media_api, tmp_path, kind):
    assert media_api.functions[f"send_{kind}"](123, tmp_path / "missing") is None
    assert not media_api.calls
