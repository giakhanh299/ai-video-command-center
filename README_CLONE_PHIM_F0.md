# Cấu hình 2 mới — Clone phim theo Whisper + F0 đa giọng

## Chỉ còn 2 lựa chọn chính trên bot

1. **Cấu hình 1 — Wuby**: giữ nguyên pipeline Wuby hiện tại.
2. **Cấu hình 2 — Clone phim**: thay hoàn toàn Cấu hình 2/3/4 cũ trong giao diện bot.

Cấu hình 2 mới chạy theo thứ tự:

```text
Nhận video
→ Whisper tách lời + timestamp
→ đọc lại SRT gốc
→ đo F0 từng đoạn thoại
→ so với voice bank thật trong voice_samples/
→ chọn voice gần nhất theo cents
→ dịch sang tiếng Việt
→ TTS từng câu bằng voice đã chọn
→ khớp duration/timeline
→ tách nền/lời gốc bằng Demucs nếu có
→ giữ nhạc/SFX + thay lời Việt
→ bắt vị trí subtitle theo logic Cấu hình 4 cũ
→ blur/che đúng vùng chữ gốc
→ burn subtitle Việt
→ render cuối
```

## Logic bắt vị trí subtitle được giữ từ Cấu hình 4

Pipeline mới tiếp tục dùng `backend/subtitle_regions.py::scan_fixed_blur_box()`:

- Lấy timestamp giữa của các câu subtitle dài nhất.
- Mở frame đúng timestamp.
- OCR tìm chữ Trung.
- Lấy union các bounding box để có một vùng che ổn định.
- Nếu không bắt được thì fallback sang `detect_subtitle_box_20_frames()`.

Mask dùng `blur_sub_black`, nên không còn dải đen full-width của cấu hình Review cũ.

## Voice bank đang dùng

Voice bank dùng các file thật có sẵn trong `voice_samples/`. F0 được đo lại runtime từ `ref_audio`, nên nếu thay file mẫu thì hệ thống tự dùng số đo mới.

| Profile | F0 đo được |
|---|---:|
| omni_dan_chuong_trinh_vip | 93.02 Hz |
| omni_laivansam | 119.40 Hz |
| omni_nam_review | 126.98 Hz |
| omni_tauthao | 128.00 Hz |
| omni_chautinhtri | 148.15 Hz |
| omni_nu_tram | 231.88 Hz |
| omni_nu_ngoc_trinh | 235.29 Hz |
| omni_nu_cute | 238.81 Hz |
| omni_nu_tre | 251.98 Hz |
| omni_betterversion | 258.06 Hz |

> Đây là matching theo pitch/F0, không phải nhận diện danh tính người nói.

## Tại sao phải chạy Whisper trước

Whisper cung cấp các khoảng `start/end` có lời thoại. F0 chỉ được đo trong các khoảng đó, giúp giảm ảnh hưởng của nhạc nền và SFX so với đo cả video.

Mỗi đoạn sinh report:

```json
{
  "start": 12.40,
  "end": 15.10,
  "source_f0": {"median_f0_hz": 128.4},
  "profile": "omni_tauthao",
  "top3": []
}
```

Một hysteresis nhỏ (`switch_margin_cents`) giúp tránh một nhân vật bị đổi giọng liên tục chỉ vì ngữ điệu lên/xuống. Scene cut sẽ reset độ bám này.

## Test riêng trước khi render

Có thể kiểm tra một video mà chưa dịch/TTS/render:

```bat
TEST_CLONE_PHIM_GIONG.bat "D:\video\phim.mp4"
```

Hoặc:

```powershell
python test_movie_clone_voice_match.py "D:\video\phim.mp4"
```

Kết quả ghi ra file:

```text
phim.movie_voice_test.json
```

Trong đó có từng câu Whisper, F0, top 3 voice và voice được chọn.

## Dependency

Project đã khai báo `faster-whisper` trong `requirements.txt`. Máy chạy thật cần cài dependency/model Whisper và model OmniVoice như project hiện tại.

Demucs là tùy chọn nhưng nên có để tách lời gốc sạch hơn:

```powershell
.\install_audio_tools.ps1
```

Nếu Demucs không có, project vẫn có fallback nhưng chất lượng giữ nhạc/SFX sẽ kém hơn.

## File mới/chỉnh chính

- `backend/movie_voice_matcher.py` — đo bank thật + F0 từng đoạn Whisper + xếp hạng voice.
- `backend/sub_processor.py` — thêm render TTS đa giọng theo từng segment.
- `backend/telegram_bot.py` — bot chỉ hiện Wuby + Clone phim và gọi pipeline mới.
- `backend/channels_config.json` — bỏ preset Cấu hình 3/4, thay Cấu hình 2 bằng workflow `movie_clone`.
- `test_movie_clone_voice_match.py` — test Whisper/F0/voice matching trước render.
- `docs/movie_voice_bank_calibration.json` — số đo voice bank hiện tại.
