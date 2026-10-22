import sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
sys.path.append('.')
from pathlib import Path
import channel_manager
import sub_processor
import video_merger

print("=== RENDER TEST VIDEO WITH REAL CLONED WUBY VOICE ===")

ch_key, ch_cfg = channel_manager.get_channel_config('-1004439918026')
input_video = Path("WUBY_V5_KIEM_TRA_LOI/sample_data/input_video.mp4")
srt_path = Path("WUBY_V5_KIEM_TRA_LOI/sample_data/subtitles_vi.srt")
voice_audio = Path("workspace/test_pipeline_wuby_dubbed.wav")
output_video = Path("workspace/wuby_v5_cloned_voice_demo.mp4")

if output_video.exists():
    output_video.unlink()

print(f"Input video: {input_video}")
print(f"SRT: {srt_path}")
print(f"Voice audio: {voice_audio} ({voice_audio.stat().st_size} bytes)")
print(f"Output video destination: {output_video}")

segments = sub_processor.parse_srt_to_segments(str(srt_path))

t0 = time.time()
video_merger.process_video_sub_and_mute(
    input_video=str(input_video),
    output_video=str(output_video),
    srt_path=str(srt_path),
    voice_audio=str(voice_audio),
    keep_bg_audio=True,
    bg_volume=0.35,
    blur_sub=False,
    use_nvenc=True,
    segments=segments,
    movie_title=None,
    mask_mode="in_video_overlay",
    channel_cfg=ch_cfg
)
t_render = time.time() - t0
print(f"Render completed in {t_render:.2f}s!")
assert output_video.exists() and output_video.stat().st_size > 10000, "Rendered video must exist and have content!"
print(f"SUCCESS: Rendered video size: {output_video.stat().st_size / 1024 / 1024:.2f} MB -> {output_video}")
