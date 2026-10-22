#!/usr/bin/env python3
"""
test_voice_clone.py - Standalone test utility for voice cloning backends.

Runs zero-shot voice cloning directly without requiring video rendering:
- KhanhTTS / OmniVoice (Higgs acoustic tokens conditioning, Whisper ASR)
- VieNeu-TTS v3 Turbo (x-vector speaker embedding + MOSS acoustic codes)
- ZeroTTS (preset/fallback voice)

Supports --debug for rich technical telemetry.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import soundfile as sf

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def _resolve_ref_text(ref_text_arg: Optional[str]) -> Optional[str]:
    if not ref_text_arg:
        return None
    p = Path(ref_text_arg)
    if p.exists() and p.is_file():
        try:
            return p.read_text(encoding="utf-8-sig", errors="replace").strip()
        except Exception:
            return p.read_text(encoding="utf-8", errors="ignore").strip()
    return ref_text_arg.strip()


def run_khanhtts_clone(
    ref_audio: Optional[str],
    ref_text: Optional[str],
    text: str,
    output_path: Path,
    device: str = "cuda:0",
    debug: bool = False,
) -> Dict[str, Any]:
    import torch
    from omnivoice import OmniVoice

    model_id = "kjanh/KhanhTTS-OmniVoice"
    t_start_load = time.time()
    vram_before = torch.cuda.memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0

    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    # If ref_text is missing, OmniVoice needs load_asr=True for Whisper transcription
    need_asr = (ref_audio is not None and not ref_text)
    model = OmniVoice.from_pretrained(model_id, device_map=device, dtype=dtype, load_asr=need_asr)
    load_time = time.time() - t_start_load
    vram_after_load = torch.cuda.memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0

    emb_created = False
    emb_shape_str = "N/A"
    emb_norm_str = "N/A"
    actual_ref_text = ref_text

    t_infer_start = time.time()
    if ref_audio:
        # Precompute voice clone prompt
        prompt = model.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=ref_text,
            preprocess_prompt=True,
        )
        actual_ref_text = prompt.ref_text
        emb_created = True
        # Discrete acoustic tokens shape (num_codebooks, seq_len)
        emb_shape_str = str(tuple(prompt.ref_audio_tokens.shape))
        emb_norm_str = f"RMS={prompt.ref_rms:.4f}, Tokens={prompt.ref_audio_tokens.numel()}"

        results = model.generate(
            text=text.strip(),
            language="Vietnamese",
            voice_clone_prompt=prompt,
            num_step=16,
        )
    else:
        results = model.generate(
            text=text.strip(),
            language="Vietnamese",
            num_step=16,
        )

    infer_time = time.time() - t_infer_start
    audio = results[0] if isinstance(results, (list, tuple)) else results
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)

    sr = int(getattr(model, "sampling_rate", 24000))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio, sr, subtype="PCM_16")
    duration = float(len(audio) / sr)

    # Clean up model to avoid holding VRAM
    del model
    if torch.cuda.is_available():
        import gc
        gc.collect()
        torch.cuda.empty_cache()

    return {
        "backend": "khanhtts",
        "model_path": model_id,
        "device": device,
        "dtype": str(dtype),
        "clone_mode": "zero_shot_clone" if ref_audio else "auto_voice",
        "speaker_embedding_created": emb_created,
        "embedding_shape": emb_shape_str,
        "embedding_norm": emb_norm_str,
        "reference_text_used": actual_ref_text,
        "load_time_sec": load_time,
        "infer_time_sec": infer_time,
        "sample_rate": sr,
        "duration_sec": duration,
        "output_path": str(output_path),
        "clone_success": bool(ref_audio),
        "fallback_occurred": False,
    }


def run_vieneu_clone(
    ref_audio: Optional[str],
    ref_text: Optional[str],
    text: str,
    output_path: Path,
    device: str = "auto",
    debug: bool = False,
) -> Dict[str, Any]:
    from vieneu import Vieneu

    t_start_load = time.time()
    tts = Vieneu(mode="v3turbo", device=device)
    load_time = time.time() - t_start_load

    emb_created = False
    emb_shape_str = "N/A"
    emb_norm_str = "N/A"

    t_infer_start = time.time()
    if ref_audio:
        # Pre-resolve reference to inspect speaker_emb and ref_codes
        try:
            spk_emb, ref_codes = tts._resolve_ref(voice=None, ref_audio=ref_audio, denoise=True, use_ref_codes=True)
            emb_created = True
            emb_shape_str = f"spk_emb: {spk_emb.shape}, codes: {ref_codes.shape if ref_codes is not None else 'None'}"
            norm = float(np.linalg.norm(spk_emb))
            emb_norm_str = f"L2_norm={norm:.4f}"
        except Exception as e:
            if debug:
                print(f"[Debug] Warning inspecting ref: {e}")

        audio = tts.infer(text=text.strip(), ref_audio=str(ref_audio), denoise=True)
    else:
        audio = tts.infer(text=text.strip())

    infer_time = time.time() - t_infer_start
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    sr = int(getattr(tts, "sample_rate", 48000))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio, sr, subtype="PCM_16")
    duration = float(len(audio) / sr)

    del tts
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    return {
        "backend": "vieneu",
        "model_path": "pnnbao-ump/VieNeu-TTS-v3-Turbo",
        "device": device,
        "dtype": "auto",
        "clone_mode": "zero_shot_clone" if ref_audio else "preset_voice",
        "speaker_embedding_created": emb_created,
        "embedding_shape": emb_shape_str,
        "embedding_norm": emb_norm_str,
        "reference_text_used": ref_text or "N/A (Acoustic extraction direct from audio)",
        "load_time_sec": load_time,
        "infer_time_sec": infer_time,
        "sample_rate": sr,
        "duration_sec": duration,
        "output_path": str(output_path),
        "clone_success": bool(ref_audio),
        "fallback_occurred": False,
    }


def run_zerotts(
    text: str,
    output_path: Path,
    voice: str = "hamy",
    debug: bool = False,
) -> Dict[str, Any]:
    # Edge-TTS / ZeroTTS preset voice
    import asyncio
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError("edge_tts package required for preset voice fallback test.")

    t_infer_start = time.time()
    edge_voice = "vi-VN-HoaiMyNeural" if "hamy" in voice.lower() or "nu" in voice.lower() else "vi-VN-NamMinhNeural"

    async def _gen():
        communicate = edge_tts.Communicate(text, edge_voice)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await communicate.save(str(output_path))

    asyncio.run(_gen())
    infer_time = time.time() - t_infer_start

    info = sf.info(str(output_path))
    return {
        "backend": "zerotts",
        "model_path": f"edge_tts/{edge_voice}",
        "device": "cloud/api",
        "dtype": "audio/mp3->wav",
        "clone_mode": "preset_voice (NO_CLONE)",
        "speaker_embedding_created": False,
        "embedding_shape": "N/A",
        "embedding_norm": "N/A",
        "reference_text_used": "N/A",
        "load_time_sec": 0.0,
        "infer_time_sec": infer_time,
        "sample_rate": int(info.samplerate),
        "duration_sec": float(info.duration),
        "output_path": str(output_path),
        "clone_success": False,  # Strict: preset voice is NOT a clone
        "fallback_occurred": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Test voice cloning directly on Vietnamese text")
    parser.add_argument("--ref", type=str, default=None, help="Reference audio path (*.ref.wav, *.wav, *.mp3)")
    parser.add_argument("--ref-text", type=str, default=None, help="Reference transcript (file or string)")
    parser.add_argument("--text", type=str, default="Trời ơi, chuyện gì đang xảy ra vậy?", help="Target Vietnamese text")
    parser.add_argument("--backend", type=str, default="khanhtts", choices=["khanhtts", "khanh_omnivoice", "omnivoice", "vieneu", "zerotts"])
    parser.add_argument("--output", type=str, default=None, help="Output WAV path (default: tests/output_<backend>.wav)")
    parser.add_argument("--device", type=str, default="cuda:0", help="Inference device (e.g. cuda:0, cpu, auto)")
    parser.add_argument("--debug", action="store_true", help="Print detailed diagnostic telemetry")
    args = parser.parse_args()

    backend_normalized = "khanhtts" if args.backend in ("khanhtts", "khanh_omnivoice", "omnivoice") else args.backend
    default_out = Path("tests") / f"output_{backend_normalized}.wav"
    output_path = Path(args.output).resolve() if args.output else default_out.resolve()

    ref_audio_path = None
    ref_audio_info = None
    if args.ref:
        p = Path(args.ref).resolve()
        if not p.exists():
            print(f"[ERROR] Reference audio file not found: {p}")
            sys.exit(1)
        ref_audio_path = str(p)
        try:
            ref_audio_info = sf.info(ref_audio_path)
        except Exception:
            pass

    ref_text = _resolve_ref_text(args.ref_text)

    # Run inference
    try:
        if backend_normalized == "khanhtts":
            res = run_khanhtts_clone(ref_audio_path, ref_text, args.text, output_path, device=args.device, debug=args.debug)
        elif backend_normalized == "vieneu":
            res = run_vieneu_clone(ref_audio_path, ref_text, args.text, output_path, device=args.device, debug=args.debug)
        else:
            res = run_zerotts(args.text, output_path, debug=args.debug)
    except Exception as exc:
        print(f"\n[VOICE][{args.backend.upper()}]")
        print(f"STATUS: CLONE_FAILED")
        print(f"REASON: {type(exc).__name__}: {exc}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(2)

    # Standard Log output
    print("=" * 60)
    print(f"BACKEND:                  {res['backend']}")
    print(f"CLONE MODE:               {res['clone_mode']}")
    print(f"REFERENCE USED:           {ref_audio_path or 'NONE'}")
    print(f"REFERENCE TRANSCRIPT USED:{res['reference_text_used'] or 'NONE'}")
    print(f"TARGET LANGUAGE:          Vietnamese")
    print(f"OUTPUT:                   {res['output_path']}")
    print(f"DURATION:                 {res['duration_sec']:.2f} s")
    status_label = "CLONE_SUCCESS" if res["clone_success"] else ("FALLBACK_PRESET_VOICE" if res["fallback_occurred"] else "TTS_SUCCESS")
    print(f"STATUS:                   {status_label}")
    print("=" * 60)

    # Debug Log output
    if args.debug:
        print("\n--- DEBUG TELEMETRY ---")
        print(f"Reference WAV loaded:     {'YES' if ref_audio_path else 'NO'}")
        print(f"Reference text loaded:    {'YES' if ref_text else 'NO'}")
        if ref_audio_info:
            print(f"Reference duration:       {ref_audio_info.duration:.2f} s")
            print(f"Reference sample rate:    {ref_audio_info.samplerate} Hz")
        print(f"Backend selected:         {res['backend']}")
        print(f"Model path:               {res['model_path']}")
        print(f"Device:                   {res['device']}")
        print(f"dtype:                    {res['dtype']}")
        print(f"Speaker embedding created:{'YES' if res['speaker_embedding_created'] else 'NO'}")
        print(f"Embedding shape:          {res['embedding_shape']}")
        print(f"Embedding norm:           {res['embedding_norm']}")
        print(f"Target text:              {args.text}")
        print(f"Target language:          Vietnamese")
        print(f"Load time:                {res['load_time_sec']:.2f} s")
        print(f"Inference time:           {res['infer_time_sec']:.2f} s")
        print(f"Output sample rate:       {res['sample_rate']} Hz")
        print(f"Output duration:          {res['duration_sec']:.2f} s")
        print(f"Clone success:            {res['clone_success']}")
        print(f"Fallback occurred:        {res['fallback_occurred']}")
        print("-----------------------\n")


if __name__ == "__main__":
    main()
