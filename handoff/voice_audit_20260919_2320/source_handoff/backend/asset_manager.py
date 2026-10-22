from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ASSETS_DIR = PROJECT_DIR / "channel_assets"
VOICE_SAMPLES_DIR = PROJECT_DIR / "voice_samples"

_IMAGE_EXTS = (".png", ".webp", ".jpg", ".jpeg", ".bmp")


def slugify_asset_name(value: str) -> str:
    """Turn a channel name into a stable Windows-friendly folder key."""
    value = (value or "").strip().replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value or "default"


def _candidate_asset_folders(channel_cfg: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    explicit = str(channel_cfg.get("asset_folder") or "").strip()
    name = str(channel_cfg.get("name") or "").strip()

    if explicit:
        explicit_path = Path(explicit)
        candidates.append(explicit_path if explicit_path.is_absolute() else CHANNEL_ASSETS_DIR / explicit_path)
    if name:
        # Support exactly what the user sees in JSON, e.g. channel_assets/Vũ Trụ Phim/
        candidates.append(CHANNEL_ASSETS_DIR / name)
        # Also support a normalized folder, e.g. channel_assets/Vu_Tru_Phim/
        candidates.append(CHANNEL_ASSETS_DIR / slugify_asset_name(name))
    candidates.append(CHANNEL_ASSETS_DIR / "default")

    unique: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _resolve_configured_path(value: Any, folders: list[Path]) -> Path | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"auto", "none", "null"}:
        return None

    p = Path(raw)
    if p.is_absolute() and p.is_file():
        return p

    for folder in folders:
        candidate = folder / p
        if candidate.is_file():
            return candidate

    project_candidate = PROJECT_DIR / p
    if project_candidate.is_file():
        return project_candidate
    return None


def _auto_find(folders: list[Path], stems: tuple[str, ...]) -> Path | None:
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for stem in stems:
            for ext in _IMAGE_EXTS:
                p = folder / f"{stem}{ext}"
                if p.is_file():
                    return p
    return None


def resolve_channel_assets(channel_cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve per-channel visual assets without making the renderer depend on hard-coded paths.

    Search order:
      1) channel_cfg.asset_folder
      2) channel_assets/<exact channel name>/
      3) channel_assets/<normalized channel name>/
      4) channel_assets/default/

    Common filenames: logo.png / watermark.png and cover.jpg / thumbnail.jpg.
    """
    folders = _candidate_asset_folders(channel_cfg)
    render_cfg = channel_cfg.get("render") if isinstance(channel_cfg.get("render"), dict) else {}
    logo_cfg = render_cfg.get("logo") if isinstance(render_cfg.get("logo"), dict) else {}
    cover_cfg = render_cfg.get("cover") if isinstance(render_cfg.get("cover"), dict) else {}

    logo_path = _resolve_configured_path(logo_cfg.get("file") or channel_cfg.get("logo_path"), folders)
    if logo_path is None and str(logo_cfg.get("file", "auto")).lower() != "none":
        logo_path = _auto_find(folders, ("logo", "watermark", "brand"))

    cover_path = _resolve_configured_path(cover_cfg.get("file") or channel_cfg.get("cover_path"), folders)
    if cover_path is None and str(cover_cfg.get("file", "auto")).lower() != "none":
        cover_path = _auto_find(folders, ("cover", "thumbnail", "poster", "intro"))

    selected_folder = next((p for p in folders if p.exists() and p.is_dir()), folders[0])
    return {
        "folder": str(selected_folder),
        "logo_path": str(logo_path) if logo_path else None,
        "cover_path": str(cover_path) if cover_path else None,
    }


def resolve_voice_sample(path_value: Any) -> Path | None:
    """Resolve a voice sample from an absolute path or from project/voice_samples."""
    if not path_value:
        return None
    p = Path(str(path_value).strip())
    if p.is_absolute() and p.is_file():
        return p
    candidate = VOICE_SAMPLES_DIR / p
    if candidate.is_file():
        return candidate
    project_candidate = PROJECT_DIR / p
    if project_candidate.is_file():
        return project_candidate
    return None
