"""Audio Separator Runner using audio-separator[gpu]
Environment: D:\\0.1_FACE_BOOK\\Lay video tiktok\\MOI_TRUONG\\audio_sep_env\\Scripts\\python.exe
Default Model Directory: D:\\0.1_FACE_BOOK\\Lay video tiktok\\MODELS\\audio_separator
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Default paths
AUDIO_SEP_PYTHON = Path(r"D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Scripts\python.exe")
AUDIO_SEP_MODELS_DIR = Path(r"D:/0.1_FACE_BOOK/Lay video tiktok/MODELS/audio_separator")
TORCH_LIB_CUDA_DIR = Path(r"C:\Program Files\Python310\Lib\site-packages\torch\lib")
DEFAULT_MODEL = "UVR-MDX-NET-Inst_HQ_3.onnx"


def setup_cuda_env() -> None:
    """Add torch/lib with CUDA 12 and cuDNN 9 to DLL search path if on Windows."""
    if sys.platform == "win32" and TORCH_LIB_CUDA_DIR.exists():
        try:
            os.add_dll_directory(str(TORCH_LIB_CUDA_DIR))
        except Exception:
            pass
        current_path = os.environ.get("PATH", "")
        if str(TORCH_LIB_CUDA_DIR) not in current_path:
            os.environ["PATH"] = str(TORCH_LIB_CUDA_DIR) + os.pathsep + current_path


def is_audio_separator_available() -> bool:
    """Check if audio-separator can be imported in current env or via external env."""
    try:
        setup_cuda_env()
        import audio_separator  # noqa: F401
        return True
    except ImportError:
        return AUDIO_SEP_PYTHON.exists()


def run_separation_direct(
    audio_path: str | Path,
    output_dir: str | Path,
    model_name: str = DEFAULT_MODEL,
    model_file_dir: str | Path | None = None,
) -> dict[str, str]:
    """Run separation directly when audio_separator is importable in current python."""
    setup_cuda_env()
    from audio_separator.separator import Separator

    input_file = Path(audio_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    models_dir = Path(model_file_dir) if model_file_dir else AUDIO_SEP_MODELS_DIR
    if not models_dir.exists():
        models_dir.mkdir(parents=True, exist_ok=True)

    separator = Separator(
        model_file_dir=str(models_dir),
        output_dir=str(out_dir),
        output_format="WAV",
    )

    # Enable CUDA execution provider on ONNXRuntime if available
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            separator.onnx_execution_provider = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        elif "TensorrtExecutionProvider" in available:
            separator.onnx_execution_provider = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception:
        pass

    separator.load_model(model_filename=model_name)
    output_files = separator.separate(str(input_file))

    vocals_path = ""
    instrumental_path = ""
    other_stems: list[str] = []

    for fn in output_files:
        full_p = out_dir / fn
        if "(Vocals)" in fn or "vocals" in fn.lower():
            vocals_path = str(full_p)
        elif "(Instrumental)" in fn or "instrumental" in fn.lower():
            instrumental_path = str(full_p)
        else:
            other_stems.append(str(full_p))

    # Fallback assignment if naming patterns differ
    if not instrumental_path and len(output_files) == 2:
        for fn in output_files:
            if str(out_dir / fn) != vocals_path:
                instrumental_path = str(out_dir / fn)
                break

    return {
        "status": "success",
        "model": model_name,
        "vocals": vocals_path,
        "instrumental": instrumental_path,
        "output_files": [str(out_dir / fn) for fn in output_files],
    }


def separate_audio(
    audio_path: str | Path,
    output_dir: str | Path,
    model_name: str = DEFAULT_MODEL,
    model_file_dir: str | Path | None = None,
) -> dict[str, str]:
    """Separate audio into vocals and instrumental.
    
    If current Python environment does not have audio_separator, delegates
    to D:\\0.1_FACE_BOOK\\Lay video tiktok\\MOI_TRUONG\\audio_sep_env\\Scripts\\python.exe via subprocess.
    """
    input_file = Path(audio_path).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check if we can run directly in current process
    can_import_direct = False
    try:
        setup_cuda_env()
        import audio_separator  # noqa: F401
        can_import_direct = True
    except ImportError:
        can_import_direct = False

    if can_import_direct:
        return run_separation_direct(input_file, out_dir, model_name=model_name, model_file_dir=model_file_dir)

    # Run via D:/0.1_FACE_BOOK/Lay video tiktok/MOI_TRUONG/audio_sep_env\Scripts\python.exe
    if not AUDIO_SEP_PYTHON.exists():
        raise RuntimeError(
            f"audio-separator environment not found at: {AUDIO_SEP_PYTHON}. "
            "Please ensure D:\\0.1_FACE_BOOK\\Lay video tiktok\\MOI_TRUONG\\audio_sep_env is installed."
        )

    runner_script = Path(__file__).resolve()
    models_dir = str(model_file_dir or AUDIO_SEP_MODELS_DIR)

    cmd = [
        str(AUDIO_SEP_PYTHON),
        str(runner_script),
        "--input", str(input_file),
        "--output-dir", str(out_dir),
        "--model", model_name,
        "--model-dir", models_dir,
        "--direct-worker",
        "--json-output",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"audio-separator failed (code {proc.returncode}): {err}")

    # Parse JSON output from the last line
    result: dict[str, Any] = {}
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result = json.loads(line)
                break
            except Exception:
                continue

    if not result:
        raise RuntimeError(f"Failed to parse separator result from output:\n{proc.stdout}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Tach vocal va nhac nen voi audio-separator GPU")
    parser.add_argument("--input", "-i", required=True, help="Path toi file audio hoac video")
    parser.add_argument("--output-dir", "-o", default="./separated", help="Thu muc xuat ket qua")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ten model (default: {DEFAULT_MODEL})")
    parser.add_argument("--model-dir", default=str(AUDIO_SEP_MODELS_DIR), help="Thu muc chua weights model")
    parser.add_argument("--json-output", action="store_true", help="In ket qua duoi dang JSON")
    parser.add_argument("--direct-worker", action="store_true", help="Chay truc tiep khong delegate")

    args = parser.parse_args()

    try:
        if args.direct_worker:
            res = run_separation_direct(
                audio_path=args.input,
                output_dir=args.output_dir,
                model_name=args.model,
                model_file_dir=args.model_dir,
            )
        else:
            res = separate_audio(
                audio_path=args.input,
                output_dir=args.output_dir,
                model_name=args.model,
                model_file_dir=args.model_dir,
            )
        if args.json_output:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print("========================================")
            print("TACH AM THANH THANH CONG!")
            print(f"- Model:        {res.get('model')}")
            print(f"- Nhac nen:     {res.get('instrumental')}")
            print(f"- Vocal:        {res.get('vocals')}")
            print("========================================")
    except Exception as exc:
        if args.json_output:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Loi: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
