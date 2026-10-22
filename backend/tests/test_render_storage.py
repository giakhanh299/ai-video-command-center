import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import render_storage as storage


@pytest.fixture
def facebook_workspace(tmp_path):
    root = tmp_path / "videos_upload"
    root.mkdir()
    config = tmp_path / "fanpage-control-center-v2.0/config/channels.json"
    config.parent.mkdir(parents=True)
    channels = [{"workflow_mode": "managed_4_stage", "workspace_root": str(root / name)}
                for name in ("KENH_002_BatPhimLen", "KENH_005_VuTruCayPhim")]
    config.write_text(json.dumps(channels), encoding="utf-8")
    return root


def write(path, content=b"video bytes"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_facebook_destinations_are_review_only(facebook_workspace):
    root = facebook_workspace
    review = root / "KENH_002_BatPhimLen" / storage.REVIEW_STAGE
    assert storage.review_directory(root, str(review.relative_to(root))) == review.resolve()
    for folder in ("KENH_002_BatPhimLen/03_CHUAN_BI_UP", "Đã Render", "../escape", str(root.parent)):
        with pytest.raises(ValueError):
            storage.review_directory(root, folder)


def test_missing_or_empty_render_is_not_a_success(tmp_path):
    with pytest.raises(FileNotFoundError):
        storage.save_to_review(tmp_path / "missing.mp4", tmp_path / "review", "out.mp4")
    empty = write(tmp_path / "empty.mp4", b"")
    with pytest.raises(FileNotFoundError):
        storage.require_rendered_video(empty)
    assert not (tmp_path / "review").exists()


def test_existing_review_video_and_subtitles_are_preserved(tmp_path):
    directory = tmp_path / "review"
    old = write(directory / "same.mp4", b"old rendered video")
    old_srt = write(directory / "same.srt", b"old subtitles")
    new = write(tmp_path / "new.mp4", b"new rendered video")
    srt = write(tmp_path / "new.srt", b"new subtitles")
    result = storage.save_to_review(new, directory, "same.mp4", srt)
    assert result != old
    assert old.read_bytes() == b"old rendered video"
    assert old_srt.read_bytes() == b"old subtitles"
    assert result.read_bytes() == new.read_bytes()
    assert result.with_suffix(".srt").read_bytes() == srt.read_bytes()
    assert storage.save_to_review(new, directory, "same.mp4", srt) == result
    assert len(list(directory.glob("*.mp4"))) == 2


def test_failed_copy_removes_only_its_new_partial_file(tmp_path, monkeypatch):
    source = write(tmp_path / "source.mp4")
    old = write(tmp_path / "review/old.mp4", b"keep")

    def fail(original, output):
        output.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(storage.shutil, "copyfileobj", fail)
    with pytest.raises(OSError, match="disk full"):
        storage.save_to_review(source, old.parent, "new.mp4")
    assert not (old.parent / "new.mp4").exists()
    assert old.read_bytes() == b"keep"


def test_fb_raw_folders_are_left_to_fb_adapters(facebook_workspace):
    root = facebook_workspace
    write(root / "KENH_002_BatPhimLen/01_CHUA_RENDER/movie.mp4")
    write(root / "KENH_005_VuTruCayPhim/01_CHUA_RENDER/movie.mp4")
    legacy = write(root / "KENH_TEST/01_CHUA_RENDER/legacy.mp4")
    direct = write(root / "manual.mp4")
    write(root / "manual_vi.mp4")
    write(root / "manual_raw.mp4")
    write(root / "KENH_002_BatPhimLen/03_CHUAN_BI_UP/approved.mp4")
    assert set(storage.watch_inputs(root)) == {legacy, direct}


def test_same_filename_is_distinct_per_channel(facebook_workspace):
    root = facebook_workspace
    a = root / "KENH_002_BatPhimLen/01_CHUA_RENDER/clip.mp4"
    b = root / "KENH_005_VuTruCayPhim/01_CHUA_RENDER/clip.mp4"
    assert storage.source_key(a, root) != storage.source_key(b, root)
    assert storage.source_key("clip.mp4", root) == "clip.mp4"


def test_cloud_upload_defaults_off_for_facebook(facebook_workspace, tmp_path, monkeypatch):
    monkeypatch.delenv("GDRIVE_UPLOAD_ENABLED", raising=False)
    assert not storage.cloud_upload_enabled(facebook_workspace)
    assert storage.cloud_upload_enabled(tmp_path / "legacy_drive")
    monkeypatch.setenv("GDRIVE_UPLOAD_ENABLED", "true")
    assert storage.cloud_upload_enabled(facebook_workspace)


def test_rerender_never_deletes_another_channel_or_approved_video(facebook_workspace):
    root = facebook_workspace
    a = write(root / "KENH_002_BatPhimLen" / storage.REVIEW_STAGE / "same.mp4")
    b = write(root / "KENH_005_VuTruCayPhim" / storage.REVIEW_STAGE / "same.mp4")
    approved = write(root / "KENH_002_BatPhimLen/03_CHUAN_BI_UP/same.mp4")
    uploaded = write(root / "KENH_002_BatPhimLen/04_DA_UP/same.mp4")
    assert storage.review_files_for_job(root, "same.mp4") == []
    assert storage.review_files_for_job(root, "same.mp4", str(a.relative_to(root))) == [a]
    assert storage.review_files_for_job(root, "same.mp4", str(approved.relative_to(root))) == []
    assert storage.review_files_for_job(root, "same.mp4", str(uploaded.relative_to(root))) == []
    a.unlink()
    assert storage.review_files_for_job(root, "same.mp4", "https://drive.google.com/file/d/test/view") == [b]


@pytest.mark.parametrize("payload", [None, b""])
def test_ffmpeg_success_without_an_output_is_rejected(tmp_path, payload):
    import video_merger
    source = Path(video_merger.__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    process = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_video_sub_and_mute")
    command = next(n for n in ast.walk(process) if isinstance(n, ast.FunctionDef) and n.name == "run_cmd")
    output, partial = tmp_path / "out.mp4", tmp_path / "out.rendering.mp4"
    output.write_bytes(b"previous render")

    def run(*args, **kwargs):
        if payload is not None:
            partial.write_bytes(payload)

    scope = dict(ffmpeg_bin="ffmpeg", inputs=[], filters=[], audio_label=None, encoder_cfg={},
                 current_label="[v]", out_vid=output, tmp_out=partial,
                 subprocess=SimpleNamespace(run=run), _to_int=video_merger._to_int)
    exec(compile(ast.Module(body=[command], type_ignores=[]), str(source), "exec"), scope)
    with pytest.raises(RuntimeError, match="FFmpeg did not create"):
        scope["run_cmd"]("libx264", [])
    assert output.read_bytes() == b"previous render"
