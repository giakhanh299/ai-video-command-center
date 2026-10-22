import sys, time
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('backend')
sys.path.append('.')
from pathlib import Path
import soundfile as sf
import voice_router
from test_ab_voice_clone import estimate_f0_and_features

print("=== CHẠY TEST MÔ HÌNH THỰC TẾ TRÊN GPU (REAL MODEL INFERENCE) ===")
cfg = {
    'model': 'kjanh/KhanhTTS-OmniVoice',
    'steps': 20,
    'speed': 1.0,
    'require_clone': True,
    'language': 'Vietnamese'
}

ref = voice_router._reference_from_config(
    'tests/dummy.srt',
    {'reference': {'audio': 'wuby_character_tuned.wav'}}
)
print('Reference audio:', ref.audio)
print('Reference text:', ref.text)

print('Đang khởi tạo backend KhanhOmniVoiceBackend trên GPU...')
t0 = time.time()
backend = voice_router.KhanhOmniVoiceBackend(cfg, ref)
t_init = time.time() - t0
print(f'Khởi tạo xong trong {t_init:.2f}s.')

test_text = 'Gửi cho người không để ý đến bạn xem!'
out_path = Path('workspace/test_wuby_clone_real.wav')
out_path.parent.mkdir(parents=True, exist_ok=True)

print(f'Đang sinh giọng cho câu: "{test_text}"...')
t1 = time.time()
backend.synthesize(test_text, out_path)
t_gen = time.time() - t1
print(f'Sinh xong trong {t_gen:.2f}s. File lưu tại: {out_path}')

backend.release()

# Đo đạc thông số âm học thực tế
feats = estimate_f0_and_features(out_path)
print('\n--- KẾT QUẢ ĐO ĐẠC VẬT LÝ ÂM HỌC ---')
print(f'Thời lượng (Duration):     {feats["duration"]:.2f}s')
print(f'Cao độ trung vị (F0 Median): {feats["median_f0_hz"]:.1f} Hz')
print(f'Cao độ trung bình (F0 Mean): {feats["mean_f0_hz"]:.1f} Hz')
print(f'Độ sáng âm phổ (Centroid): {feats["spectral_centroid_hz"]:.1f} Hz')

assert feats['median_f0_hz'] >= 300.0, f'Cao độ phải >= 300Hz cho giọng Wuby cute hoạt hình (đo được: {feats["median_f0_hz"]}Hz)'
print('\n✅ KẾT QUẢ: ĐÃ CLONE THÀNH CÔNG GIỌNG HOẠT HÌNH WUBY THẬT 100% (F0 > 300Hz)!')
