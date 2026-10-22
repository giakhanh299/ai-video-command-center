from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

import asset_manager

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "channels_config.json"

BASE_VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "nu_tre": {
        "label": "Nữ Trẻ Trung (Edge Hoài My)",
        "engine": "edge",
        "voice": "vi-VN-HoaiMyNeural",
        "pitch": "+8Hz",
    },
    "nu_tram": {
        "label": "Nữ Trầm Ấm (Edge Hoài My)",
        "engine": "edge",
        "voice": "vi-VN-HoaiMyNeural",
        "pitch": "-6Hz",
    },
    "nam_minh": {
        "label": "Nam Minh (Edge)",
        "engine": "edge",
        "voice": "vi-VN-NamMinhNeural",
        "pitch": "+0Hz",
    },
    "hoaimy": {
        "label": "Hoài My gốc (Edge)",
        "engine": "edge",
        "voice": "vi-VN-HoaiMyNeural",
        "pitch": "+0Hz",
    },
    "google": {
        "label": "Chị Google",
        "engine": "google",
    },
}

SUPPORTED_VOICES = {k: v["label"] for k, v in BASE_VOICE_PROFILES.items()}

SUPPORTED_MASKS = {
    "black_bar": "Dải đen điện ảnh (che trên/dưới)",
    "blur": "Làm mờ vùng phụ đề (BoxBlur)",
    "none": "Không che (giữ nguyên khung hình)",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 2,
    "default": {
        "name": "Kênh Mặc Định (Wuby Main)",
        "workflow": "wuby",
        "voice": "nu_tre",
        "speed": 1.4,
        "mask_mode": "in_video_overlay",
        "burn_sub": True,
        "show_title_card": True,
        "keep_bg_audio": True,
        "bg_volume": 0.50,
        "drive_folder": "Đã Render/Wuby",
    },
    "voice_profiles": copy.deepcopy(BASE_VOICE_PROFILES),
    "render_profiles": {
        "review_film_black": {
            "mask_mode": "black_bar",
            "film_bars": {"top_ratio": 0.10, "bottom_ratio": 0.22, "bottom_max_ratio": 0.35},
            "title": {
                "enabled": True,
                "font": "Arial",
                "color": "#FFE600",
                "outline_color": "#000000",
                "outline_size": 3,
                "bold": True,
                "persistent_on_top_bar": True,
                "intro_duration": 6.0,
            },
            "subtitle": {
                "enabled": True,
                "font": "Arial",
                "color": "#FFFFFF",
                "outline_color": "#000000",
                "outline_size": 6,
                "bold": True,
                "max_lines": 2,
            },
            "logo": {
                "enabled": True,
                "file": "auto",
                "position": "bottom_right",
                "width_ratio": 0.18,
                "opacity": 0.12,
                "margin_x": 20,
                "margin_y": 20,
            },
            "cover": {
                "enabled": True,
                "file": "auto",
                "mode": "intro",
                "duration": 1.2,
                "fit": "cover",
            },
            "encoder": {"use_nvenc": True, "nvenc_preset": "p4", "cq": 28},
        }
    },
    "workflows": {
        "film_review_black": {
            "name": "Review phim - che đen + title/sub Việt",
            "render_profile": "review_film_black",
            "settings": {
                "mask_mode": "black_bar",
                "burn_sub": True,
                "show_title_card": True,
                "keep_bg_audio": True,
            },
        }
    },
    "channels": {},
    "presets": {},
}

_cached_config: Dict[str, Any] = {}


def deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively merge nested dictionaries without losing sibling settings."""
    result = copy.deepcopy(base)
    if not isinstance(override, dict):
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _legacy_entry_to_v2(entry: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(entry)
    if "mask_mode" in out:
        out.setdefault("render", {})["mask_mode"] = out["mask_mode"]
    return out


def _normalize_schema(data: dict[str, Any]) -> dict[str, Any]:
    """Accept both the old flat config and the v2 channel/workflow/profile schema."""
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULT_CONFIG)

    if "channels" in data or "schema_version" in data or "render_profiles" in data:
        normalized = deep_merge(DEFAULT_CONFIG, data)
        normalized["schema_version"] = 2
        normalized.setdefault("channels", {})
        normalized.setdefault("presets", {})
        normalized.setdefault("voice_profiles", {})
        normalized.setdefault("render_profiles", {})
        normalized.setdefault("workflows", {})
        return normalized

    # Legacy flat schema: default + chat IDs + named presets.
    normalized = copy.deepcopy(DEFAULT_CONFIG)
    normalized["default"] = deep_merge(normalized["default"], _legacy_entry_to_v2(data.get("default", {})))
    for key, value in data.items():
        if key == "default" or not isinstance(value, dict):
            continue
        target = "channels" if re.fullmatch(r"-?\d+", str(key).strip()) else "presets"
        normalized[target][str(key)] = _legacy_entry_to_v2(value)
    return normalized


def load_channels_config(force_reload: bool = False) -> Dict[str, Any]:
    global _cached_config
    if _cached_config and not force_reload:
        return _cached_config

    if not CONFIG_FILE.exists():
        save_channels_config(copy.deepcopy(DEFAULT_CONFIG))
        return _cached_config

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        _cached_config = _normalize_schema(raw)
        return _cached_config
    except Exception as err:
        print(f"[ChannelManager] Lỗi nạp channels_config.json: {err}")
        _cached_config = copy.deepcopy(DEFAULT_CONFIG)
        return _cached_config


def save_channels_config(config: Dict[str, Any]) -> bool:
    global _cached_config
    try:
        normalized = _normalize_schema(config)
        CONFIG_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        _cached_config = normalized
        return True
    except Exception as err:
        print(f"[ChannelManager] Lỗi lưu channels_config.json: {err}")
        return False


def _normalize_chat_id(chat_id: Any) -> str:
    return str(chat_id).strip()


def _match_channel_key(chat_id: str, channels: Dict[str, Any]) -> str | None:
    if chat_id in channels:
        return chat_id
    clean_chat = chat_id.replace("-100", "").replace("-", "")
    for key in channels.keys():
        clean_key = str(key).replace("-100", "").replace("-", "")
        if clean_key and clean_key == clean_chat:
            return str(key)
    return None


def _find_preset_keys(text: str | None, config: dict[str, Any]) -> list[str]:
    if not text:
        return []
    lower = text.lower()
    presets = config.get("presets", {})
    found: list[str] = []

    for key, preset in presets.items():
        tags = {f"#{str(key).lower()}"}
        if isinstance(preset, dict):
            for tag in preset.get("hashtags", []) or []:
                tag = str(tag).strip().lower()
                if tag:
                    tags.add(tag if tag.startswith("#") else f"#{tag}")
        if any(tag in lower for tag in tags):
            found.append(str(key))

    shortcuts = {
        "#nam": "kenh_nam",
        "#kenhnam": "kenh_nam",
        "#nutram": "kenh_nu_tram",
        "#nu_tram": "kenh_nu_tram",
        "#khongche": "kenh_khong_che",
        "#noche": "kenh_khong_che",
        "#blur": "kenh_blur",
    }
    for tag, key in shortcuts.items():
        if tag in lower and key in presets and key not in found:
            found.append(key)
    return found



def _preset_overlay(preset: dict[str, Any]) -> dict[str, Any]:
    """Preset metadata (name/hashtags) must not rename the actual Telegram channel."""
    out = copy.deepcopy(preset) if isinstance(preset, dict) else {}
    out.pop("name", None)
    out.pop("hashtags", None)
    return out

def get_supported_voices() -> dict[str, str]:
    cfg = load_channels_config()
    profiles = deep_merge(BASE_VOICE_PROFILES, cfg.get("voice_profiles", {}))
    return {key: str(value.get("label") or key) for key, value in profiles.items() if isinstance(value, dict)}


def get_channel_entries() -> dict[str, dict[str, Any]]:
    return load_channels_config().get("channels", {})


def get_preset_entries() -> dict[str, dict[str, Any]]:
    return load_channels_config().get("presets", {})


def _resolve_voice_profile(voice_key: str, config: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    profiles = deep_merge(BASE_VOICE_PROFILES, config.get("voice_profiles", {}))
    profile = copy.deepcopy(profiles.get(voice_key, profiles.get("nu_tre", {})))
    voice_overrides = cfg.get("voice_overrides") if isinstance(cfg.get("voice_overrides"), dict) else {}
    profile = deep_merge(profile, voice_overrides)

    ref = profile.get("ref_audio") or profile.get("ref_audio_path") or profile.get("reference_audio")
    resolved_ref = asset_manager.resolve_voice_sample(ref)
    if resolved_ref:
        profile["ref_audio"] = str(resolved_ref)
    return profile


def get_channel_config(chat_id_or_key: Any = "default", text: str | None = None) -> Tuple[str, Dict[str, Any]]:
    """
    Resolve one immutable-style configuration for a job.

    Priority (low -> high):
      default -> workflow/settings -> render profile -> channel -> hashtag presets -> inline overrides.
    """
    config = load_channels_config()
    channels = config.get("channels", {})
    presets = config.get("presets", {})
    chat_str = _normalize_chat_id(chat_id_or_key)

    matched_channel = _match_channel_key(chat_str, channels)
    channel_key = matched_channel or "default"
    channel_cfg = channels.get(matched_channel, {}) if matched_channel else {}

    # Calling with a named preset is supported for manual/testing usage.
    if not matched_channel and chat_str in presets:
        channel_key = chat_str
        channel_cfg = presets.get(chat_str, {})

    preset_keys = _find_preset_keys(text, config)

    # First calculate which workflow/profile should be selected after all selectors.
    selector = deep_merge(config.get("default", {}), channel_cfg)
    for preset_key in preset_keys:
        selector = deep_merge(selector, _preset_overlay(presets.get(preset_key, {})))

    workflow_name = str(selector.get("workflow") or "film_review_black")
    workflow_cfg = config.get("workflows", {}).get(workflow_name, {})
    render_profile_name = str(
        selector.get("render_profile")
        or workflow_cfg.get("render_profile")
        or "review_film_black"
    )
    render_profile = config.get("render_profiles", {}).get(render_profile_name, {})

    resolved = copy.deepcopy(config.get("default", {}))
    resolved["workflow"] = workflow_name
    resolved["render_profile"] = render_profile_name
    resolved = deep_merge(resolved, workflow_cfg.get("settings", {}))
    resolved["render"] = deep_merge(resolved.get("render", {}), render_profile)
    resolved = deep_merge(resolved, channel_cfg)
    for preset_key in preset_keys:
        resolved = deep_merge(resolved, _preset_overlay(presets.get(preset_key, {})))

    # Inline one-job overrides.
    if text:
        speed_match = re.search(r"\bspeed=([0-2](?:\.\d+)?)\b", text, re.IGNORECASE)
        if speed_match:
            try:
                resolved["speed"] = float(speed_match.group(1))
            except Exception:
                pass

        voice_keys = list(get_supported_voices().keys())
        if voice_keys:
            voice_pattern = "|".join(re.escape(k) for k in sorted(voice_keys, key=len, reverse=True))
            voice_match = re.search(rf"\bvoice=({voice_pattern})\b", text, re.IGNORECASE)
            if voice_match:
                resolved["voice"] = voice_match.group(1)

        mask_match = re.search(r"\bmask=(black_bar|blur|none)\b", text, re.IGNORECASE)
        if mask_match:
            mask = mask_match.group(1).lower()
            resolved["mask_mode"] = mask
            resolved.setdefault("render", {})["mask_mode"] = mask

        workflow_match = re.search(r"\bworkflow=([A-Za-z0-9_\-]+)\b", text, re.IGNORECASE)
        if workflow_match and workflow_match.group(1) in config.get("workflows", {}):
            # Keep this lightweight: explicit workflow is intended mainly for one-off jobs.
            wf_name = workflow_match.group(1)
            wf = config["workflows"].get(wf_name, {})
            rp_name = str(wf.get("render_profile") or render_profile_name)
            resolved = deep_merge(resolved, wf.get("settings", {}))
            resolved["workflow"] = wf_name
            resolved["render_profile"] = rp_name
            resolved["render"] = deep_merge(resolved.get("render", {}), config.get("render_profiles", {}).get(rp_name, {}))

    render_cfg = resolved.get("render") if isinstance(resolved.get("render"), dict) else {}
    if "mask_mode" in render_cfg:
        resolved["mask_mode"] = str(render_cfg.get("mask_mode"))

    voice_key = str(resolved.get("voice") or "nu_tre")
    resolved["_voice_profile"] = _resolve_voice_profile(voice_key, config, resolved)
    resolved["_assets"] = asset_manager.resolve_channel_assets(resolved)
    resolved["_preset_keys"] = preset_keys
    return channel_key, resolved


def update_channel_setting(channel_key: str, setting_key: str, setting_value: Any) -> Tuple[bool, str]:
    config = load_channels_config(force_reload=True)
    channel_key = _normalize_chat_id(channel_key)
    channels = config.setdefault("channels", {})

    if channel_key not in channels:
        channels[channel_key] = {
            "name": f"Kênh {channel_key}",
            "workflow": config.get("default", {}).get("workflow", "film_review_black"),
        }

    target = channels[channel_key]

    if setting_key == "voice":
        val = str(setting_value).strip()
        voices = get_supported_voices()
        if val not in voices:
            return False, f"Giọng đọc không hợp lệ. Các giọng hỗ trợ: {', '.join(voices.keys())}"
        target["voice"] = val

    elif setting_key == "speed":
        try:
            val = float(str(setting_value).replace(",", "."))
            if not (0.5 <= val <= 2.5):
                return False, "Tốc độ phải từ 0.5 đến 2.5."
            target["speed"] = round(val, 2)
        except Exception:
            return False, "Giá trị tốc độ không hợp lệ (ví dụ: 1.4 hoặc 1.5)."

    elif setting_key == "mask_mode":
        val = str(setting_value).strip().lower()
        if val not in SUPPORTED_MASKS:
            return False, f"Chế độ che chữ không hợp lệ. Hỗ trợ: {', '.join(SUPPORTED_MASKS.keys())}"
        target["mask_mode"] = val
        target.setdefault("render", {})["mask_mode"] = val

    elif setting_key == "workflow":
        val = str(setting_value).strip()
        if val not in config.get("workflows", {}):
            return False, f"Workflow không tồn tại: {val}"
        target["workflow"] = val

    elif setting_key == "show_title_card":
        val = str(setting_value).strip().lower() in {"true", "1", "yes", "on", "bật"}
        target["show_title_card"] = val

    elif setting_key == "bg_volume":
        try:
            val = float(str(setting_value).replace(",", "."))
            if not (0.0 <= val <= 1.0):
                return False, "Âm lượng nền phải từ 0.0 đến 1.0."
            target["bg_volume"] = round(val, 2)
        except Exception:
            return False, "Giá trị âm lượng không hợp lệ."

    elif setting_key in {"drive_folder", "name", "asset_folder"}:
        target[setting_key] = str(setting_value).strip()

    else:
        target[setting_key] = setting_value

    saved = save_channels_config(config)
    if saved:
        return True, (
            f"Đã cập nhật <b>{setting_key}</b> = <code>{target.get(setting_key)}</code> "
            f"cho kênh <b>{target.get('name', channel_key)}</b>."
        )
    return False, "Lỗi khi lưu cấu hình vào file."


def format_channel_info(channel_key: str, cfg: Dict[str, Any]) -> str:
    voices = get_supported_voices()
    voice_key = str(cfg.get("voice", "nu_tre"))
    voice_name = voices.get(voice_key, voice_key)
    mask = str(cfg.get("mask_mode", "black_bar"))
    mask_name = SUPPORTED_MASKS.get(mask, mask)
    title_status = "Bật" if cfg.get("show_title_card", True) else "Tắt"
    assets = cfg.get("_assets", {}) if isinstance(cfg.get("_assets"), dict) else {}
    logo_status = Path(str(assets.get("logo_path"))).name if assets.get("logo_path") else "chưa có"
    cover_status = Path(str(assets.get("cover_path"))).name if assets.get("cover_path") else "chưa có"

    return (
        f"📺 <b>CẤU HÌNH KÊNH: {cfg.get('name', channel_key)}</b>\n"
        f"• <b>Mã định danh:</b> <code>{channel_key}</code>\n"
        f"• 🧩 <b>Workflow:</b> <code>{cfg.get('workflow')}</code>\n"
        f"• 🎨 <b>Render profile:</b> <code>{cfg.get('render_profile')}</code>\n"
        f"• 🎙 <b>Giọng đọc:</b> <code>{voice_key}</code> ({voice_name})\n"
        f"• ⚡ <b>Tốc độ:</b> <code>{cfg.get('speed')}x</code>\n"
        f"• 🔲 <b>Che chữ:</b> <code>{mask}</code> ({mask_name})\n"
        f"• 🎬 <b>Tiêu đề:</b> <code>{title_status}</code>\n"
        f"• 🔊 <b>Âm lượng nền:</b> <code>{cfg.get('bg_volume', 0.10)}</code>\n"
        f"• 🖼 <b>Cover:</b> <code>{cover_status}</code>\n"
        f"• 🏷 <b>Logo:</b> <code>{logo_status}</code>\n"
        f"• 📁 <b>Assets:</b> <code>{assets.get('folder', '')}</code>\n"
        f"• 📁 <b>Drive:</b> <code>{cfg.get('drive_folder', 'Đã Render')}</code>"
    )
