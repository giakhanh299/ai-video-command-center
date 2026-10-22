import sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
sys.path.append('.')
from pathlib import Path
import channel_manager
import sub_processor

print("=== TEST PRESET CHANNEL (REVIEW FILM BLACK / NAM MINH) ===")

# Load channel config for -5579042871 (Kênh Review Nam)
ch_key, ch_cfg = channel_manager.get_channel_config('-5579042871')
print(f"Channel Key: {ch_key}, Voice: {ch_cfg.get('voice')}, Speed: {ch_cfg.get('speed')}")
vp = ch_cfg.get('_voice_profile', {})
print(f"Profile: {vp.get('label')}, Engine: {vp.get('engine')}, Voice: {vp.get('voice')}")

# Test segments
segments = [
    sub_processor.SubtitleSegment(start=0.5, end=2.5, text="Bộ phim này kể về một câu chuyện vô cùng kịch tính."),
    sub_processor.SubtitleSegment(start=3.0, end=5.0, text="Nhân vật chính quyết định quay trở lại để đối đầu kẻ thù.")
]

out_audio = Path("workspace/test_preset_channel.wav")
if out_audio.exists():
    out_audio.unlink()

res_path = sub_processor.generate_dubbed_audio(
    segments=segments,
    output_audio_path=str(out_audio),
    voice=ch_cfg.get("voice"),
    speed=ch_cfg.get("speed", 1.4),
    total_duration_sec=5.5,
    force=True,
    voice_profile=vp
)

assert Path(res_path).exists() and Path(res_path).stat().st_size > 1000, "Preset audio must exist!"
print(f"PASS: Preset channel successfully generated audio -> {res_path} ({Path(res_path).stat().st_size} bytes)")
