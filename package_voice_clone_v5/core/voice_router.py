"""Multi-backend Vietnamese voice router with verified zero-shot voice cloning.

Priority path by default:
1) KhanhTTS / OmniVoice zero-shot clone (24 kHz, discrete acoustic tokens conditioning)
2) VieNeu-TTS v3 Turbo zero-shot clone (48 kHz, x-vector + MOSS audio codes)
3) ZeroTTS preset/custom-pack fallback (preset voice, strict fallback reporting)

Rules:
- No silent fallback: If primary clone fails, explicitly report CLONE_FAILED and mark clone_success=false.
- Cache integrity: Cache key includes SHA256 of reference audio binary bytes and reference text.
- VRAM management: Unload models and empty CUDA cache between backends.
- Duration matching bounds: 0.90 - 1.15 to avoid destroying cloned timbre and pitch.
"""
from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import soundfile as sf

from .zerotts_voice import (
    ZeroTTSLocal,
    _api_synthesize_many,
    _fit_wav_to_slot,
    _resample_if_needed,
    parse_srt,
)


class VoiceBackendError(RuntimeError):
    pass


class VoiceQualityError(VoiceBackendError):
    pass


@dataclass
class ReferenceVoice:
    audio: Optional[Path]
    text: Optional[str]


@dataclass
class BackendAttempt:
    backend: str
    ok: bool
    detail: str


def _path_meta(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    p = Path(value).expanduser()
    try:
        p = p.resolve()
        st = p.stat()
        return {"path": str(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns}
    except OSError:
        return {"path": str(p), "missing": True}


def _file_sha256(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except Exception:
        return ""


def _normalize_transcript(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    normalized = unicodedata.normalize("NFC", str(text).strip())
    return normalized if normalized else None


def _reference_from_config(
    srt_path: str | Path,
    cfg: Dict[str, Any],
    explicit_audio: Optional[str] = None,
    explicit_text: Optional[str] = None,
) -> ReferenceVoice:
    ref_cfg = cfg.get("reference", {}) or {}
    audio = explicit_audio or ref_cfg.get("audio")
    text = explicit_text if explicit_text is not None else ref_cfg.get("text")

    srt = Path(srt_path).resolve()
    if not audio and bool(ref_cfg.get("auto_sidecar", True)):
        suffix = str(ref_cfg.get("sidecar_audio_suffix", ".ref.wav"))
        candidate = srt.with_name(srt.stem + suffix)
        if candidate.exists():
            audio = str(candidate)

    if not text and bool(ref_cfg.get("auto_sidecar", True)):
        suffix = str(ref_cfg.get("sidecar_text_suffix", ".ref.txt"))
        candidate = srt.with_name(srt.stem + suffix)
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8-sig", errors="replace").strip()

    audio_path = None
    if audio:
        p = Path(str(audio)).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Voice reference not found: {p}")
        audio_path = p

    clean_text = _normalize_transcript(text)
    return ReferenceVoice(audio=audio_path, text=clean_text)


def _validate_reference(ref: ReferenceVoice, cfg: Dict[str, Any]) -> None:
    if not ref.audio:
        return
    info = sf.info(str(ref.audio))
    ref_cfg = cfg.get("reference", {}) or {}
    min_sec = float(ref_cfg.get("min_sec", 2.5))
    max_sec = float(ref_cfg.get("max_sec", 15.0))
    if info.duration < min_sec:
        raise VoiceBackendError(
            f"REFERENCE_AUDIO_BAD: Reference voice is too short ({info.duration:.2f}s); minimum required is {min_sec:.1f}s."
        )
    if info.duration > max_sec:
        print(
            f"[Voice] Warning: reference is {info.duration:.2f}s; recommended <= {max_sec:.1f}s. "
            "Backend will trim to optimal window."
        )


def _quality_check(path: Path, text: str, cfg: Dict[str, Any]) -> Dict[str, float]:
    gate = cfg.get("quality_gate", {}) or {}
    if not bool(gate.get("enabled", True)):
        return {"duration": float(sf.info(str(path)).duration)}
    audio, sr = sf.read(str(path), dtype="float32", always_2d=False)
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if x.size == 0 or not np.all(np.isfinite(x)):
        raise VoiceQualityError("Generated audio is empty or contains non-finite values.")
    duration = float(x.size / max(1, int(sr)))
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12))
    peak = float(np.max(np.abs(x)))
    clip_ratio = float(np.mean(np.abs(x) >= 0.995))
    min_duration = float(gate.get("min_duration_sec", 0.15))
    min_rms = float(gate.get("min_rms", 0.0015))
    max_clip = float(gate.get("max_clip_ratio", 0.08))
    if duration < min_duration:
        raise VoiceQualityError(f"Audio too short: {duration:.3f}s")
    if rms < min_rms:
        raise VoiceQualityError(f"Audio too quiet: rms={rms:.6f}")
    if clip_ratio > max_clip:
        raise VoiceQualityError(f"Audio clipping too high: ratio={clip_ratio:.4f}")
    return {"duration": duration, "rms": rms, "peak": peak, "clip_ratio": clip_ratio}


def _is_oom_or_cuda_error(exc: BaseException) -> bool:
    s = str(exc).lower()
    terms = (
        "out of memory", "cuda", "cublas", "cudnn", "allocation", "alloc failed",
        "device-side assert", "torch.cuda", "hip out of memory",
    )
    return any(t in s for t in terms)


def _log_vram(action: str) -> None:
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
            reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
            print(f"[VRAM] {action:<24} | Allocated: {allocated:.2f} GB | Reserved: {reserved:.2f} GB")
    except Exception:
        pass


def _empty_cuda_cache() -> None:
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                try:
                    torch.cuda.ipc_collect()
                except Exception:
                    pass
    except Exception:
        pass


class VoiceBackend:
    backend_id = "base"
    is_clone_backend = False

    def __init__(self, cfg: Dict[str, Any], reference: ReferenceVoice):
        self.cfg = cfg
        self.reference = reference
        self.sample_rate = 24000

    def synthesize(self, text: str, output: Path) -> Path:
        raise NotImplementedError

    def release(self) -> None:
        _log_vram(f"Before unload ({self.backend_id})")
        _empty_cuda_cache()
        _log_vram(f"After unload ({self.backend_id})")


class KhanhOmniVoiceBackend(VoiceBackend):
    backend_id = "khanh_omnivoice"
    is_clone_backend = True

    def __init__(self, cfg: Dict[str, Any], reference: ReferenceVoice):
        super().__init__(cfg, reference)
        if bool(cfg.get("require_reference", True)) and not reference.audio:
            raise VoiceBackendError("KhanhTTS clone requires a 3-10s reference audio clip.")
        try:
            import torch
            from omnivoice import OmniVoice
        except ImportError as exc:
            raise VoiceBackendError(
                "KhanhTTS backend is not installed. Install omnivoice and torch/torchaudio."
            ) from exc

        self.torch = torch
        requested = str(cfg.get("device", "auto")).lower()
        if requested == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            device = requested
        dtype_name = str(cfg.get("dtype", "auto")).lower()
        if dtype_name == "auto":
            dtype = torch.float16 if device.startswith("cuda") else torch.float32
        else:
            dtype = getattr(torch, dtype_name, torch.float16 if device.startswith("cuda") else torch.float32)

        _log_vram("Before load (KhanhTTS)")
        model_id = str(cfg.get("model", "kjanh/KhanhTTS-OmniVoice"))
        need_asr = (reference.audio is not None and not reference.text)
        self.model = OmniVoice.from_pretrained(model_id, device_map=device, dtype=dtype, load_asr=need_asr)
        self.sample_rate = int(getattr(self.model, "sampling_rate", 24000))
        _log_vram("After load (KhanhTTS)")

        # Precompute VoiceClonePrompt ONCE for the entire session
        self.prompt = None
        if self.reference.audio:
            self.prompt = self.model.create_voice_clone_prompt(
                ref_audio=str(self.reference.audio),
                ref_text=self.reference.text,
                preprocess_prompt=True,
            )
            print(
                f"[VOICE][KhanhTTS] Voice clone prompt pre-encoded | "
                f"Tokens: {tuple(self.prompt.ref_audio_tokens.shape)} | RMS: {self.prompt.ref_rms:.4f}"
            )
            if not self.reference.text:
                print(f"[VOICE][KhanhTTS] Auto-transcribed reference text: \"{self.prompt.ref_text}\"")

    def synthesize(self, text: str, output: Path) -> Path:
        kwargs: Dict[str, Any] = {
            "text": text.strip(),
            "language": self.cfg.get("language", "Vietnamese"),
            "num_step": int(self.cfg.get("steps", 16)),
        }
        if self.prompt is not None:
            kwargs["voice_clone_prompt"] = self.prompt
        elif self.reference.audio:
            kwargs["ref_audio"] = str(self.reference.audio)
            if self.reference.text:
                kwargs["ref_text"] = self.reference.text

        speed = float(self.cfg.get("speed", 1.0))
        if abs(speed - 1.0) > 0.001:
            kwargs["speed"] = speed

        try:
            result = self.model.generate(**kwargs)
        except TypeError:
            kwargs.pop("num_step", None)
            result = self.model.generate(**kwargs)

        audio = result[0] if isinstance(result, (list, tuple)) else result
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), audio, self.sample_rate, subtype="PCM_16")
        return output

    def release(self) -> None:
        self.prompt = None
        try:
            del self.model
        except Exception:
            pass
        self.model = None
        super().release()


class VieNeuBackend(VoiceBackend):
    backend_id = "vieneu"
    is_clone_backend = True

    def __init__(self, cfg: Dict[str, Any], reference: ReferenceVoice):
        super().__init__(cfg, reference)
        if bool(cfg.get("require_reference", True)) and not reference.audio:
            raise VoiceBackendError("VieNeu clone requires a 3-8s reference audio clip.")
        try:
            from vieneu import Vieneu
        except ImportError as exc:
            raise VoiceBackendError("VieNeu backend is not installed. Install package: vieneu") from exc

        mode = str(cfg.get("mode", "v3turbo"))
        device = str(cfg.get("device", "auto"))
        _log_vram("Before load (VieNeu)")
        self.tts = Vieneu(mode=mode, device=device)
        self.sample_rate = int(getattr(self.tts, "sample_rate", 48000))
        _log_vram("After load (VieNeu)")
        print(f"[VOICE][VieNeu] Loaded VieNeu-TTS ({mode}) | Sample rate: {self.sample_rate} Hz")

    def synthesize(self, text: str, output: Path) -> Path:
        kwargs: Dict[str, Any] = {
            "text": text.strip(),
            "denoise": bool(self.cfg.get("denoise", True)),
        }
        if self.reference.audio:
            kwargs["ref_audio"] = str(self.reference.audio)
        elif self.cfg.get("voice"):
            kwargs["voice"] = str(self.cfg.get("voice"))

        audio = self.tts.infer(**kwargs)
        if audio is None or len(audio) == 0:
            raise VoiceQualityError("VieNeu generated empty audio.")
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), audio, self.sample_rate, subtype="PCM_16")
        return output

    def release(self) -> None:
        try:
            del self.tts
        except Exception:
            pass
        self.tts = None
        super().release()


class ZeroTTSBackend(VoiceBackend):
    backend_id = "zerotts"
    is_clone_backend = False  # Preset voice, NOT a clone

    def __init__(self, cfg: Dict[str, Any], reference: ReferenceVoice):
        super().__init__(cfg, reference)
        self.mode = str(cfg.get("backend", "local")).lower()
        self.local = None
        if self.mode == "local":
            self.local = ZeroTTSLocal(cfg)
            self.sample_rate = int(getattr(self.local, "sample_rate", 48000))
        elif self.mode == "api":
            self.sample_rate = int(cfg.get("api_sample_rate", 24000))
        else:
            raise VoiceBackendError("ZeroTTS backend must be local or api.")

    def synthesize(self, text: str, output: Path) -> Path:
        if self.mode == "local":
            return self.local.synthesize(text, output)
        _api_synthesize_many([text], [output], self.cfg)
        return output

    def release(self) -> None:
        self.local = None
        super().release()


BACKEND_CLASSES = {
    "khanh_omnivoice": KhanhOmniVoiceBackend,
    "omnivoice": KhanhOmniVoiceBackend,
    "khanhtts": KhanhOmniVoiceBackend,
    "vieneu": VieNeuBackend,
    "zerotts": ZeroTTSBackend,
}


def _legacy_zerotts_candidate(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    c = dict(cfg)
    c["id"] = "zerotts"
    c["enabled"] = True
    return [c]


def _backend_candidates(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    engine = str(cfg.get("engine", "router")).lower()
    if engine == "zerotts":
        return _legacy_zerotts_candidate(cfg)
    router = cfg.get("router", {}) or {}
    candidates = router.get("backends", []) or []
    out: List[Dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict) or not bool(item.get("enabled", True)):
            continue
        out.append(dict(item))
    if not out:
        raise VoiceBackendError("No enabled voice backends in voice.router.backends.")
    return out


def _cache_key(
    text: str,
    cfg: Dict[str, Any],
    ref: ReferenceVoice,
    backend_id: str = "router",
    speed: float = 1.0,
    language: str = "Vietnamese",
) -> str:
    """Computes a cryptographically secure cache key incorporating audio binary content fingerprint."""
    ref_audio_hash = _file_sha256(ref.audio)
    ref_text_hash = hashlib.sha256((ref.text or "").encode("utf-8")).hexdigest()[:16]
    payload = {
        "schema": 5,
        "backend": backend_id,
        "text": text.strip(),
        "speed": round(float(speed), 3),
        "language": language,
        "ref_audio_hash": ref_audio_hash,
        "ref_text_hash": ref_text_hash,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _make_backend(candidate: Dict[str, Any], global_cfg: Dict[str, Any], ref: ReferenceVoice) -> VoiceBackend:
    backend_id = str(candidate.get("id", "")).lower().strip()
    cls = BACKEND_CLASSES.get(backend_id)
    if cls is None:
        raise VoiceBackendError(f"Unknown voice backend: {backend_id}")
    merged = dict(global_cfg)
    merged.update(candidate)
    merged.pop("router", None)
    return cls(merged, ref)


def _synthesize_missing(
    texts: Sequence[str],
    paths: Sequence[Path],
    cfg: Dict[str, Any],
    ref: ReferenceVoice,
) -> Tuple[List[str], List[BackendAttempt]]:
    remaining = list(zip(texts, paths))
    used: List[str] = []
    attempts: List[BackendAttempt] = []
    candidates = _backend_candidates(cfg)

    for candidate in candidates:
        if not remaining:
            break
        backend_id = str(candidate.get("id", "unknown"))
        backend: Optional[VoiceBackend] = None
        print(f"[Voice] Trying backend: {backend_id} ({len(remaining)} cue(s) remaining)")
        try:
            backend = _make_backend(candidate, cfg, ref)
            next_remaining = []
            for text, path in remaining:
                try:
                    tmp = path.with_suffix(".tmp.wav")
                    if tmp.exists():
                        tmp.unlink()
                    backend.synthesize(text, tmp)
                    _quality_check(tmp, text, cfg)
                    tmp.replace(path)
                    used.append(backend_id)
                except Exception as cue_exc:
                    if path.exists() and path.stat().st_size < 128:
                        path.unlink(missing_ok=True)
                    tmp = path.with_suffix(".tmp.wav")
                    tmp.unlink(missing_ok=True)
                    next_remaining.append((text, path))
                    detail = f"{type(cue_exc).__name__}: {cue_exc}"
                    attempts.append(BackendAttempt(backend_id, False, detail))
                    print(f"[VOICE][{backend_id.upper()}] STATUS: CLONE_FAILED | REASON: {detail}")
                    if _is_oom_or_cuda_error(cue_exc):
                        idx = remaining.index((text, path))
                        next_remaining.extend(remaining[idx + 1 :])
                        break
            remaining = next_remaining
            if not remaining:
                attempts.append(BackendAttempt(backend_id, True, "all remaining cues generated"))
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            attempts.append(BackendAttempt(backend_id, False, detail))
            print(f"[VOICE][{backend_id.upper()}] STATUS: CLONE_FAILED | REASON: {detail}")
        finally:
            if backend is not None:
                try:
                    backend.release()
                except Exception:
                    pass
            _empty_cuda_cache()

    if remaining:
        failed = ", ".join(p.name for _, p in remaining[:5])
        history = " | ".join(f"{a.backend}: {a.detail}" for a in attempts[-8:])
        raise VoiceBackendError(
            f"All voice backends failed for {len(remaining)} cue(s): {failed}. Attempts: {history}"
        )
    return used, attempts


def render_srt_voice_track(
    srt_path: str | Path,
    output_wav: str | Path,
    cfg: Dict[str, Any],
    video_duration: Optional[float] = None,
    cache_dir: Optional[str | Path] = None,
    reference_audio: Optional[str] = None,
    reference_text: Optional[str] = None,
) -> str:
    """Render timeline-aligned Vietnamese voice track with verified zero-shot clone and strict reporting."""
    cues = parse_srt(srt_path)
    if not cues:
        raise ValueError(f"SRT has no valid cues: {srt_path}")

    out = Path(output_wav).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cache_root = Path(cache_dir).resolve() if cache_dir else out.parent / ".cache" / "voice_router"
    raw_dir = cache_root / "raw"
    fit_dir = cache_root / "fit"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fit_dir.mkdir(parents=True, exist_ok=True)

    ref = _reference_from_config(srt_path, cfg, reference_audio, reference_text)
    try:
        _validate_reference(ref, cfg)
    except VoiceBackendError as exc:
        policy = str((cfg.get("reference", {}) or {}).get("invalid_policy", "fallback")).lower()
        if policy == "error":
            raise
        print(f"[Voice] Invalid clone reference: {exc}")
        ref = ReferenceVoice(audio=None, text=None)

    if ref.audio:
        print(f"[Voice] Clone reference: {ref.audio.name} ({sf.info(str(ref.audio)).duration:.2f}s)")
        if ref.text:
            print(f"[Voice] Clone reference transcript: \"{ref.text}\"")
    else:
        print("[Voice] No clone reference found. Router will fall back to preset voice.")

    raw_paths: List[Path] = []
    missing_texts: List[str] = []
    missing_paths: List[Path] = []
    speed = float(cfg.get("speed", 1.0))
    language = str(cfg.get("language", "Vietnamese"))

    for cue in cues:
        key = _cache_key(cue.text, cfg, ref, backend_id="router", speed=speed, language=language)
        p = raw_dir / f"{key}.wav"
        raw_paths.append(p)
        if not p.exists() or p.stat().st_size < 128:
            missing_texts.append(cue.text)
            missing_paths.append(p)

    attempts: List[BackendAttempt] = []
    used: List[str] = []
    if missing_paths:
        print(f"[Voice] Generate {len(missing_paths)} new cue(s); cache hit {len(cues) - len(missing_paths)}.")
        used, attempts = _synthesize_missing(missing_texts, missing_paths, cfg, ref)
    else:
        print(f"[Voice] Cache hit for all {len(cues)} cue(s).")

    duration_cfg = cfg.get("duration_match", {}) or {}
    fitted: List[Path] = []
    for cue, raw in zip(cues, raw_paths):
        fit_key = hashlib.sha1(
            (raw.name + json.dumps(duration_cfg, sort_keys=True) + f"|{cue.duration:.3f}").encode("utf-8")
        ).hexdigest()[:24]
        fit = fit_dir / f"{fit_key}.wav"
        if not fit.exists() or fit.stat().st_size < 128:
            _fit_wav_to_slot(raw, fit, cue.duration, duration_cfg)
        fitted.append(fit)

    first = sf.info(str(fitted[0]))
    sr = int(first.samplerate)
    total_sec = float(video_duration or max(c.end for c in cues))
    total_sec = max(total_sec, max(c.end for c in cues) + 0.05)
    master = np.zeros(max(1, int(np.ceil(total_sec * sr))), dtype=np.float32)
    gain = float(cfg.get("output_gain", 1.0))
    fade_ms = max(0.0, float(cfg.get("edge_fade_ms", 8.0)))

    for cue, fit in zip(cues, fitted):
        audio, cue_sr = sf.read(str(fit), dtype="float32", always_2d=False)
        x = np.asarray(audio, dtype=np.float32)
        if x.ndim > 1:
            x = x.mean(axis=1)
        x = _resample_if_needed(x, int(cue_sr), sr)
        max_len = max(1, int(cue.duration * sr))
        if len(x) > max_len:
            x = x[:max_len]
        fade_n = min(len(x) // 2, int(sr * fade_ms / 1000.0))
        if fade_n > 1:
            ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
            x[:fade_n] *= ramp
            x[-fade_n:] *= ramp[::-1]
        x *= gain
        start = max(0, int(round(cue.start * sr)))
        end = min(len(master), start + len(x))
        if end > start:
            master[start:end] += x[: end - start]

    peak = float(np.max(np.abs(master))) if len(master) else 0.0
    if peak > 0.98:
        master *= 0.98 / peak
    sf.write(str(out), master, sr, subtype="PCM_16")

    # Determine clone success and final mode
    used_set = set(used)
    final_backend = used[0] if used else "cached"
    is_zerotts = "zerotts" in used_set or (not used and cfg.get("engine") == "zerotts")
    clone_success = bool(ref.audio and not is_zerotts)
    final_mode = "cloned_voice" if clone_success else "preset_voice"

    if clone_success:
        print(f"[VOICE][{final_backend.upper()}] STATUS: CLONE_SUCCESS | REFERENCE: {ref.audio.name}")
    elif is_zerotts:
        voice_name = cfg.get("voice", "hamy")
        print(f"[VOICE][ZeroTTS] STATUS: FALLBACK_PRESET_VOICE | VOICE: {voice_name} | WARNING: ORIGINAL VOICE WAS NOT CLONED")

    report = {
        "requested_mode": "clone_original_voice",
        "reference_audio": str(ref.audio) if ref.audio else None,
        "reference_text": ref.text,
        "backend_attempts": [
            {
                "backend": a.backend,
                "status": "success" if a.ok else "failed",
                "detail": a.detail,
            }
            for a in attempts
        ],
        "final_backend": final_backend,
        "final_mode": final_mode,
        "clone_success": clone_success,
        "cue_count": len(cues),
        "new_cue_count": len(missing_paths),
        "output": str(out),
        "sample_rate": sr,
    }

    report_path = out.with_name(out.stem + "_voice_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    compat_report = dict(report)
    compat_report["engine"] = cfg.get("engine", "router")
    compat_report["backends_used_for_new_cues"] = sorted(set(used))
    compat_report["attempts"] = [a.__dict__ for a in attempts]
    out.with_name(out.stem + "_report.json").write_text(json.dumps(compat_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[Voice] Timeline ready: {out.name} | {len(cues)} cue(s) | {sr} Hz")
    return str(out)


def backend_status(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lightweight status check."""
    rows: List[Dict[str, Any]] = []
    for candidate in _backend_candidates(cfg):
        backend_id = str(candidate.get("id", ""))
        module = {
            "khanh_omnivoice": "omnivoice",
            "omnivoice": "omnivoice",
            "khanhtts": "omnivoice",
            "vieneu": "vieneu",
            "zerotts": "zerotts",
        }.get(backend_id, backend_id)
        rows.append({
            "backend": backend_id,
            "enabled": bool(candidate.get("enabled", True)),
            "module": module,
            "installed": bool(importlib.util.find_spec(module)) if module else False,
        })
    return rows
