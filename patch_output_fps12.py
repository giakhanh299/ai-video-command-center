from pathlib import Path

root = Path(r"D:/0.1_FACE_BOOK/Lay video tiktok")
vm = root / "backend" / "video_merger.py"
text = vm.read_text(encoding="utf-8", errors="ignore")
old = 'cmd += ["-c:v", encoder, *extra_args, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(tmp_out)]'
new = 'cmd += ["-c:v", encoder, *extra_args, "-r", "12", "-fps_mode", "cfr", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(tmp_out)]'
if new in text:
    print("ALREADY_OUTPUT_FPS12")
elif old in text:
    vm.write_text(text.replace(old, new), encoding="utf-8")
    print("PATCHED_OUTPUT_FPS12")
else:
    raise SystemExit("OUTPUT_CMD_PATTERN_NOT_FOUND")

wc = root / "backend" / "wuby_config.py"
if wc.exists():
    t = wc.read_text(encoding="utf-8", errors="ignore")
    t2 = t.replace('"sample_fps": 24.0', '"sample_fps": 12.0').replace('"sample_fps": 24', '"sample_fps": 12')
    if t2 != t:
        wc.write_text(t2, encoding="utf-8")
        print("PATCHED_OCR_SAMPLE_FPS12")
    else:
        print("OCR_SAMPLE_FPS_UNCHANGED")
