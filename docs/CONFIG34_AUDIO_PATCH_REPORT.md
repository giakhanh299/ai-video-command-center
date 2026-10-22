# Patch report - Cấu hình 3 và 4 audio reconstruction

## Cấu hình 3
- Tên: AI giữ nền - tắt thoại gốc.
- Giữ nguyên Whisper/F0/voice-bank/subtitle pipeline của Clone phim.
- `dialogue_replace.strategy = ai_first`.
- `mask_source = whisper_segments` để khóa toàn bộ khoảng thoại gốc, tránh lọt tiếng khi TTS ngắn hơn.
- Ưu tiên Demucs htdemucs nếu môi trường đã có; fallback center-cancel.
- Ngoài vùng thoại: giữ audio gốc. Trong vùng thoại: background/instrumental + TTS Việt.

## Cấu hình 4
- Tên: 5.1 Smart - giữ nền/SFX.
- ffprobe audio trước khi xử lý.
- Nếu >=6 kênh: downmix FL/FR + surround + LFE, cố ý bỏ center channel FC.
- Nếu không đủ kênh hoặc xử lý surround thất bại: fallback Demucs, sau đó center-cancel.
- Dùng cùng Whisper segment mask như cấu hình 3.

## Kiểm thử
- Synthetic 5.1: nhận 6 channels, layout 5.1, separator `surround_center_omit:6ch:5.1`, output background stereo 2 channels.
- 67 tests liên quan + 5 subtests: PASS.
- Full-suite có một failure cũ ở `tests_v7/test_translation.py::test_api_failure_no_source_fallback`, không thuộc patch này.
