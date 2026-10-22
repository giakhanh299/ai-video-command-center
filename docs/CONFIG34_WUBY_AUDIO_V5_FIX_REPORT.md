# Config 3/4 Wuby + Audio Hard Replace V5

## Mục tiêu sửa
- Cấu hình 3/4 kế thừa pipeline hình ảnh/preflight/OCR của Wuby thay vì dùng movie pipeline rút gọn.
- Cấu hình 4 phải triệt thoại gốc thật sự, kể cả thoại rò từ center sang L/R của track 5.1.
- Không dùng sidechain ducking mạnh làm nhạc/SFX tụt-phồng theo từng câu.
- Giảm cỡ chữ Wuby overlay.
- Đo F0 theo từng câu nhưng khóa voice theo cụm người nói; có sửa lỗi octave 0.5x/2x.

## Cấu hình 3
Wuby visual/preflight -> Demucs/AI background -> hard replace cửa sổ thoại Whisper -> TTS Việt.
Không đưa original dialogue mix trở lại trong cửa sổ thoại.

## Cấu hình 4
Wuby visual/preflight -> probe 5.1/7.1 -> center-omit background -> lớp cleanup thứ hai chỉ trong cửa sổ Whisper -> TTS Việt.
Nếu Demucs model chưa có local thì lớp cleanup speech-window fallback center-cancel. Ngoài vùng thoại vẫn giữ nền surround giàu chi tiết.

## Audio mix
Bỏ compressor sidechain mạnh ở hard-replace path. Nền chạy ổn định; chỉ chuyển giữa rich background và speech-clean background bằng mask Whisper có attack/release mềm.

## Subtitle
Wuby overlay min/max font: 26/44 (trước 34/56), outline tối đa 4.

## Voice stability
Whisper vẫn chia theo câu. Mỗi câu vẫn đo F0, nhưng không tự chọn voice độc lập nữa. Các câu được gom theo acoustic voiceprint; một cluster người nói khóa một voice Việt. F0 0.5x/2x được octave-align trước khi chọn voice.

## Test
- Unit/regression liên quan: 36 passed.
- Synthetic 5.1: center voice 880 Hz bị rò ở L/R. Sau final hard-replace mix, biên độ 880 Hz trong speech window giảm từ ~274 (ngoài speech) xuống ~0.28, trong khi TTS 500 Hz vẫn ~842.
