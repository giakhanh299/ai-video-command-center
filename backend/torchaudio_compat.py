from __future__ import annotations

import sys
import types
from pathlib import Path


def apply_torchaudio_compat() -> None:
    """Fixes Windows compatibility issues with torchaudio 2.10.

    1. Provides dummy set_audio_backend / get_audio_backend (removed in 2.10).
    2. Provides sox_effects stub for s3prl / wespeaker imports.
    3. Replaces torchaudio.load with SoundFile to prevent the 0xc0000139 TorchCodec crash on Windows.
    """
    try:
        import torchaudio
    except ImportError:
        return

    if not hasattr(torchaudio, "set_audio_backend"):
        torchaudio.set_audio_backend = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
    if not hasattr(torchaudio, "get_audio_backend"):
        torchaudio.get_audio_backend = lambda: None  # type: ignore[attr-defined]

    if "torchaudio.sox_effects" not in sys.modules:
        sox = types.ModuleType("torchaudio.sox_effects")

        def unavailable(*_args, **_kwargs):
            raise RuntimeError("TORCHAUDIO_SOX_EFFECTS_UNAVAILABLE")

        sox.apply_effects_tensor = unavailable  # type: ignore[attr-defined]
        sox.apply_effects_file = unavailable  # type: ignore[attr-defined]
        sys.modules["torchaudio.sox_effects"] = sox

    # Torchaudio 2.10 delegates load() to TorchCodec. The installed TorchCodec
    # binary fails on Windows (0xc0000139). SoundFile handles WAV, MP3, FLAC, OGG safely.
    if not getattr(torchaudio.load, "_wuby_soundfile_compat", False):
        def soundfile_load(
            uri, frame_offset=0, num_frames=-1, normalize=True,
            channels_first=True, format=None, buffer_size=4096, backend=None,
        ):
            del normalize, format, buffer_size, backend
            import soundfile as sf
            import torch

            start = max(0, int(frame_offset or 0))
            frames = int(num_frames) if int(num_frames) >= 0 else -1
            data, sample_rate = sf.read(
                str(uri), start=start, frames=frames, dtype="float32", always_2d=True,
            )
            tensor = torch.from_numpy(data.copy())
            if channels_first:
                tensor = tensor.transpose(0, 1).contiguous()
            return tensor, int(sample_rate)

        soundfile_load._wuby_soundfile_compat = True  # type: ignore[attr-defined]
        torchaudio.load = soundfile_load  # type: ignore[assignment]


# Automatically apply on import
apply_torchaudio_compat()
