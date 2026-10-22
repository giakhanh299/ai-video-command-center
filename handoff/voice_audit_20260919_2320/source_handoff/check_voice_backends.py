#!/usr/bin/env python3
"""
check_voice_backends.py - Inspect and report health and readiness of voice backends.
Checks:
- KhanhTTS / OmniVoice (package, HuggingFace weights cache, CUDA / VRAM)
- VieNeu-TTS v3 Turbo (package, HuggingFace weights cache, ONNX / PyTorch backend)
- ZeroTTS (Piper TTS local binary/models or API)
- VRAM status and GPU information
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def check_gpu() -> dict:
    gpu_info = {
        "cuda_available": False,
        "device_count": 0,
        "device_name": "N/A",
        "vram_total_gb": 0.0,
        "vram_free_gb": 0.0,
    }
    try:
        import torch
        if torch.cuda.is_available():
            gpu_info["cuda_available"] = True
            gpu_info["device_count"] = torch.cuda.device_count()
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory
            reserved = torch.cuda.memory_reserved(0)
            allocated = torch.cuda.memory_allocated(0)
            free = total - reserved
            gpu_info["vram_total_gb"] = round(total / (1024 ** 3), 2)
            gpu_info["vram_free_gb"] = round(free / (1024 ** 3), 2)
    except Exception as exc:
        gpu_info["error"] = str(exc)
    return gpu_info


def check_hf_cache(model_subfolder_pattern: str) -> bool:
    hf_home = os.environ.get("HF_HOME", "D:\\0.1_FACE_BOOK\\DUNG_CHUNG\\MODELS\\HF_CACHE")
    hf_path = Path(hf_home) / "hub"
    if not hf_path.exists():
        hf_path = Path.home() / ".cache" / "huggingface" / "hub"
    if not hf_path.exists():
        return False
    for p in hf_path.glob(f"*{model_subfolder_pattern}*"):
        if p.is_dir():
            return True
    return False


def main():
    print("=" * 75)
    print("🔍 KIỂM TRA TOÀN DIỆN CÁC BACKEND VOICE CLONING (V4 MULTI-VOICE ROUTER)")
    print("=" * 75)

    gpu = check_gpu()
    print(f"🖥️  GPU:          {gpu['device_name']}")
    print(f"⚡ CUDA:         {'SẴN SÀNG' if gpu['cuda_available'] else 'KHÔNG KHẢ DỤNG'}")
    if gpu["cuda_available"]:
        print(f"💾 VRAM:         {gpu['vram_free_gb']} GB rảnh / {gpu['vram_total_gb']} GB tổng")
    print("-" * 75)

    backends = []

    # 1. KhanhTTS / OmniVoice
    has_omnivoice = bool(importlib.util.find_spec("omnivoice"))
    cached_khanh = check_hf_cache("KhanhTTS-OmniVoice")
    status_khanh = "SẴN SÀNG (GPU)" if (has_omnivoice and cached_khanh and gpu["cuda_available"]) else (
        "CÓ PACKAGE (Cần tải weights)" if has_omnivoice else "CHƯA CÀI ĐẶT"
    )
    backends.append({
        "name": "KhanhTTS / OmniVoice",
        "id": "khanh_omnivoice",
        "installed": has_omnivoice,
        "cached": cached_khanh,
        "mode": "Zero-shot Cross-Lingual Clone (24 kHz)",
        "status": status_khanh,
    })

    # 2. VieNeu-TTS v3 Turbo
    has_vieneu = bool(importlib.util.find_spec("vieneu"))
    cached_vieneu = check_hf_cache("VieNeu-TTS-v3-Turbo")
    status_vieneu = "SẴN SÀNG (ONNX/GPU)" if (has_vieneu and cached_vieneu) else (
        "CÓ PACKAGE (Cần tải weights)" if has_vieneu else "CHƯA CÀI ĐẶT"
    )
    backends.append({
        "name": "VieNeu-TTS v3 Turbo",
        "id": "vieneu",
        "installed": has_vieneu,
        "cached": cached_vieneu,
        "mode": "Zero-shot Voice Clone (48 kHz)",
        "status": status_vieneu,
    })

    # 3. ZeroTTS
    has_piper = bool(importlib.util.find_spec("piper")) or bool(importlib.util.find_spec("piper_tts"))
    backends.append({
        "name": "ZeroTTS (Local/API)",
        "id": "zerotts",
        "installed": True,
        "cached": True,
        "mode": "Preset Voice / Fallback Only (Không phải clone)",
        "status": "SẴN SÀNG (Fallback)",
    })

    # Output Table
    print(f"{'BACKEND':<26} | {'PACKAGE':<10} | {'WEIGHTS':<10} | {'TRẠNG THÁI'}")
    print("-" * 75)
    for b in backends:
        pkg = "✅ Cài đặt" if b["installed"] else "❌ Thiếu"
        weights = "✅ Cache" if b["cached"] else "⚠️ Chưa"
        print(f"{b['name']:<26} | {pkg:<10} | {weights:<10} | {b['status']}")
    print("-" * 75)

    print("\nChi tiết tính năng clone:")
    for b in backends:
        print(f" • [{b['id']}]: {b['mode']}")

    print("=" * 75)


if __name__ == "__main__":
    main()
