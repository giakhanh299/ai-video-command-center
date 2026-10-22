"""ZeroTTS integration for Vietnamese SRT dubbing.

Supports:
- local built-in ZeroTTS voices (default: ``hamy`` for cute/animated delivery)
- local custom voice latent ``voice.npz`` packs obtained from ZeroWeight Audio Studio
- ZeroWeight hosted realtime API using an existing cloned ``voice_id``

Important: the public ZeroTTS package does NOT include the voice encoder needed to
create a new clone directly from a raw reference WAV. This module therefore never
pretends that a reference clip can be cloned locally. Use ``custom_voice_npz`` or
``backend=api`` + an existing cloned ``voice_id`` for that case.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import soundfile as sf


@dataclass
class SRTCue:
    index: int
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.01, self.end - self.start)


def _parse_timecode(value: str) -> float:
    value = value.strip().replace(".", ",")
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: str | Path) -> List[SRTCue]:
    p = Path(path)
    raw = p.read_text(encoding="utf-8-sig", errors="replace")
    blocks = re.split(r"\r?\n\s*\r?\n", raw.strip()) if raw.strip() else []
    cues: List[SRTCue] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_idx is None:
            continue
        try:
            idx = int(lines[0].strip()) if time_idx > 0 else len(cues) + 1
        except ValueError:
            idx = len(cues) + 1
        left, right = [x.strip() for x in lines[time_idx].split("-->", 1)]
        start = _parse_timecode(left.split()[0])
        end = _parse_timecode(right.split()[0])
        text = " ".join(x.strip() for x in lines[time_idx + 1 :] if x.strip())
        # Strip common inline SRT tags but keep visible punctuation/text.
        text = re.sub(r"<[^>]+>", "", text).strip()
        if text and end > start:
            cues.append(SRTCue(idx, start, end, text))
    return cues


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for candidate in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if os.path.exists(candidate):
            return candidate
    return "ffmpeg"


def _atempo_chain(factor: float) -> str:
    """Return an FFmpeg atempo chain for any positive factor."""
    factor = max(0.05, float(factor))
    parts: List[float] = []
    while factor > 2.0:
        parts.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        parts.append(0.5)
        factor /= 0.5
    parts.append(factor)
    return ",".join(f"atempo={p:.6f}" for p in parts)


def _fit_wav_to_slot(src: Path, dst: Path, target_sec: float, cfg: Dict[str, Any]) -> Path:
    info = sf.info(str(src))
    actual = float(info.duration)
    if actual <= 0.01 or target_sec <= 0.01:
        shutil.copy2(src, dst)
        return dst

    enabled = bool(cfg.get("enabled", True))
    fill_ratio = float(cfg.get("target_fill_ratio", 0.92))
    desired = max(0.05, target_sec * fill_ratio)
    max_speedup = max(1.0, float(cfg.get("max_speedup", 1.40)))
    max_slowdown = max(1.0, float(cfg.get("max_slowdown", 1.10)))
    stretch_short = bool(cfg.get("stretch_short", False))
    base_speed = max(0.5, float(cfg.get("base_speed", 1.0)))

    # atempo > 1 = faster/shorter. Apply channel style speed first.
    factor = base_speed
    styled_duration = actual / base_speed
    if enabled and styled_duration > desired:
        factor *= min(max_speedup, styled_duration / desired)
    elif enabled and stretch_short and styled_duration < desired:
        factor *= max(1.0 / max_slowdown, styled_duration / desired)

    if abs(factor - 1.0) < 0.01:
        shutil.copy2(src, dst)
        return dst

    cmd = [
        _ffmpeg(), "-y", "-loglevel", "error", "-i", str(src),
        "-filter:a", _atempo_chain(factor),
        "-ac", "1", str(dst),
    ]
    subprocess.run(cmd, check=True)
    return dst


def _resample_if_needed(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if src_rate == dst_rate:
        return audio
    try:
        from scipy.signal import resample_poly
        import math

        g = math.gcd(int(src_rate), int(dst_rate))
        return resample_poly(audio, dst_rate // g, src_rate // g).astype(np.float32)
    except Exception:
        # Linear fallback; acceptable for a final safety path, not preferred.
        n = max(1, int(round(len(audio) * dst_rate / src_rate)))
        x_old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
        x_new = np.linspace(0.0, 1.0, n, endpoint=False)
        return np.interp(x_new, x_old, audio).astype(np.float32)


def _voice_cache_key(text: str, cfg: Dict[str, Any]) -> str:
    npz_meta = None
    npz_value = cfg.get("custom_voice_npz")
    if npz_value:
        try:
            npz_path = Path(str(npz_value)).expanduser().resolve()
            st = npz_path.stat()
            npz_meta = {"path": str(npz_path), "size": st.st_size, "mtime_ns": st.st_mtime_ns}
        except OSError:
            npz_meta = {"path": str(npz_value), "missing": True}
    pack_meta = None
    pack_value = cfg.get("custom_voice_pack")
    if pack_value:
        try:
            pack_path = Path(str(pack_value)).expanduser().resolve()
            st = pack_path.stat()
            pack_meta = {"path": str(pack_path), "size": st.st_size, "mtime_ns": st.st_mtime_ns}
        except OSError:
            pack_meta = {"path": str(pack_value), "missing": True}
    relevant = {
        "engine": cfg.get("engine", "zerotts"),
        "backend": cfg.get("backend", "local"),
        "model": cfg.get("model", "zeroweight-ai/ZeroTTS"),
        "voice": cfg.get("voice", "hamy"),
        "voice_id": cfg.get("voice_id"),
        "custom_voice_npz": npz_meta,
        "custom_voice_pack": pack_meta,
        "voice_pack_name": cfg.get("voice_pack_name"),
        "normalize_vi": cfg.get("normalize_vi", True),
        "cfg_scale": cfg.get("cfg_scale", 1.0),
        "audio_temperature": cfg.get("audio_temperature", 0.8),
        "audio_topk": cfg.get("audio_topk", 25),
        "audio_topp": cfg.get("audio_topp", 0.95),
        "audio_repetition_penalty": cfg.get("audio_repetition_penalty", 1.2),
        "eoa_extra_frames": cfg.get("eoa_extra_frames", 1),
        "text": text,
    }
    raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:24]


class ZeroTTSLocal:
    def __init__(self, cfg: Dict[str, Any]):
        try:
            from zerotts import ZeroTTS, normalize_vi_text
        except ImportError as exc:
            raise RuntimeError(
                "Chưa cài ZeroTTS. Chạy: pip install zerotts>=0.1.5"
            ) from exc
        self._normalize_vi_text = normalize_vi_text
        self.cfg = cfg
        self.tts = ZeroTTS.from_pretrained(str(cfg.get("model", "zeroweight-ai/ZeroTTS")))
        self.sample_rate = int(getattr(self.tts, "sample_rate", 48000))
        self.voice = self._resolve_voice()

    def _resolve_voice(self):
        pack = self.cfg.get("custom_voice_pack")
        if pack:
            p = Path(str(pack)).expanduser().resolve()
            if not p.exists():
                raise FileNotFoundError(f"Không tìm thấy ZeroTTS voice pack: {p}")
            if not hasattr(self.tts, "add_voices"):
                raise RuntimeError(
                    "ZeroTTS runtime này chưa có add_voices(). Hãy cập nhật zerotts hoặc dùng custom_voice_npz."
                )
            before = set(self.tts.list_voices())
            self.tts.add_voices(str(p))
            requested = self.cfg.get("voice_pack_name")
            if requested:
                return str(requested)
            added = [name for name in self.tts.list_voices() if name not in before]
            if added:
                return added[0]
            # Most packs use the zip stem as installed name; validate lazily at synthesize time.
            return p.stem

        npz = self.cfg.get("custom_voice_npz")
        if npz:
            p = Path(str(npz)).expanduser().resolve()
            if not p.exists():
                raise FileNotFoundError(f"Không tìm thấy ZeroTTS voice latent: {p}")
            with np.load(str(p)) as data:
                if "voice_emb" not in data:
                    raise ValueError(f"{p.name} không có key 'voice_emb'")
                return np.asarray(data["voice_emb"], dtype=np.float32).copy()
        return str(self.cfg.get("voice", "hamy"))

    def synthesize(self, text: str, output: Path) -> Path:
        if bool(self.cfg.get("reference_audio_clone", False)):
            raise RuntimeError(
                "ZeroTTS public không có voice encoder để clone trực tiếp reference WAV. "
                "Hãy dùng custom_voice_pack/custom_voice_npz hoặc backend='api' với voice_id đã clone."
            )
        clean = text.strip()
        if bool(self.cfg.get("normalize_vi", True)):
            clean = self._normalize_vi_text(clean)
        kwargs = {
            "voice": self.voice,
            "cfg_scale": float(self.cfg.get("cfg_scale", 1.0)),
            "audio_temperature": float(self.cfg.get("audio_temperature", 0.8)),
            "audio_topk": int(self.cfg.get("audio_topk", 25)),
            "audio_topp": float(self.cfg.get("audio_topp", 0.95)),
            "audio_repetition_penalty": float(self.cfg.get("audio_repetition_penalty", 1.2)),
            "eoa_extra_frames": int(self.cfg.get("eoa_extra_frames", 1)),
        }
        audio = np.asarray(self.tts.synthesize(clean, **kwargs), dtype=np.float32).reshape(-1)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), audio, self.sample_rate, subtype="PCM_16")
        return output


async def _api_synthesize_many_async(texts: Sequence[str], outputs: Sequence[Path], cfg: Dict[str, Any]) -> None:
    try:
        import httpx
        import websockets
    except ImportError as exc:
        raise RuntimeError("API backend cần: pip install httpx websockets") from exc

    api_key = str(cfg.get("api_key") or os.environ.get(str(cfg.get("api_key_env", "ZEROWEIGHT_API_KEY")), "")).strip()
    if not api_key:
        raise RuntimeError(
            "Thiếu ZeroWeight API key. Đặt biến môi trường ZEROWEIGHT_API_KEY hoặc voice.api_key."
        )
    voice_id = str(cfg.get("voice_id") or cfg.get("voice") or "hamy")
    sample_rate = int(cfg.get("api_sample_rate", 24000))
    base_url = str(cfg.get("api_base_url", "https://api.zeroweight.ai")).rstrip("/")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{base_url}/api/v1/realtime/stream/session",
            headers={"X-ZW-Api-Key": api_key},
            json={"voice_id": voice_id, "format": "pcm_s16le", "sample_rate": sample_rate},
        )
        response.raise_for_status()
        session = response.json()

    async with websockets.connect(session["url"], max_size=None) as socket:
        for i, (text, output) in enumerate(zip(texts, outputs), 1):
            context_id = f"cue-{i}"
            await socket.send(json.dumps({
                "type": "synthesize",
                "context_id": context_id,
                "text": text,
                "segment_mode": "auto",
            }, ensure_ascii=False))
            await socket.send(json.dumps({"type": "end", "context_id": context_id}))
            pcm = bytearray()
            while True:
                frame = await socket.recv()
                if isinstance(frame, bytes):
                    if len(frame) > 12:
                        pcm.extend(frame[12:])
                    continue
                message = json.loads(frame)
                if message.get("type") == "context_done":
                    break
                if message.get("type") == "error":
                    raise RuntimeError(message.get("message", "ZeroWeight stream error"))
            output.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(sample_rate)
                out.writeframes(bytes(pcm))


def _api_synthesize_many(texts: Sequence[str], outputs: Sequence[Path], cfg: Dict[str, Any]) -> None:
    asyncio.run(_api_synthesize_many_async(texts, outputs, cfg))


def render_srt_voice_track(
    srt_path: str | Path,
    output_wav: str | Path,
    cfg: Dict[str, Any],
    video_duration: Optional[float] = None,
    cache_dir: Optional[str | Path] = None,
) -> str:
    """Generate a timeline-aligned Vietnamese dub from an SRT using ZeroTTS."""
    cues = parse_srt(srt_path)
    if not cues:
        raise ValueError(f"SRT không có cue hợp lệ: {srt_path}")

    out = Path(output_wav).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cache_root = Path(cache_dir).resolve() if cache_dir else out.parent / ".cache" / "zerotts"
    cache_root.mkdir(parents=True, exist_ok=True)
    raw_dir = cache_root / "raw"
    fit_dir = cache_root / "fit"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fit_dir.mkdir(parents=True, exist_ok=True)

    backend = str(cfg.get("backend", "local")).lower().strip()
    if backend not in {"local", "api"}:
        raise ValueError("voice.backend phải là 'local' hoặc 'api'")

    raw_paths: List[Path] = []
    missing_texts: List[str] = []
    missing_paths: List[Path] = []
    for cue in cues:
        key = _voice_cache_key(cue.text, cfg)
        p = raw_dir / f"{key}.wav"
        raw_paths.append(p)
        if not p.exists() or p.stat().st_size < 128:
            missing_texts.append(cue.text)
            missing_paths.append(p)

    if missing_paths:
        print(f"[ZeroTTS] Sinh {len(missing_paths)} câu mới; {len(cues)-len(missing_paths)} câu từ cache.")
        if backend == "local":
            engine = ZeroTTSLocal(cfg)
            for text, p in zip(missing_texts, missing_paths):
                engine.synthesize(text, p)
        else:
            _api_synthesize_many(missing_texts, missing_paths, cfg)
    else:
        print(f"[ZeroTTS] Dùng cache toàn bộ {len(cues)} câu.")

    # Fit each utterance conservatively into its subtitle time slot.
    fitted: List[Path] = []
    duration_cfg = cfg.get("duration_match", {}) or {}
    for cue, raw in zip(cues, raw_paths):
        fit_key = hashlib.sha1(
            (raw.name + json.dumps(duration_cfg, sort_keys=True) + f"|{cue.duration:.3f}").encode("utf-8")
        ).hexdigest()[:24]
        fit = fit_dir / f"{fit_key}.wav"
        if not fit.exists() or fit.stat().st_size < 128:
            _fit_wav_to_slot(raw, fit, cue.duration, duration_cfg)
        fitted.append(fit)

    # Determine one output sample rate, then mix cues onto the SRT timeline.
    first_info = sf.info(str(fitted[0]))
    sr = int(first_info.samplerate)
    total_sec = float(video_duration or max(c.end for c in cues))
    total_sec = max(total_sec, max(c.end for c in cues) + 0.05)
    master = np.zeros(max(1, int(np.ceil(total_sec * sr))), dtype=np.float32)
    gain = float(cfg.get("output_gain", 1.0))
    fade_ms = max(0.0, float(cfg.get("edge_fade_ms", 8.0)))

    for cue, fit in zip(cues, fitted):
        audio, cue_sr = sf.read(str(fit), dtype="float32", always_2d=False)
        if np.asarray(audio).ndim > 1:
            audio = np.asarray(audio).mean(axis=1)
        audio = _resample_if_needed(np.asarray(audio), int(cue_sr), sr)
        max_len = max(1, int(cue.duration * sr))
        if len(audio) > max_len:
            audio = audio[:max_len]
        # Tiny edge fade to avoid clicks from hard cue cuts.
        fade_n = min(len(audio) // 2, int(sr * fade_ms / 1000.0))
        if fade_n > 1:
            ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
            audio[:fade_n] *= ramp
            audio[-fade_n:] *= ramp[::-1]
        audio = audio.astype(np.float32) * gain
        start = max(0, int(round(cue.start * sr)))
        end = min(len(master), start + len(audio))
        if end > start:
            master[start:end] += audio[: end - start]

    peak = float(np.max(np.abs(master))) if len(master) else 0.0
    if peak > 0.98:
        master *= 0.98 / peak
    sf.write(str(out), master, sr, subtype="PCM_16")
    print(f"[ZeroTTS] Voice timeline: {out.name} | {len(cues)} cue | {sr} Hz")
    return str(out)
