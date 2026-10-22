from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from .errors import DomainError

MAX_BYTES = 500 * 1024 * 1024


def storage_path(root: Path, key: str) -> Path:
    parts = PurePosixPath(key).parts
    if not parts or "\\" in key or ":" in key or key.startswith("/") or any(p in (".", "..") for p in parts):
        raise DomainError("INVALID_STORAGE_KEY", 422)
    if str(PurePosixPath(key)) != key:
        raise DomainError("INVALID_STORAGE_KEY", 422)
    base = root.resolve()
    candidate = base.joinpath(*parts)
    for part in [candidate, *candidate.parents]:
        if part == base:
            break
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise DomainError("UNSAFE_FILE_PATH", 422)
    resolved = candidate.resolve()
    if not resolved.is_relative_to(base) or resolved == base:
        raise DomainError("UNSAFE_FILE_PATH", 422)
    return resolved


def checksum(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inspect_video(path: Path):
    # Lazy import: API import/health never loads model libraries or legacy bot.
    from wuby_studio.media import probe, frame_rate
    try:
        data = probe(path)
        video = data["video"]
        if not video or not 0 < data["duration"] <= 3600:
            raise ValueError("Invalid video")
        if not 0 < video["width"] <= 4096 or not 0 < video["height"] <= 4096:
            raise ValueError("Video dimensions")
        fps = frame_rate(data)
        raw_frames = str(video.get("nb_frames", ""))
        return {"duration": data["duration"], "width": video["width"], "height": video["height"],
                "fps": fps, "has_audio": data["audio"] is not None, "codec": video["codec_name"],
                "frames": int(raw_frames) if raw_frames.isdigit() else None}
    except Exception as exc:
        raise DomainError("INVALID_VIDEO", 422) from exc


def verify_file(root: Path, row):
    path = storage_path(root, row["storage_key"])
    if not path.is_file():
        raise DomainError("FILE_NOT_FOUND", 422)
    before = path.stat()
    if not 0 < before.st_size <= MAX_BYTES or before.st_size != row["size_bytes"] or checksum(path) != row["sha256"]:
        raise DomainError("FILE_INTEGRITY_MISMATCH", 422)
    kind, mime = row["kind"], row["media_type"]
    if (kind, mime, path.suffix.lower()) == ("video", "video/mp4", ".mp4"):
        inspect_video(path)
    elif (kind, mime, path.suffix.lower()) == ("report", "application/json", ".json"):
        if before.st_size > 1024 * 1024:
            raise DomainError("REPORT_TOO_LARGE", 422)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
        except (ValueError, UnicodeError) as exc:
            raise DomainError("INVALID_REPORT", 422) from exc
    else:
        # Audio/subtitle/packet verification is intentionally not guessed.
        raise DomainError("FILE_KIND_NOT_SUPPORTED", 422)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise DomainError("FILE_CHANGED_DURING_VERIFY", 422)
    return path
