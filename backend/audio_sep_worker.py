# backend/audio_sep_worker.py
import sys
from pathlib import Path

# Forward to root audio_sep_worker.py
ROOT_WORKER = Path(__file__).resolve().parent.parent / "audio_sep_worker.py"
if ROOT_WORKER.exists():
    with open(ROOT_WORKER, "r", encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    raise FileNotFoundError(f"Root audio_sep_worker.py not found: {ROOT_WORKER}")
