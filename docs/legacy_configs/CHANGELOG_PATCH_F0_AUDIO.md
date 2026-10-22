# Patch F0 + Audio Dialogue Replacement

## Đã thêm
- Tự đo F0 giọng gốc và chọn preset TTS Việt gần nhất trong bank 10 giọng.
- So khoảng cách bằng cents để tránh sai lệch do thang Hz tuyến tính.
- Chuyển audio dựa trên activity của track TTS thực tế, không dựa riêng vào thời gian sub.
- Tách nền bằng Demucs khi có; fallback center-cancel khi separator chưa sẵn sàng.
- Cache nền theo video/model.
- Script hiệu chuẩn F0 cho 10 mẫu giọng.

## Đã sửa
- `#namreview` không còn khớp nhầm `#nam`.
- Cache TTS có hash text/engine/voice/pitch/rate/speed và `force=True` có tác dụng.
- Legacy ducking đọc đúng `SubtitleSegment`.
- Cấu hình 3 ép render lại để tránh trả nhầm file cũ khi logic audio thay đổi.
- Audio bitrate profile Cấu hình 3 nâng lên 160k.

## Test
- Python compile: PASS.
- JSON config parse: PASS.
- Hashtag routing: PASS.
- Synthetic 130 Hz source -> measured 131.15 Hz -> selected 130 Hz bank: PASS.
- Synthetic audio switch render with FFmpeg: PASS.
- Demucs full separation was not completed in this environment because the model checkpoint could not be downloaded (network unavailable); fallback path was exercised successfully.
