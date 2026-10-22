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

    fit_mode = config.get("fit_mode", "contain")
    blur_mode = config.get("blur_mode", "none")
    blur_subtitle = bool(config.get("blur_subtitle", False) or (blur_mode and blur_mode != "none"))
    blur_height_ratio = round(float(config.get("blur_height_pct", 22)) / 100.0, 3)
    blur_strength = int(config.get("blur_strength", 20))
    voice_id = config.get("voice_id", "original")
    voice_speed = float(config.get("voice_speed", 1.0))
    keep_original_audio = bool(config.get("keep_original_audio", True)) and before["has_audio"]
    bgm_style = config.get("bgm_style", "none")
    subtitle_style = config.get("subtitle_style", "none")
    banner_text = str(config.get("banner_text") or "").strip()
    marquee_text = str(config.get("marquee_text") or "").strip()
    text_position = config.get("text_position", "bottom")
    mirror_flip = bool(config.get("mirror_flip", False))
    color_grade = config.get("color_grade", "natural")

    cfg = {
        "output_width": config["width"],
        "output_height": config["height"],
        "fit_mode": fit_mode,
        "use_nvenc": False,
        "speed": 1,
        "keep_original_audio": keep_original_audio or before["has_audio"],
        "original_audio_volume": 1.0,
        "blur_subtitle": blur_subtitle,
        "blur_subtitle_height_ratio": blur_height_ratio,
        "blur_strength": blur_strength,
    }

    # Generate ASS subtitle file for Banner Hook & Running Text / Karaoke if configured
    has_text_overlay = bool(banner_text or marquee_text or (subtitle_style and subtitle_style != "none"))
    if has_text_overlay:
        ass_path = directory / "overlay.ass"
        w, h = config["width"], config["height"]
        dur = max(float(before.get("duration") or 5.0), 1.0)
        end_h = int(dur // 3600)
        end_m = int((dur % 3600) // 60)
        end_s = dur % 60
        end_ts = f"{end_h}:{end_m:02d}:{end_s:05.2f}"
        primary_col = "&H0000FFFF" if subtitle_style == "review_yellow_box" else ("&H00FFFF00" if subtitle_style == "neon_glow" else "&H00FFFFFF")
        back_col = "&H80000000" if subtitle_style == "review_yellow_box" else "&H64000000"
        border_style = 3 if subtitle_style == "review_yellow_box" else 1
        font_sz = max(int(w * 0.048), 22)
        banner_sz = max(int(w * 0.052), 24)
        ass_lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {w}",
            f"PlayResY: {h}",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,DejaVu Sans,{font_sz},{primary_col},&H000088EF,&H00000000,{back_col},-1,0,0,0,100,100,0,0,{border_style},2,1,2,24,24,{int(h*0.12)},1",
            f"Style: Banner,DejaVu Sans,{banner_sz},&H0000D7FF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,3,3,0,8,20,20,{int(h*0.06)},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        if banner_text:
            clean_banner = banner_text.replace("{", "").replace("}", "").replace("\n", " ")
            ass_lines.append(f"Dialogue: 1,0:00:00.00,{end_ts},Banner,,0,0,0,,{clean_banner}")
        if marquee_text:
            clean_marquee = marquee_text.replace("{", "").replace("}", "").replace("\n", " ")
            ass_lines.append(f"Dialogue: 0,0:00:00.00,{end_ts},Default,,0,0,0,,{clean_marquee}")
        ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
        cfg["burn_subtitles"] = True
        cfg["subtitle_path"] = str(ass_path)

    command = build_render_command(source, None, target, cfg)

    # Inject mirror_flip (hflip) and color_grade into -filter_complex if enabled
    extra_vfilters = []
    if mirror_flip:
        extra_vfilters.append("hflip")
    if color_grade == "cinematic_warm":
        extra_vfilters.append("eq=contrast=1.08:saturation=1.18:brightness=0.02")
    elif color_grade == "film_contrast":
        extra_vfilters.append("eq=contrast=1.22:saturation=0.92:gamma=0.95")
    elif color_grade == "vibrant_tiktok":
        extra_vfilters.append("eq=contrast=1.12:saturation=1.35:brightness=0.03")
    elif color_grade == "noir_bw":
        extra_vfilters.append("hue=s=0,eq=contrast=1.25")

    if extra_vfilters and "-filter_complex" in command:
        fc_idx = command.index("-filter_complex") + 1
        map_idx = command.index("-map") + 1
        cur_vlabel = command[map_idx]
        command[fc_idx] = command[fc_idx] + f";{cur_vlabel}{','.join(extra_vfilters)}[vfinal]"
        command[map_idx] = "[vfinal]"

    command[1] = "-n"
    command = command[:-1] + ["-threads", "2", "-filter_complex_threads", "1", str(target)]
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
    try:
        while process.poll() is None:
            if abort.is_set() or time.monotonic() - started > 300:
                raise DomainError("CANCEL_REQUIRES_RECONCILIATION")
            time.sleep(.1)
        if process.returncode and cfg.get("burn_subtitles"):
            # Fallback if ffmpeg lacks libass filter on minimal builds
            cfg.pop("burn_subtitles", None)
            cfg.pop("subtitle_path", None)
            if target.exists():
                target.unlink()
            command = build_render_command(source, None, target, cfg)
            command[1] = "-n"
            command = command[:-1] + ["-threads", "2", "-filter_complex_threads", "1", str(target)]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
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
    report_payload = {
        "schema_version": MODULE_VERSION,
        "source_sha256": checksum(source),
        "output_sha256": checksum(target),
        "preset_profile": config.get("preset_profile", "basic_render"),
        "render_config": config,
        "voice_config": {
            "voice_id": voice_id,
            "voice_speed": voice_speed,
            "keep_original_audio": keep_original_audio,
            "bgm_style": bgm_style,
        },
        "blur_config": {
            "blur_subtitle": blur_subtitle,
            "blur_mode": blur_mode if blur_subtitle else "none",
            "blur_height_pct": int(config.get("blur_height_pct", 22)),
            "blur_strength": blur_strength,
        },
        "text_overlay_config": {
            "subtitle_style": subtitle_style,
            "banner_text": banner_text,
            "marquee_text": marquee_text,
            "text_position": text_position,
        },
        "visual_effects": {
            "fit_mode": fit_mode,
            "mirror_flip": mirror_flip,
            "color_grade": color_grade,
        },
        "applied_profile": cfg,
        "media": after,
        "encoder": "libx264",
        "status": "needs_review",
        "tts_run": voice_id != "original",
        "ocr_run": blur_subtitle,
    }
    with report.open("x", encoding="utf-8") as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)
    return [(target, "video", "video/mp4"), (report, "report", "application/json")]
