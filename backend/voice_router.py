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
import sys as _v7_sys
_v7_project = str(Path(__file__).resolve().parents[1])
if _v7_project not in _v7_sys.path:
    _v7_sys.path.insert(0, _v7_project)
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import soundfile as sf

try:
    from .zerotts_voice import (
        ZeroTTSLocal,
        _api_synthesize_many,
        _fit_wav_to_slot,
        _resample_if_needed,
        parse_srt,
    )
except ImportError:
    from zerotts_voice import (
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


def _reference_from_config(srt_path, cfg, explicit_audio=None, explicit_text=None):
    from wuby_studio.common import ROOT
    ref_cfg=cfg.get("reference") or {}
    audio=explicit_audio or ref_cfg.get("audio") or cfg.get("ref_audio")
    text=explicit_text if explicit_text is not None else ref_cfg.get("text",cfg.get("ref_text"))
    root=Path(cfg.get("project_root") or ROOT).resolve();srt=Path(srt_path).resolve()
    if not audio and ref_cfg.get("auto_sidecar",True):
        p=srt.with_suffix(".ref.wav")
        if p.is_file():audio=str(p)
    p=None
    if audio:
        raw=Path(str(audio)).expanduser()
        choices=[raw] if raw.is_absolute() else [root/raw,root/"voice_samples"/raw,srt.parent/raw]
        p=next((c.resolve() for c in choices if c.is_file()),None)
        if p is None:raise VoiceBackendError(f"REFERENCE_AUDIO_MISSING: {audio}")
        if not text:
            for candidate in (p.with_suffix(".txt"),p.with_suffix(".ref.txt")):
                if candidate.is_file():text=candidate.read_text(encoding="utf-8-sig").strip();break
    return ReferenceVoice(p,_normalize_transcript(text))


def _validate_reference(ref: ReferenceVoice, cfg: Dict[str, Any]) -> None:
    if not ref.audio:
        if bool(cfg.get("require_clone", False)):
            raise VoiceBackendError(
                "REFERENCE_AUDIO_MISSING: Profile yêu cầu bắt buộc clone (require_clone=True) "
                "nhưng không tìm thấy file âm thanh mẫu (ref_audio)."
            )
        return
    info = sf.info(str(ref.audio))
    ref_cfg = cfg.get("reference", {}) or {}
    min_sec = float(ref_cfg.get("min_sec", 2.0))
    max_sec = float(ref_cfg.get("max_sec", 15.0))
    if info.duration < min_sec:
        raise VoiceBackendError(
            f"REFERENCE_AUDIO_BAD: Reference voice is too short ({info.duration:.2f}s); minimum required is {min_sec:.1f}s."
        )
    if info.duration > max_sec:
        print(
            f"[Voice] Warning: reference is {info.duration:.2f}s; recommended <= {max_sec:.1f}s. "
            "Review the reference; no automatic trim is promised."
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
            import sys
            source_root = Path(__file__).resolve().parent.parent / "OmniVoice"
            if source_root.is_dir() and str(source_root) not in sys.path:
                sys.path.insert(0,str(source_root))
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
        clean_text = text.strip()
        try:
            from .vi_text_normalizer import normalize_vietnamese_text
            clean_text = normalize_vietnamese_text(clean_text)
        except Exception:
            try:
                from vi_text_normalizer import normalize_vietnamese_text
                clean_text = normalize_vietnamese_text(clean_text)
            except Exception:
                pass
        kwargs: Dict[str, Any] = {
            "text": clean_text,
            "language": self.cfg.get("language", "Vietnamese"),
            "num_step": int(self.cfg.get("num_step", self.cfg.get("steps", 20))),
            "guidance_scale": float(self.cfg.get("guidance_scale", 2.0)),
        }
        if self.prompt is not None:
            kwargs["voice_clone_prompt"] = self.prompt
        elif self.reference.audio:
            kwargs["ref_audio"] = str(self.reference.audio)
            if self.reference.text:
                kwargs["ref_text"] = self.reference.text

        speed = float(self.cfg.get("synthesis_speed", self.cfg.get("speed", 1.0)))
        if abs(speed - 1.0) > 0.001:
            kwargs["speed"] = speed

        result = self.model.generate(**kwargs)

        audio = result[0] if isinstance(result, (list, tuple)) else result
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output), audio, self.sample_rate, subtype="PCM_16")
        return output

    def synthesize_batch(self, texts: Sequence[str], outputs: Sequence[Path]) -> None:
        """Use OmniVoice's native list API, retaining one reference and voice."""
        if len(texts) != len(outputs) or not texts or len(texts) > 4:
            raise ValueError('INVALID_OMNIVOICE_BATCH')
        try:
            from .vi_text_normalizer import normalize_vietnamese_text
        except ImportError:
            from vi_text_normalizer import normalize_vietnamese_text
        kwargs = {
            'text': [normalize_vietnamese_text(text.strip()) for text in texts],
            'language': self.cfg.get('language', 'Vietnamese'),
            'num_step': int(self.cfg.get('num_step', self.cfg.get('steps', 20))),
            'guidance_scale': float(self.cfg.get('guidance_scale', 2.0)),
        }
        if self.prompt is not None:
            kwargs['voice_clone_prompt'] = self.prompt
        elif self.reference.audio:
            kwargs['ref_audio'] = str(self.reference.audio)
            kwargs['ref_text'] = self.reference.text
        speed = float(self.cfg.get('synthesis_speed', self.cfg.get('speed', 1.0)))
        if abs(speed - 1.0) > .001:
            kwargs['speed'] = speed
        results = self.model.generate(**kwargs)
        if not isinstance(results, (list, tuple)) or len(results) != len(outputs):
            raise VoiceBackendError('OMNIVOICE_BATCH_RESULT_COUNT_MISMATCH')
        for audio, output in zip(results, outputs):
            output.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output), np.asarray(audio, dtype=np.float32).reshape(-1), self.sample_rate, subtype='PCM_16')

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
    require_clone = bool(cfg.get("require_clone", False))

    if engine == "zerotts":
        if require_clone:
            raise VoiceBackendError("Engine 'zerotts' là giọng preset mẫu, không thể dùng khi require_clone=True.")
        return _legacy_zerotts_candidate(cfg)

    if engine in {"omnivoice", "khanh_omnivoice", "khanhtts"}:
        out = [{"id": "khanh_omnivoice", "enabled": True, "model": cfg.get("model", "kjanh/KhanhTTS-OmniVoice")}]
        if not require_clone:
            out.append({"id": "zerotts", "enabled": True})
        return out

    if engine == "vieneu":
        out = [{"id": "vieneu", "enabled": True}]
        if not require_clone:
            out.append({"id": "zerotts", "enabled": True})
        return out

    if engine != "router":
        raise VoiceBackendError(f"UNKNOWN_TTS_ENGINE: {engine}")
    router = cfg.get("router", {}) or {}
    candidates = router.get("backends", []) or []
    out: List[Dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict) or not bool(item.get("enabled", True)):
            continue
        bid = str(item.get("id", "")).lower()
        if require_clone and bid == "zerotts":
            continue
        out.append(dict(item))

    if not out:
        out = [
            {"id": "khanh_omnivoice", "enabled": True, "model": cfg.get("model", "kjanh/KhanhTTS-OmniVoice")},
            {"id": "vieneu", "enabled": True},
        ]
        if not require_clone:
            out.append({"id": "zerotts", "enabled": True})

    if not out:
        raise VoiceBackendError("Không tìm thấy backend khả dụng cho cấu hình giọng này.")
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
        "schema": 6,
        "backend": backend_id,
        "model": str(cfg.get("model", "")),
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
    require_clone = bool(cfg.get("require_clone", False))

    for candidate in candidates:
        if not remaining:
            break
        backend_id = str(candidate.get("id", "unknown"))
        backend: Optional[VoiceBackend] = None
        print(f"[Voice] Trying backend: {backend_id} ({len(remaining)} cue(s) remaining)")
        try:
            backend = _make_backend(candidate, cfg, ref)
            next_remaining = []
            batch_size = max(1, min(4, int(cfg.get('synthesis_batch_size', os.getenv('DOUYIN_VOICE_BATCH_SIZE', '1')))))
            quality_retry_count = max(0, min(2, int(cfg.get('quality_retry_count', 1))))
            prefetched = set()
            for cue_index, (text, path) in enumerate(remaining):
                if batch_size > 1 and cue_index % batch_size == 0 and callable(getattr(backend, 'synthesize_batch', None)):
                    group = remaining[cue_index:cue_index + batch_size]
                    temporary = [p.with_suffix('.tmp.wav') for _, p in group]
                    try:
                        for p in temporary:p.unlink(missing_ok=True)
                        backend.synthesize_batch([t for t, _ in group], temporary)
                        prefetched.update(temporary)
                    except Exception:
                        # Same model, same reference; fall back to single cues
                        # on a batch-memory or batch-API failure.
                        for p in temporary:p.unlink(missing_ok=True)
                        try:
                            import torch
                            torch.cuda.empty_cache()
                        except Exception:
                            pass
                try:
                    tmp = path.with_suffix(".tmp.wav")
                    for quality_attempt in range(quality_retry_count + 1):
                        try:
                            if quality_attempt or tmp not in prefetched:
                                if tmp.exists():tmp.unlink()
                                backend.synthesize(text, tmp)
                            _quality_check(tmp, text, cfg)
                            break
                        except VoiceQualityError:
                            prefetched.discard(tmp)
                            tmp.unlink(missing_ok=True)
                            if quality_attempt >= quality_retry_count:
                                raise
                            _empty_cuda_cache()
                    tmp.replace(path)
                    prefetched.discard(tmp)

                    # Save sidecar metadata verifying actual backend and clone status
                    meta_path = path.with_suffix(".meta.json")
                    meta_info = {
                        "backend": backend_id,
                        "is_clone": bool(getattr(backend, "is_clone_backend", False) and ref.audio),
                        "model": str(candidate.get("model", "")),
                        "text": text,
                    }
                    meta_path.write_text(json.dumps(meta_info, ensure_ascii=False, indent=2), encoding="utf-8")

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
        msg = f"Tất cả voice backends đều thất bại cho {len(remaining)} câu: {failed}. Chi tiết: {history}"
        if require_clone:
            msg = f"CLONE_FAILED: Yêu cầu bắt buộc clone (require_clone=True) nhưng các backend clone đều lỗi: {history}"
        raise VoiceBackendError(msg)
    return used, attempts



def render_srt_voice_track(srt_path, output_wav, cfg, video_duration=None, cache_dir=None, reference_audio=None, reference_text=None):
    import sys
    from wuby_studio.voice_pipeline import render
    return render(sys.modules[__name__],srt_path,output_wav,cfg,video_duration,cache_dir,reference_audio,reference_text)


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
