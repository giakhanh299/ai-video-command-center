# dialogue_replace.py
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


AUDIO_SEP_PYTHON = r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Scripts\python.exe"
AUDIO_SEP_MODEL_DIR = r"D:/0.1_FACE_BOOK/Lay video tiktok/MODELS/audio_separator"
DEFAULT_MODEL = "UVR-MDX-NET-Inst_HQ_3.onnx"


def sha256_file(path, chunk_size=8 * 1024 * 1024):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)

    return h.hexdigest()


def run_checked(cmd):
    creationflags = 0

    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(map(str, cmd))
            + "\n\nSTDOUT:\n"
            + proc.stdout
            + "\n\nSTDERR:\n"
            + proc.stderr
        )

    return proc


def _get_ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    candidates = [
        r"C:\Users\w\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe",
        r"C:\Users\w\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            # Also add parent to PATH
            p = os.path.dirname(c)
            if p not in os.environ.get("PATH", ""):
                os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
            return c
    return "ffmpeg"


def extract_original_audio(video_path, wav_path):
    Path(wav_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cmd = [
        _get_ffmpeg_exe(),
        "-y",
        "-i", str(video_path),

        # chỉ extract audio để separator xử lý
        "-map", "0:a:0",

        "-vn",
        "-ac", "2",
        "-ar", "48000",
        "-c:a", "pcm_s16le",

        str(wav_path),
    ]

    run_checked(cmd)

    if not Path(wav_path).exists():
        raise RuntimeError(
            f"Không extract được audio: {wav_path}"
        )


def _parse_worker_json(stdout):
    lines = [
        x.strip()
        for x in stdout.splitlines()
        if x.strip()
    ]

    # audio-separator có thể log trước JSON,
    # vì vậy đọc từ dưới lên.
    for line in reversed(lines):
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("ok"):
                return obj
        except Exception:
            continue

    raise RuntimeError(
        "Không đọc được JSON từ audio_sep_worker:\n"
        + stdout
    )


def find_worker_script():
    candidates = [
        Path(__file__).resolve().parent / "audio_sep_worker.py",
        Path(__file__).resolve().parent.parent / "audio_sep_worker.py",
        Path(r"D:/0.1_FACE_BOOK/Lay video tiktok\audio_sep_worker.py"),
        Path(r"D:/0.1_FACE_BOOK/Lay video tiktok\backend\audio_sep_worker.py"),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c.resolve()
    raise FileNotFoundError("Không tìm thấy file audio_sep_worker.py")


def prepare_dialogue_replacement(
    video_path,
    cache_root,
    worker_script=None,
    model_filename=DEFAULT_MODEL,
    model_dir=AUDIO_SEP_MODEL_DIR,
    audio_sep_python=AUDIO_SEP_PYTHON,
    require_cuda=True,
):
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(video_path)

    if not Path(audio_sep_python).exists():
        raise RuntimeError(
            f"Không thấy audio-separator env: "
            f"{audio_sep_python}"
        )

    if worker_script is None:
        worker_script = find_worker_script()
    else:
        worker_script = Path(worker_script)

    if not worker_script.exists():
        raise FileNotFoundError(f"Worker script không tồn tại: {worker_script}")

    # Cache thay đổi nếu video hoặc model thay đổi.
    video_hash = sha256_file(video_path)

    cache_key = hashlib.sha256(
        (
            video_hash
            + "|"
            + model_filename
        ).encode("utf-8")
    ).hexdigest()

    job_dir = (
        Path(cache_root)
        / cache_key[:2]
        / cache_key
    )

    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    cached_instrumental = (
        job_dir / "instrumental.wav"
    )

    cached_vocals = (
        job_dir / "vocals.wav"
    )

    meta_file = job_dir / "meta.json"

    # CACHE HIT
    if (
        cached_instrumental.exists()
        and cached_instrumental.stat().st_size > 1000
    ):
        return {
            "cache_hit": True,
            "instrumental": str(cached_instrumental),
            "vocals": (
                str(cached_vocals)
                if cached_vocals.exists()
                else None
            ),
            "video_hash": video_hash,
        }

    source_wav = job_dir / "original_audio.wav"

    if not source_wav.exists():
        extract_original_audio(
            video_path,
            source_wav,
        )

    separator_out = job_dir / "separator_output"

    separator_out.mkdir(
        parents=True,
        exist_ok=True,
    )

    cmd = [
        str(audio_sep_python),
        str(worker_script),

        "--input",
        str(source_wav),

        "--output-dir",
        str(separator_out),

        "--model-dir",
        str(model_dir),

        "--model",
        str(model_filename),
    ]

    if require_cuda:
        cmd.append("--require-cuda")

    proc = run_checked(cmd)

    result = _parse_worker_json(
        proc.stdout
    )

    inst_src = Path(
        result["instrumental"]
    )

    if not inst_src.exists():
        raise RuntimeError(
            "audio-separator báo thành công "
            "nhưng không có Instrumental"
        )

    shutil.copy2(
        inst_src,
        cached_instrumental,
    )

    vocal_src = result.get("vocals")

    if vocal_src and Path(vocal_src).exists():
        shutil.copy2(
            vocal_src,
            cached_vocals,
        )

    metadata = {
        "video": str(video_path),
        "video_hash": video_hash,
        "cache_key": cache_key,
        "model": model_filename,
        "instrumental": str(cached_instrumental),
        "vocals": (
            str(cached_vocals)
            if cached_vocals.exists()
            else None
        ),
        "cuda": result.get("cuda"),
    }

    meta_file.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # source WAV rất lớn, không cần cache
    try:
        source_wav.unlink()
    except Exception:
        pass

    return {
        "cache_hit": False,
        "instrumental": str(cached_instrumental),
        "vocals": (
            str(cached_vocals)
            if cached_vocals.exists()
            else None
        ),
        "video_hash": video_hash,
    }


def final_mix_hard_replace(
    rendered_video,
    instrumental_file,
    new_voice_file,
    output_video,
    instrumental_volume=0.8,
):
    """
    QUAN TRỌNG:
    Input 0 audio KHÔNG xuất hiện trong filtergraph.
    [0:a] tuyệt đối không được mix vào output.
    """

    instrumental_volume = max(
        0.0,
        min(float(instrumental_volume), 2.0),
    )

    filter_complex = (
        f"[1:a]"
        f"aresample=48000,"
        f"volume={instrumental_volume}"
        f"[ainst];"

        f"[2:a]"
        f"aresample=48000"
        f"[avoice];"

        f"[ainst][avoice]"
        f"amix="
        f"inputs=2:"
        f"duration=first:"
        f"dropout_transition=0:"
        f"normalize=0,"
        f"alimiter=limit=0.95"
        f"[aout]"
    )

    cmd = [
        _get_ffmpeg_exe(),
        "-y",

        # input 0 = video đã render hình/sub/logo
        "-i", str(rendered_video),

        # input 1 = nền sạch
        "-i", str(instrumental_file),

        # input 2 = voice/TTS mới
        "-i", str(new_voice_file),

        "-filter_complex",
        filter_complex,

        # VIDEO ONLY từ input 0
        "-map", "0:v:0",

        # AUDIO ONLY từ filter output
        "-map", "[aout]",

        "-c:v", "copy",

        "-c:a", "aac",
        "-b:a", "256k",

        "-shortest",

        str(output_video),
    ]

    run_checked(cmd)

    return str(output_video)


def apply_final_audio(
    original_video,
    rendered_video,
    tts_voice_file,
    final_output,
    channel_config,
):
    """
    Áp dụng lồng tiếng và thay thế hoàn toàn thoại gốc.
    DÙNG CHUNG cho cả Wuby lẫn Cấu hình 2 (VideoMerger).
    
    LUẬT BẮT BUỘC:
    Nếu hard_replace: true mà separator lỗi, PHẢI FAIL NGAY.
    TUYỆT ĐỐI KHÔNG FALLBACK VỀ AUDIO GỐC để tránh lọt tiếng Trung/tiếng gốc.
    """
    cfg = channel_config.get("dialogue_replace", {}) if isinstance(channel_config, dict) else {}
    if not cfg.get("enabled", False):
        if str(rendered_video) != str(final_output):
            shutil.copy2(rendered_video, final_output)
        return str(final_output)

    hard_replace = bool(cfg.get("hard_replace", True))
    if not hard_replace:
        # Nếu không bật hard replace thì giữ nguyên
        if str(rendered_video) != str(final_output):
            shutil.copy2(rendered_video, final_output)
        return str(final_output)

    # Bóc tách nhạc nền (Instrumental)
    try:
        stems = prepare_dialogue_replacement(
            video_path=original_video,
            cache_root=cfg.get("cache_dir", r"cache\audio_stems"),
            worker_script=cfg.get("worker_script"),
            model_filename=cfg.get("model_filename", DEFAULT_MODEL),
            model_dir=cfg.get("model_file_dir", AUDIO_SEP_MODEL_DIR),
            audio_sep_python=cfg.get("separator_python", AUDIO_SEP_PYTHON),
            require_cuda=bool(cfg.get("require_cuda", True)),
        )
    except Exception as exc:
        # LUẬT BẮT BUỘC: KHÔNG FALLBACK VỀ AUDIO GỐC
        raise RuntimeError(
            f"[FATAL] Bóc tách âm thanh thất bại (hard_replace=True). "
            f"Không được phép fallback âm thanh gốc để tránh lọt tiếng gốc: {exc}"
        ) from exc

    instrumental_file = stems.get("instrumental")
    if not instrumental_file or not Path(instrumental_file).exists():
        raise RuntimeError(
            "[FATAL] Không tìm thấy file Instrumental sạch sau khi bóc tách. "
            "Render bị dừng để tránh lọt tiếng thoại gốc."
        )

    instrumental_volume = cfg.get("instrumental_volume", 0.8)

    # Ghép âm thanh cuối cùng: [ainst] + [avoice] (hoàn toàn KHÔNG CÓ [0:a])
    final_mix_hard_replace(
        rendered_video=rendered_video,
        instrumental_file=instrumental_file,
        new_voice_file=tts_voice_file,
        output_video=final_output,
        instrumental_volume=instrumental_volume,
    )

    return str(final_output)
