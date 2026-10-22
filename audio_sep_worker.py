# audio_sep_worker.py
import argparse
import json
import os
import sys
from pathlib import Path


def add_cuda_dll_dirs():
    candidates = [
        r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Lib\site-packages\torch\lib",
        r"C:\Program Files\Python310\Lib\site-packages\torch\lib",
        r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Lib\site-packages\nvidia\cublas\bin",
        r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Lib\site-packages\nvidia\cudnn\bin",
        r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Lib\site-packages\nvidia\cuda_runtime\bin",
    ]

    for p in candidates:
        if os.path.isdir(p):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass

            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument(
        "--model",
        default="UVR-MDX-NET-Inst_HQ_3.onnx",
    )
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()

    add_cuda_dll_dirs()

    import torch
    import onnxruntime as ort

    providers = ort.get_available_providers()

    has_cuda = (
        torch.cuda.is_available()
        or "CUDAExecutionProvider" in providers
        or "TensorrtExecutionProvider" in providers
    )

    status = {
        "torch_cuda": bool(torch.cuda.is_available()),
        "onnx_providers": providers,
        "cuda_ready": has_cuda,
    }

    if args.require_cuda:
        if not has_cuda:
            raise RuntimeError(
                f"audio-separator: CUDA acceleration unavailable. Providers={providers}, Torch CUDA={torch.cuda.is_available()}"
            )

    from audio_separator.separator import Separator

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    separator = Separator(
        model_file_dir=args.model_dir,
        output_dir=str(out_dir),
        output_format="WAV",
    )

    # Đảm bảo ONNXRuntime dùng GPU nếu CUDAExecutionProvider sẵn sàng
    if "CUDAExecutionProvider" in providers:
        separator.onnx_execution_provider = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    elif "TensorrtExecutionProvider" in providers:
        separator.onnx_execution_provider = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]

    separator.load_model(
        model_filename=args.model
    )

    outputs = separator.separate(args.input)

    resolved = []

    for item in outputs:
        p = Path(item)

        if not p.is_absolute():
            candidate = out_dir / p
            if candidate.exists():
                p = candidate

        resolved.append(str(p.resolve()))

    instrumental = None
    vocals = None

    for p in resolved:
        name = Path(p).name.lower()

        if "instrumental" in name or "no_vocals" in name:
            instrumental = p

        if "vocals" in name and "no_vocals" not in name:
            vocals = p

    # Fallback tìm trực tiếp trong output directory
    if not instrumental:
        for p in out_dir.glob("*"):
            n = p.name.lower()

            if p.is_file() and (
                "instrumental" in n
                or "no_vocals" in n
            ):
                instrumental = str(p.resolve())
                break

    if not vocals:
        for p in out_dir.glob("*"):
            n = p.name.lower()

            if p.is_file() and "vocals" in n and "no_vocals" not in n:
                vocals = str(p.resolve())
                break

    if not instrumental or not Path(instrumental).exists():
        raise RuntimeError(
            f"Không tìm thấy Instrumental. outputs={resolved}"
        )

    result = {
        "ok": True,
        "instrumental": instrumental,
        "vocals": vocals,
        "cuda": status,
        "model": args.model,
    }

    # Dòng cuối stdout phải là JSON
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
