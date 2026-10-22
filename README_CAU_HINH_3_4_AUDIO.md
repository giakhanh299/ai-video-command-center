# Cấu hình 3 và 4 - bản V5

## 3 - Wuby + AI giữ nền
Clone pipeline Wuby: preflight hình/scene/OCR/voice -> xóa chữ -> chèn chữ Việt. Khác Wuby gốc ở audio: AI tách dialogue, hard replace thoại gốc theo timestamp Whisper, giữ music/SFX/ambience và ghép TTS Việt. Không duck nền mạnh.

## 4 - Wuby + 5.1 Smart hard mute
Clone pipeline Wuby. Audio >= 6 kênh: ưu tiên bỏ center để lấy nền giàu chi tiết. Trong đúng cửa sổ thoại Whisper, dùng thêm lớp cleanup thứ hai để dập thoại còn rò ở L/R rồi ghép TTS. Nếu không có 5.1 thì fallback AI separation/center-cancel theo cấu hình.

## Giọng
Đo F0 từng câu nhưng khóa một voice cho cùng cụm người nói. Có octave correction để tránh một người bị đổi nam/nữ vì F0 bị bắt 2x hoặc 0.5x.

## Chữ
Wuby overlay đã giảm cỡ chữ còn 26-44 và tự co theo box.
