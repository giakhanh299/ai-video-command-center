from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

import asset_manager

OMNIVOICE_DIR = Path(__file__).resolve().parent.parent / "OmniVoice"
if OMNIVOICE_DIR.exists() and str(OMNIVOICE_DIR) not in sys.path:
    sys.path.insert(0, str(OMNIVOICE_DIR))


class OmniVoiceServiceError(RuntimeError):
    pass


def _to_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


class OmniVoiceService:
    """
    Lazy adapter for the OmniVoice source bundled with this project.

    Important: the bundled API uses model.generate(text=..., ref_audio=..., ref_text=...)
    and returns numpy audio arrays. This adapter persists those arrays to WAV and caches
    the expensive voice-clone prompt per reference voice.
    """

    def __init__(
        self,
        model_name: str = "k2-fsa/OmniVoice",
        device: str = "auto",
        dtype: str = "float16",
        local_files_only: bool = False,
        model_loader: Callable[[str], Any] | None = None,
        verbose: bool = False,
    ):
        self.model_name = model_name or "k2-fsa/OmniVoice"
        self.device = device or "auto"
        self.dtype = dtype or "float16"
        self.local_files_only = bool(local_files_only)
        self.model_loader = model_loader
        self.verbose = verbose
        self._model: Any = None
        self._prompt_cache: dict[tuple[str, str], Any] = {}
        # One GPU model should not generate multiple chunks concurrently on a 16GB card.
        self._generation_lock = threading.Lock()

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[OmniVoice] {message}", flush=True)

    def _resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _resolve_dtype(self):
        try:
            import torch
            key = str(self.dtype).strip().lower()
            if key in {"float32", "fp32"}:
                return torch.float32
            if key in {"bfloat16", "bf16"}:
                return torch.bfloat16
            return torch.float16
        except Exception:
            return None

    def diagnostics(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "model_name": self.model_name,
            "requested_device": self.device,
            "resolved_device": self._resolve_device(),
            "dtype": self.dtype,
            "local_files_only": self.local_files_only,
            "prompt_cache_size": len(self._prompt_cache),
        }
        try:
            import torch
            info["torch_version"] = getattr(torch, "__version__", "")
            info["cuda_available"] = bool(torch.cuda.is_available())
            if torch.cuda.is_available():
                info["cuda_device_name"] = torch.cuda.get_device_name(0)
        except Exception as exc:
            info["torch_error"] = f"{type(exc).__name__}: {exc}"
        return info

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            if self.model_loader:
                model = self.model_loader(self.model_name)
            else:
                from omnivoice import OmniVoice

                kwargs: dict[str, Any] = {
                    "device_map": self._resolve_device(),
                }
                dtype = self._resolve_dtype()
                if dtype is not None:
                    kwargs["dtype"] = dtype
                if self.local_files_only:
                    kwargs["local_files_only"] = True

                self._log(f"Loading {self.model_name} on {kwargs.get('device_map')} ({self.dtype})")
                model = OmniVoice.from_pretrained(self.model_name, **kwargs)
        except Exception as exc:
            raise OmniVoiceServiceError(
                "Không thể nạp OmniVoice. Kiểm tra model cache/dependencies/CUDA. "
                f"Chi tiết: {type(exc).__name__}: {exc}"
            ) from exc

        if not callable(getattr(model, "generate", None)):
            raise OmniVoiceServiceError("OmniVoice model không có method generate().")
        self._model = model
        return model

    def _resolve_ref_audio(self, voice_cfg: dict[str, Any]) -> Path | None:
        raw = (
            voice_cfg.get("ref_audio")
            or voice_cfg.get("ref_audio_path")
            or voice_cfg.get("reference_audio")
            or voice_cfg.get("voice_path")
        )
        return asset_manager.resolve_voice_sample(raw)

    def _get_clone_prompt(self, model: Any, ref_audio: Path, ref_text: str | None) -> Any:
        key = (str(ref_audio.resolve()).lower(), ref_text or "")
        if key in self._prompt_cache:
            return self._prompt_cache[key]

        create_prompt = getattr(model, "create_voice_clone_prompt", None)
        if not callable(create_prompt):
            return None

        self._log(f"Creating reusable clone prompt from {ref_audio.name}")
        prompt = create_prompt(ref_audio=str(ref_audio), ref_text=ref_text or None)
        self._prompt_cache[key] = prompt
        return prompt

    def synthesize(
        self,
        text: str,
        output_file: Path,
        voice_cfg: dict[str, Any],
        speed_override: float | None = None,
    ) -> Path:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        clean_text = str(text or "").strip()
        if not clean_text:
            raise ValueError("OmniVoice text is empty")

        model = self._load_model()
        mode = str(voice_cfg.get("mode") or "clone").strip().lower()
        language = voice_cfg.get("language") or voice_cfg.get("language_code") or "vi"
        speed = speed_override if speed_override is not None else _to_float(voice_cfg.get("speed"), 1.0)

        generation_kwargs: dict[str, Any] = {
            "text": clean_text,
            "language": language,
            "speed": max(0.5, min(float(speed), 2.5)),
            "num_step": _to_int(voice_cfg.get("num_step"), 32),
            "guidance_scale": _to_float(voice_cfg.get("guidance_scale"), 2.0),
            "t_shift": _to_float(voice_cfg.get("t_shift"), 0.1),
            "denoise": _to_bool(voice_cfg.get("denoise"), True),
            "postprocess_output": _to_bool(voice_cfg.get("postprocess_output"), True),
        }

        if mode == "design":
            generation_kwargs["instruct"] = str(voice_cfg.get("instruct") or "female, low pitch").strip()
        elif mode == "auto":
            pass
        else:
            ref_audio = self._resolve_ref_audio(voice_cfg)
            if not ref_audio or not ref_audio.is_file():
                raise FileNotFoundError(
                    "Không tìm thấy file giọng mẫu OmniVoice. "
                    f"Cấu hình ref_audio={voice_cfg.get('ref_audio')!r}; thư mục mặc định={asset_manager.VOICE_SAMPLES_DIR}"
                )
            ref_text_raw = str(voice_cfg.get("ref_text") or "").strip()
            ref_text = ref_text_raw or None

            # Build and cache prompt once; if the model cannot expose this API, fall back
            # to the standard ref_audio/ref_text arguments.
            prompt = self._get_clone_prompt(model, ref_audio, ref_text)
            if prompt is not None:
                generation_kwargs["voice_clone_prompt"] = prompt
            else:
                generation_kwargs["ref_audio"] = str(ref_audio)
                generation_kwargs["ref_text"] = ref_text

        with self._generation_lock:
            try:
                audios = model.generate(**generation_kwargs)
            except Exception as exc:
                raise OmniVoiceServiceError(
                    f"OmniVoice generate() thất bại: {type(exc).__name__}: {exc}"
                ) from exc

        if not audios:
            raise OmniVoiceServiceError("OmniVoice không trả về audio.")

        try:
            import soundfile as sf
            sample_rate = int(getattr(model, "sampling_rate", None) or 24000)
            sf.write(str(output_file), audios[0], sample_rate)
        except Exception as exc:
            raise OmniVoiceServiceError(
                f"Không thể ghi WAV OmniVoice: {type(exc).__name__}: {exc}"
            ) from exc

        if not output_file.exists() or output_file.stat().st_size <= 100:
            raise OmniVoiceServiceError(f"OmniVoice output không hợp lệ: {output_file}")
        return output_file


_service_singleton: OmniVoiceService | None = None


def get_omnivoice_service() -> OmniVoiceService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = OmniVoiceService(
            model_name=os.getenv("OMNIVOICE_MODEL", "kjanh/KhanhTTS-OmniVoice").strip() or "kjanh/KhanhTTS-OmniVoice",
            device=os.getenv("OMNIVOICE_DEVICE", "auto").strip() or "auto",
            dtype=os.getenv("OMNIVOICE_DTYPE", "float16").strip() or "float16",
            local_files_only=_to_bool(os.getenv("OMNIVOICE_LOCAL_FILES_ONLY", "false"), False),
            verbose=_to_bool(os.getenv("OMNIVOICE_VERBOSE", "true"), True),
        )
    return _service_singleton
