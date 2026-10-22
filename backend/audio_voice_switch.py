from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("FFMPEG_NOT_FOUND")
    return exe


def _cache_key(path: str, fingerprint: str) -> str:
    p = Path(path)
    st = p.stat()
    raw = f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}|{fingerprint}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]




def probe_audio_stream(input_media: str) -> dict[str, Any]:
    """Inspect the first audio stream without decoding the whole file."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"channels": 0, "channel_layout": "", "codec_name": "", "sample_rate": 0}
    cmd = [
        ffprobe, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=channels,channel_layout,codec_name,sample_rate",
        "-of", "json", str(input_media),
    ]
    try:
        cp = subprocess.run(cmd, check=True, capture_output=True, text=True)
        payload = json.loads(cp.stdout or "{}")
        stream = (payload.get("streams") or [{}])[0]
        return {
            "channels": int(stream.get("channels") or 0),
            "channel_layout": str(stream.get("channel_layout") or ""),
            "codec_name": str(stream.get("codec_name") or ""),
            "sample_rate": int(stream.get("sample_rate") or 0),
        }
    except Exception as exc:
        return {"channels": 0, "channel_layout": "", "codec_name": "", "sample_rate": 0, "probe_error": type(exc).__name__}


def _extract_surround_background(input_media: str, output_wav: Path, channels: int) -> Path:
    """Downmix multichannel audio to stereo while deliberately omitting the center channel.

    Movie dialogue is commonly center-heavy. Surround/LFE channels are retained so music,
    ambience and effects survive far better than a generic center-cancel.
    """
    if channels < 6:
        raise RuntimeError(f"SURROUND_REQUIRED:{channels}ch")
    if channels >= 8:
        # Typical 7.1 order: FL FR FC LFE BL BR SL SR. Omit c2 (FC).
        pan = "pan=stereo|c0=0.78*c0+0.32*c4+0.32*c6+0.16*c3|c1=0.78*c1+0.32*c5+0.32*c7+0.16*c3"
    else:
        # Typical 5.1 / 5.1(side): FL FR FC LFE B/SL B/SR. Omit c2 (FC).
        pan = "pan=stereo|c0=0.82*c0+0.52*c4+0.16*c3|c1=0.82*c1+0.52*c5+0.16*c3"
    subprocess.run([
        _ffmpeg(), "-y", "-v", "error", "-i", str(input_media), "-vn",
        "-af", f"{pan},alimiter=limit=0.95", "-ar", "44100", "-c:a", "pcm_s16le", str(output_wav),
    ], check=True)
    if not output_wav.exists() or output_wav.stat().st_size < 1000:
        raise RuntimeError("SURROUND_BACKGROUND_OUTPUT_MISSING")
    return output_wav


def _extract_wav(input_video: str, output_wav: Path) -> None:
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", str(input_video), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(output_wav)], check=True)


def _run_demucs(source_wav: Path, cache_dir: Path, model: str) -> Path:
    if importlib.util.find_spec("demucs") is None:
        raise RuntimeError("DEMUCS_NOT_INSTALLED: pip install demucs")
    out_root = cache_dir / "demucs_out"
    cmd = [sys.executable, "-m", "demucs.separate", "--two-stems=vocals", "-n", model, "-o", str(out_root), str(source_wav)]
    subprocess.run(cmd, check=True)
    candidates = list(out_root.glob(f"{model}/**/no_vocals.wav"))
    if not candidates:
        candidates = list(out_root.glob("**/no_vocals.wav"))
    if not candidates:
        raise RuntimeError("DEMUCS_NO_VOCALS_OUTPUT_MISSING")
    return candidates[0]


def _run_ai_separator(source_wav: Path, cache_dir: Path, model: str) -> tuple[Path, str]:
    """Run AI separation prioritizing audio-separator[gpu], falling back to Demucs."""
    try:
        try:
            from .audio_separator_runner import separate_audio, is_audio_separator_available, DEFAULT_MODEL
        except ImportError:
            from audio_separator_runner import separate_audio, is_audio_separator_available, DEFAULT_MODEL

        if is_audio_separator_available():
            sep_model = model if model and model.endswith((".onnx", ".ckpt", ".yaml")) else DEFAULT_MODEL
            out_root = cache_dir / "audio_sep_out"
            res = separate_audio(audio_path=source_wav, output_dir=out_root, model_name=sep_model)
            inst = res.get("instrumental")
            if inst and Path(inst).exists() and Path(inst).stat().st_size > 1000:
                return Path(inst), f"audio_separator:{sep_model}"
    except Exception as exc:
        # If audio_separator failed, attempt demucs fallback
        pass

    # Demucs fallback
    demucs_out = _run_demucs(source_wav, cache_dir, model)
    return demucs_out, f"demucs:{model}"



def _center_cancel(source_wav: Path, output_wav: Path) -> Path:
    # Fallback only: cancels center content and can also affect centered music/SFX.
    subprocess.run([
        _ffmpeg(), "-y", "-v", "error", "-i", str(source_wav),
        "-af", "pan=stereo|c0=c0-c1|c1=c1-c0", "-c:a", "pcm_s16le", str(output_wav)
    ], check=True)
    return output_wav


def _smooth_binary_mask(binary: np.ndarray, rate: int, attack_ms: float, release_ms: float) -> np.ndarray:
    y = binary.astype(np.float32, copy=True)
    attack = max(1, int(rate * attack_ms / 1000.0))
    release = max(1, int(rate * release_ms / 1000.0))
    on = np.flatnonzero(binary > 0.5)
    if len(on) == 0:
        return y
    starts = on[np.r_[True, np.diff(on) > 1]]
    ends = on[np.r_[np.diff(on) > 1, True]]
    for s, e in zip(starts, ends):
        a0 = max(0, s - attack)
        if s > a0:
            y[a0:s] = np.maximum(y[a0:s], np.linspace(0.0, 1.0, s - a0, endpoint=False, dtype=np.float32))
        r1 = min(len(y), e + 1 + release)
        if r1 > e + 1:
            y[e + 1:r1] = np.maximum(y[e + 1:r1], np.linspace(1.0, 0.0, r1 - e - 1, endpoint=False, dtype=np.float32))
    return np.clip(y, 0.0, 1.0)


def build_voice_activity_masks(voice_audio: str, out_dir: Path, cfg: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    data, sr = sf.read(str(voice_audio), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    rate = int(cfg.get("mask_rate", 1000))
    hop = max(1, int(sr / rate))
    usable = len(mono) // hop * hop
    if usable <= 0:
        raise RuntimeError("VOICE_AUDIO_EMPTY")
    blocks = mono[:usable].reshape(-1, hop)
    rms = np.sqrt(np.mean(blocks.astype(np.float64) ** 2, axis=1)).astype(np.float32)
    peak = float(np.max(rms)) if len(rms) else 0.0
    threshold = max(float(cfg.get("absolute_threshold", 0.003)), peak * float(cfg.get("relative_threshold", 0.035)))
    active = (rms >= threshold).astype(np.float32)

    # Fill short internal gaps so breaths do not make original dialogue pop back in.
    max_gap = max(0, int(rate * float(cfg.get("fill_gap_ms", 180.0)) / 1000.0))
    if max_gap > 0:
        zeros = np.flatnonzero(active < 0.5)
        if len(zeros):
            starts = zeros[np.r_[True, np.diff(zeros) > 1]]
            ends = zeros[np.r_[np.diff(zeros) > 1, True]]
            for s, e in zip(starts, ends):
                if s > 0 and e + 1 < len(active) and (e - s + 1) <= max_gap:
                    active[s:e + 1] = 1.0

    mask = _smooth_binary_mask(active, rate, float(cfg.get("attack_ms", 80.0)), float(cfg.get("release_ms", 220.0)))
    orig = 1.0 - mask
    voice_mask = out_dir / "tts_active_mask.wav"
    original_mask = out_dir / "original_active_mask.wav"
    sf.write(str(voice_mask), mask, rate, subtype="FLOAT")
    sf.write(str(original_mask), orig, rate, subtype="FLOAT")
    meta = {"mask_rate": rate, "threshold": threshold, "active_ratio": float(np.mean(active)), "attack_ms": cfg.get("attack_ms", 80.0), "release_ms": cfg.get("release_ms", 220.0)}
    return voice_mask, original_mask, meta




def build_segment_activity_masks(segments: list[dict[str, Any]], duration_sec: float, out_dir: Path, cfg: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    """Build a speech mask from original Whisper timings, not from TTS waveform.

    This prevents the original voice from leaking through when the Vietnamese TTS is
    shorter, has pauses, or duration matching leaves a small gap.
    """
    rate = int(cfg.get("mask_rate", 1000))
    total = max(1, int(max(0.1, duration_sec) * rate))
    active = np.zeros(total, dtype=np.float32)
    pre = float(cfg.get("speech_pre_padding_ms", 100.0)) / 1000.0
    post = float(cfg.get("speech_post_padding_ms", 220.0)) / 1000.0
    used = 0
    for seg in segments or []:
        try:
            st = max(0.0, float(seg.get("start", 0.0)) - pre)
            en = min(duration_sec, float(seg.get("end", st)) + post)
        except Exception:
            continue
        if en <= st:
            continue
        i0 = max(0, min(total, int(st * rate)))
        i1 = max(i0, min(total, int(en * rate)))
        active[i0:i1] = 1.0
        used += 1
    mask = _smooth_binary_mask(active, rate, float(cfg.get("attack_ms", 60.0)), float(cfg.get("release_ms", 180.0)))
    orig = 1.0 - mask
    voice_mask = out_dir / "original_speech_mask.wav"
    original_mask = out_dir / "original_non_speech_mask.wav"
    sf.write(str(voice_mask), mask, rate, subtype="FLOAT")
    sf.write(str(original_mask), orig, rate, subtype="FLOAT")
    meta = {
        "mask_rate": rate, "source": "whisper_segments", "segment_count": used,
        "active_ratio": float(np.mean(active)), "speech_pre_padding_ms": pre * 1000.0,
        "speech_post_padding_ms": post * 1000.0,
    }
    return voice_mask, original_mask, meta


def prepare_dialogue_replacement(input_video: str, voice_audio: str, work_dir: str | Path, cfg: dict[str, Any], segments: list[dict[str, Any]] | None = None) -> dict[str, str]:
    """Prepare clean/background audio and control masks for Vietnamese dubbing.

    strategy=ai_first: Demucs -> center-cancel fallback.
    strategy=surround_first: for >=5.1 omit center channel -> Demucs -> center-cancel fallback.
    mask_source=whisper_segments: original audio is preserved only outside original speech windows.
    """
    work = Path(work_dir)
    model = str(cfg.get("separator_model", "htdemucs"))
    strategy = str(cfg.get("strategy", "ai_first")).strip().lower() or "ai_first"
    probe = probe_audio_stream(input_video)
    fingerprint = f"{strategy}|{model}|{probe.get('channels', 0)}|{probe.get('channel_layout', '')}"
    cache = work / f"audio_replace_{_cache_key(input_video, fingerprint)}"
    cache.mkdir(parents=True, exist_ok=True)
    source_wav = cache / "original_44100.wav"
    if not source_wav.exists() or source_wav.stat().st_size < 1000:
        _extract_wav(input_video, source_wav)

    instrumental = cache / "instrumental.wav"
    manifest_path = cache / "manifest.json"
    previous_method = ""
    if manifest_path.exists():
        try:
            previous_method = str(json.loads(manifest_path.read_text(encoding="utf-8")).get("separator") or "")
        except Exception:
            previous_method = ""

    sep_method = previous_method or "cache"
    needs_build = not instrumental.exists() or instrumental.stat().st_size < 1000
    if needs_build:
        surround_done = False
        if strategy == "surround_first" and int(probe.get("channels") or 0) >= int(cfg.get("surround_min_channels", 6)):
            try:
                _extract_surround_background(input_video, instrumental, int(probe.get("channels") or 0))
                sep_method = f"surround_center_omit:{probe.get('channels')}ch:{probe.get('channel_layout') or 'unknown'}"
                surround_done = True
            except Exception as exc:
                sep_method = f"surround_failed:{type(exc).__name__}"

        if not surround_done:
            try:
                sep_out, sep_method = _run_ai_separator(source_wav, cache, model)
                shutil.copy2(sep_out, instrumental)
            except Exception as exc:
                if bool(cfg.get("require_separator", False)):
                    raise
                fallback = str(cfg.get("fallback", "center_cancel")).lower()
                if fallback != "center_cancel":
                    raise RuntimeError(f"SEPARATOR_FAILED:{exc}") from exc
                _center_cancel(source_wav, instrumental)
                sep_method = f"center_cancel_fallback:{type(exc).__name__}"

    mask_source = str(cfg.get("mask_source", "tts_waveform")).strip().lower()
    duration_sec = float(sf.info(str(source_wav)).duration)
    if mask_source in {"whisper", "whisper_segments", "segments"} and segments:
        voice_mask, original_mask, mask_meta = build_segment_activity_masks(segments, duration_sec, cache, cfg)
    else:
        voice_mask, original_mask, mask_meta = build_voice_activity_masks(voice_audio, cache, cfg)

    # For surround sources, center omission alone can still leak dialogue into L/R.
    # Build a second, more aggressively cleaned bed and use it ONLY inside Whisper
    # speech windows. Outside speech windows we keep the richer surround background.
    speech_instrumental: Path | None = None
    speech_cleanup_method = ""
    if strategy == "surround_first" and bool(cfg.get("speech_cleanup", True)):
        speech_instrumental = cache / "speech_instrumental.wav"
        if not speech_instrumental.exists() or speech_instrumental.stat().st_size < 1000:
            try:
                clean_root = cache / "speech_cleanup"
                clean_out, speech_cleanup_method = _run_ai_separator(instrumental, clean_root, model)
                shutil.copy2(clean_out, speech_instrumental)
            except Exception as exc:
                # Dependency-free fallback. This is deliberately used only during
                # speech windows so it cannot hollow out the soundtrack everywhere.
                _center_cancel(instrumental, speech_instrumental)
                speech_cleanup_method = f"center_cancel_after_surround:{type(exc).__name__}"
        else:
            speech_cleanup_method = "cache"

    manifest = {
        "input_video": str(input_video),
        "voice_audio": str(voice_audio),
        "instrumental": str(instrumental),
        "speech_instrumental": str(speech_instrumental) if speech_instrumental else "",
        "voice_mask": str(voice_mask),
        "original_mask": str(original_mask),
        "separator": sep_method,
        "speech_cleanup": speech_cleanup_method,
        "strategy": strategy,
        "audio_probe": probe,
        "mask": mask_meta,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # Keep scalar metadata string-friendly for current renderer/debug output.
    out = {k: str(v) for k, v in manifest.items() if isinstance(v, str)}
    out["audio_channels"] = str(probe.get("channels") or 0)
    out["audio_layout"] = str(probe.get("channel_layout") or "")
    return out

