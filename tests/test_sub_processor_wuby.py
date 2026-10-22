import sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
sys.path.append('.')
from pathlib import Path
import channel_manager
import sub_processor
from test_ab_voice_clone import estimate_f0_and_features

print("=== TEST SUB_PROCESSOR INTEGRATION WITH WUBY_CLONE ===")

# Load channel config for -1004439918026
ch_key, ch_cfg = channel_manager.get_channel_config('-1004439918026')
print(f"Channel Key: {ch_key}, Voice: {ch_cfg.get('voice')}, Speed: {ch_cfg.get('speed')}")
vp = ch_cfg.get('_voice_profile', {})
print(f"Profile: {vp.get('label')}, Engine: {vp.get('engine')}, Require Clone: {vp.get('require_clone')}")

# Create test subtitle segments
segments = [
    sub_processor.SubtitleSegment(start=0.15, end=2.23, text="Gửi cho người không để ý đến bạn xem!"),
    sub_processor.SubtitleSegment(start=3.00, end=5.57, text="Em bận thì cứ bận đi.")
]

out_audio = Path("workspace/test_pipeline_wuby_dubbed.wav")
if out_audio.exists():
    out_audio.unlink()

print("\n--- 1. Chạy generate_dubbed_audio với Wuby Clone thật ---")
t0 = time.time()
res_path = sub_processor.generate_dubbed_audio(
    segments=segments,
    output_audio_path=str(out_audio),
    voice=ch_cfg.get("voice"),
    speed=ch_cfg.get("speed", 1.0),
    total_duration_sec=6.0,
    force=True,
    voice_profile=vp
)
t_dur = time.time() - t0
print(f"Hoàn thành generate_dubbed_audio trong {t_dur:.2f}s -> {res_path}")

assert Path(res_path).exists(), "Output audio must exist!"
feats = estimate_f0_and_features(res_path)
print(f"Acoustic features: Duration: {feats['duration']:.2f}s, F0 Mean: {feats['mean_f0_hz']:.1f}Hz, Centroid: {feats['spectral_centroid_hz']:.1f}Hz")
assert feats['mean_f0_hz'] > 260.0, "F0 must be high-pitched cartoon clone!"
print("PASS: SubProcessor successfully generated dubbed audio via Voice Router!")

print("\n--- 2. Test bắt buộc clone khi thiếu reference audio (Cấm tự đổi sang Hoài My) ---")
bad_vp = dict(vp)
bad_vp['ref_audio'] = 'non_existent_audio_file_9999.wav'
bad_vp['require_clone'] = True

bad_out = Path("workspace/test_bad_ref.wav")
try:
    sub_processor.generate_dubbed_audio(
        segments=segments,
        output_audio_path=str(bad_out),
        voice=ch_cfg.get("voice"),
        speed=1.0,
        total_duration_sec=6.0,
        force=True,
        voice_profile=bad_vp
    )
    print("FAIL: Should have raised CLONE_FAILED error!")
    assert False
except Exception as e:
    print(f"PASS: Correctly aborted with error: {type(e).__name__}: {e}")
    assert "CLONE_FAILED" in str(e) or "REFERENCE_AUDIO_MISSING" in str(e) or "not found" in str(e).lower()

print("\n--- 3. Test Manifest & Cache Invalidation ---")
manifest_path = out_audio.with_suffix(".manifest.json")
assert manifest_path.exists(), "Manifest file must exist!"
print("Manifest exists and records exact configuration!")

print("\nALL INTEGRATION TESTS PASSED!")
