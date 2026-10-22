from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    result = {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "wespeaker_installed": importlib.util.find_spec("wespeaker") is not None,
        "torch_installed": importlib.util.find_spec("torch") is not None,
        "cuda_available": False,
        "light_asd_repo": (ROOT / "external" / "Light-ASD" / "Columbia_test.py").is_file(),
        "light_asd_talkset_weight": (
            ROOT / "external" / "Light-ASD" / "weight" / "finetuning_TalkSet.model"
        ).is_file(),
        "light_asd_ava_weight": (
            ROOT / "external" / "Light-ASD" / "weight" / "pretrain_AVA_CVPR.model"
        ).is_file(),
    }
    if result["torch_installed"]:
        try:
            import torch

            result["cuda_available"] = bool(torch.cuda.is_available())
            result["cuda_device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
            result["torch_version"] = str(torch.__version__)
        except Exception as exc:
            result["torch_error"] = f"{type(exc).__name__}: {exc}"

    result["wespeaker_importable"] = False
    if result["wespeaker_installed"]:
        try:
            from backend.character_identity import _prepare_torchaudio_compat
            _prepare_torchaudio_compat()
            import wespeaker  # noqa: F401
            result["wespeaker_importable"] = True
        except Exception as exc:
            result["wespeaker_error"] = f"{type(exc).__name__}: {exc}"

    result["character_id_ready"] = bool(
        result["ffmpeg"] and result["wespeaker_importable"]
    )
    result["light_asd_ready"] = bool(
        result["light_asd_repo"]
        and (result["light_asd_talkset_weight"] or result["light_asd_ava_weight"])
        and result["cuda_available"]
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["character_id_ready"]:
        print("\n[WARN] WeSpeaker/ffmpeg is not ready. The app will use the lightweight timbre fallback.")
    if not result["light_asd_ready"]:
        print("[WARN] Light-ASD is not fully ready. Jobs still run; ambiguous dialogue stays on audio identity fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
