"""CPU compose adapter around the established FFmpeg command builder."""
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

from ..errors import DomainError
from ..registry import MODULE_VERSION
from ..storage import checksum, inspect_video


def run(config, source, directory, abort):
    before = inspect_video(source)
    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from backend.video_merger import build_render_command
    target = directory / "render.mp4"
    if target.exists() or abort.is_set():
        raise DomainError("OUTPUT_ALREADY_EXISTS")
    cfg = {"output_width": config["width"], "output_height": config["height"], "fit_mode": "contain",
           "use_nvenc": False, "speed": 1, "keep_original_audio": before["has_audio"],
           "original_audio_volume": 1.0, "blur_subtitle": False}
    command = build_render_command(source, None, target, cfg)
    command[1] = "-n"
    command = command[:-1] + ["-threads", "2", "-filter_complex_threads", "1", str(target)]
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
    try:
        while process.poll() is None:
            if abort.is_set() or time.monotonic() - started > 300:
                raise DomainError("CANCEL_REQUIRES_RECONCILIATION")
            time.sleep(.1)
        if process.returncode:
            raise DomainError("EXECUTION_FAILED")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    after = inspect_video(target)
    tolerance = 1 / float(Fraction(before["fps"])) + .05
    if (after["width"], after["height"]) != (config["width"], config["height"]) or after["fps"] != before["fps"] or abs(after["duration"] - before["duration"]) > tolerance or after["has_audio"] != before["has_audio"]:
        raise DomainError("EXECUTION_FAILED")
    if before["frames"] is not None and after["frames"] != before["frames"]:
        raise DomainError("EXECUTION_FAILED")
    report = directory / "render-report.json"
    with report.open("x", encoding="utf-8") as f:
        json.dump({"schema_version": MODULE_VERSION, "source_sha256": checksum(source), "output_sha256": checksum(target),
                   "media": after, "encoder": "libx264", "status": "needs_review", "tts_run": False, "ocr_run": False}, f)
    return [(target, "video", "video/mp4"), (report, "report", "application/json")]
