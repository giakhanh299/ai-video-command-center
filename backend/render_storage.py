"""Local render delivery and ownership of the shared Facebook review folders."""

import hashlib
import json
import os
import shutil
from pathlib import Path

REVIEW_STAGE = "02_MOI_RENDER_CHO_XAC_NHAN"
RAW_STAGE = "01_CHUA_RENDER"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}


def render_receipt_path(video: str | Path, *, for_write: bool = False) -> Path:
    """Group verification data away from review videos; read old layouts too."""
    video = Path(video)
    grouped = video.parent / '.render_metadata' / video.with_suffix('.render.json').name
    legacy = video.with_suffix('.render.json')
    if for_write:
        grouped.parent.mkdir(parents=True, exist_ok=True)
        return grouped
    return grouped if grouped.is_file() else legacy


def managed_channel_roots(root: Path) -> set[Path]:
    config = root.parent / "fanpage-control-center-v2.0/config/channels.json"
    if not config.is_file():
        return set()
    channels = json.loads(config.read_text(encoding="utf-8"))
    return {
        Path(c["workspace_root"]).resolve() for c in channels
        if c.get("workflow_mode") == "managed_4_stage" and c.get("workspace_root")
        and Path(c["workspace_root"]).resolve().is_relative_to(root.resolve())
    }


def review_directory(root: Path, folder: str) -> Path:
    root = root.resolve()
    destination = (root / folder).resolve()
    if destination == root or not destination.is_relative_to(root):
        raise ValueError("Render folder must stay inside the configured video workspace")
    managed = managed_channel_roots(root)
    # Separate render-only projects have no publisher channel or ready stage.
    render_only = set()
    registry = Path(__file__).with_name('render_only_projects.json')
    if registry.exists():
        for entry in json.loads(registry.read_text(encoding='utf-8')):
            name = entry['folder']
            if Path(name).name != name or not name.startswith('THU_NGHIEM_'):
                raise ValueError('Invalid render-only project folder')
            candidate = (root / name / REVIEW_STAGE).resolve()
            if candidate.is_relative_to(root):
                render_only.add(candidate)
    if managed and destination not in {c / REVIEW_STAGE for c in managed} | render_only:
        raise ValueError("Facebook renders must be saved in a channel's review folder")
    return destination


def require_rendered_video(path: str | Path) -> Path:
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Render did not create a nonempty video: {path}")
    return path


def _digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def _copy_new(source: Path, destination: Path) -> None:
    # Exclusive creation keeps an existing review/approved file intact.
    stream = destination.open("xb")
    try:
        with stream, source.open("rb") as original:
            shutil.copyfileobj(original, stream)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def save_to_review(video: str | Path, directory: Path, filename: str,
                   subtitles: str | Path | None = None) -> Path:
    video = require_rendered_video(video)
    if Path(filename).name != filename or not filename.lower().endswith(".mp4"):
        raise ValueError("Expected a video filename without directories")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    checksum = None
    while True:
        try:
            _copy_new(video, target)
            break
        except FileExistsError:
            checksum = checksum or _digest(video)
            if _digest(target) == checksum:
                break
            candidate = directory / f"{Path(filename).stem}_{checksum[:12]}.mp4"
            if candidate == target:
                raise FileExistsError(f"Conflicting review video: {target}")
            target = candidate
    # Never replace an independently supplied subtitle for an existing video.
    if subtitles and Path(subtitles).is_file():
        try:
            _copy_new(Path(subtitles), target.with_suffix(".srt"))
        except FileExistsError:
            pass
    return target


def watch_inputs(root: Path):
    """The Facebook coordinator owns its 01 folders and their render adapters."""
    managed = managed_channel_roots(root)
    for entry in root.iterdir():
        if entry.is_file():
            candidates = [entry]
        elif entry.name.startswith("KENH_") and entry.resolve() not in managed:
            raw = entry / RAW_STAGE
            candidates = raw.iterdir() if raw.is_dir() else []
        else:
            continue
        for path in candidates:
            stem = path.stem
            if (path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
                    and not path.name.startswith(".")
                    and not stem.endswith(("_vi", "_raw"))
                    and "_nu_tre" not in stem and "_hoaimy" not in stem):
                yield path


def source_key(path: str | Path, root: Path) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    return path.resolve().relative_to(root.resolve()).as_posix().casefold()


def cloud_upload_enabled(root: Path) -> bool:
    override = os.getenv("GDRIVE_UPLOAD_ENABLED")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on"}
    return not managed_channel_roots(root)


def review_files_for_job(root: Path, filename: str, location: str = "") -> list[Path]:
    """Find one job's review video; ambiguous names never select another channel."""
    root = root.resolve()

    def in_review(path):
        path = path.resolve()
        return (path.is_relative_to(root) and
                (path.parent.name == REVIEW_STAGE or path.relative_to(root).parts[0] == "Đã Render"))

    video = None
    if location and not location.startswith(("https://", "http://")):
        candidate = root / location
        if candidate.is_file() and in_review(candidate):
            video = candidate
        else:
            return []
    if video is None and filename and Path(filename).name == filename:
        matches = list(root.glob(f"KENH_*/{REVIEW_STAGE}/{filename}"))
        legacy = root / "Đã Render"
        if legacy.is_dir():
            matches.extend(legacy.rglob(filename))
        matches = [p for p in matches if p.is_file() and in_review(p)]
        if len(matches) == 1:
            video = matches[0]
    return [p for p in (video, video.with_suffix(".srt") if video else None) if p and p.is_file()]
