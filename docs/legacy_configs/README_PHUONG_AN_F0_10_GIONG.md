# Cấu hình 3 - Chọn 1/10 giọng Việt theo F0 + thay lời gốc khi TTS đọc

## Mục tiêu đã triển khai

Luồng mới KHÔNG clone giọng và KHÔNG nhận diện danh tính người nói.

1. Video gốc được đo cao độ cơ bản F0 trên các khoảng có lời thoại.
2. Lấy `median_f0_hz` để tránh bị một vài nốt/âm nhạc kéo sai kết quả.
3. So với bank tối đa 10 (hoặc nhiều hơn) giọng TTS Việt có sẵn.
4. Chọn giọng có khoảng cách cao độ gần nhất theo **cents** (so sánh theo thang log, hợp lý hơn trừ Hz trực tiếp).
5. Giọng đã chọn được giữ ổn định cho toàn video.
6. Track TTS Việt sau khi tạo được phân tích activity:
   - TTS đang đọc -> audio gốc được hạ ra, dùng **instrumental/nền đã tách + TTS Việt**.
   - TTS im -> trả lại **audio gốc đầy đủ**.
7. Chuyển trạng thái có attack/release để tránh tiếng gốc bật/tắt giật.

## File mới

- `backend/pitch_voice_selector.py`: đo F0 và chọn giọng gần nhất.
- `backend/audio_voice_switch.py`: tách nền, tạo mask activity từ track TTS và chuẩn bị chuyển audio.
- `workspace/calibrate_voice_bank.py`: tùy chọn, đo F0 từ 10 file mẫu giọng và in ra giá trị để điền vào JSON.
- `install_audio_tools.ps1`: cài Demucs và các thư viện âm thanh cần thiết.

## Bank 10 giọng mẫu

Trong `backend/channels_config.json` có 10 profile từ `pitch_v01` đến `pitch_v10` và mục:

```json
"pitch_match": {
  "enabled": true,
  "voice_bank": [
    {"profile": "pitch_v01", "reference_hz": 100},
    ...
    {"profile": "pitch_v10", "reference_hz": 260}
  ]
}
```

Các giá trị 100..260 Hz hiện là **bank mẫu để hệ thống chạy ngay**. Khi bạn có 10 giọng thật, hãy thay:

- `voice_profiles.pitch_vXX.voice`: ID/model giọng thực tế.
- `voice_profiles.pitch_vXX.pitch`: nếu engine hỗ trợ pitch.
- `pitch_match.voice_bank[].reference_hz`: F0 trung vị đã đo của từng giọng.

Nếu bạn đã biết sẵn 10 tần số, chỉ cần điền trực tiếp 10 `reference_hz`.

## Cách đo 10 giọng cho chuẩn

Nên cho cả 10 giọng đọc **cùng một đoạn tiếng Việt** dài khoảng 8-15 giây, xuất WAV. Tên file nên trùng profile:

```text
voice_samples/
  pitch_v01.wav
  pitch_v02.wav
  ...
  pitch_v10.wav
```

Sau đó chạy:

```powershell
python workspace/calibrate_voice_bank.py voice_samples
```

Script sẽ in F0 trung vị của từng file. Dùng các số đó thay cho `reference_hz` trong `channels_config.json`.

## Tách lời gốc / giữ nhạc nền

Cấu hình 3 bật:

```json
"dialogue_replace": {
  "enabled": true,
  "separator_model": "htdemucs",
  "instrumental_volume": 0.85,
  "tts_volume": 1.0,
  "attack_ms": 80,
  "release_ms": 220,
  "fill_gap_ms": 180
}
```

### Khuyến nghị: cài Demucs

Chạy PowerShell:

```powershell
.\install_audio_tools.ps1
```

Hoặc:

```powershell
python -m pip install -U demucs soundfile numpy scipy
```

Lần đầu Demucs có thể tải checkpoint model. Sau đó file nền đã tách được cache theo video/model, nên đổi font/logo hoặc render lại không cần tách lại video từ đầu.

Nếu Demucs không chạy, bản vá có fallback `center_cancel`. Fallback này chỉ là phương án cứu hộ: nó có thể làm ảnh hưởng nhạc/hiệu ứng nằm ở giữa stereo. Muốn chất lượng tốt nhất thì dùng model separator.

## Logic chuyển tiếng mới

Không dùng hàng trăm/hàng nghìn `between(t,...)` từ SRT nữa.

Track TTS được đo trực tiếp để tạo hai mask bù nhau:

```text
TTS activity mask        0 ---- 1 ===== 1 ---- 0
Original activity mask   1 ==== 0 ----- 0 ==== 1
```

FFmpeg trộn:

```text
original * original_mask
+ instrumental * tts_mask
+ Vietnamese TTS
```

Do đó:

```text
TTS im      -> audio gốc
TTS đang nói -> nền đã tách + giọng Việt
```

Điều này đúng với yêu cầu "giọng Việt đọc thì tắt lời gốc; giọng Việt nghỉ thì trả tiếng gốc" và không phụ thuộc việc subtitle còn đang hiện trên màn hình hay không.

## Các lỗi liên quan đã sửa trong gói này

- `#namreview` không còn bị khớp nhầm thêm `#nam`.
- Cache TTS không còn chỉ dựa vào số thứ tự câu; hash hiện gồm text/engine/voice/pitch/rate/speed.
- `force=True` thực sự bỏ cache cũ.
- Đường ducking legacy đọc đúng cả dict và `SubtitleSegment`.
- Cấu hình 3 bật `force_render` để không vô tình trả lại video cũ khi thay logic audio.
- Bỏ kiểu dựng biểu thức thời gian hàng chục nghìn ký tự trong chế độ `dialogue_replace`; chuyển sang audio mask.

## Kiểm thử đã chạy khi đóng gói

- Compile toàn bộ Python: đạt.
- Hashtag:
  - `#cauhinh3` -> chỉ `cauhinh3`.
  - `#namreview` -> chỉ `cauhinh3`.
  - `#reviewnam` -> chỉ `cauhinh3`.
  - `#nam` -> `kenh_nam`.
- Test F0 bằng video tổng hợp 130 Hz:
  - đo được ~131.15 Hz;
  - chọn đúng bank 130 Hz.
- Test render audio-switch bằng video + TTS tổng hợp: FFmpeg xuất video thành công.

## Lưu ý chất lượng

F0 chỉ giúp chọn giọng gần về độ trầm/bổng. Nó không đảm bảo giống chất giọng, độ khàn, độ dày hay cảm xúc. Đây là chủ ý của phương án này: **chọn giọng Việt có sẵn gần tông**, không clone.
