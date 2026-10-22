# Config 2 + Wuby Character ID V6 — change report

## Đã làm

- Thêm `backend/character_identity.py` làm tầng nhận diện nhân vật dùng chung.
- Config 2 (`movie_clone`) và Wuby (`wuby_preflight.voice_match`) bật Character ID mặc định.
- Primary: WeSpeaker model `chinese`, diarization toàn audio để tạo ID xuyên suốt video.
- Tie-break: Light-ASD chỉ nhận các cửa sổ thoại bị đánh dấu mơ hồ; không quét ASD toàn video.
- Character ID không dựa vào F0/pitch.
- Một Character ID khóa một Vietnamese voice profile trong video.
- Không pitch-shift output.
- Nếu model tùy chọn chưa cài, pipeline fail-soft sang timbre/spectral fallback thay vì dừng job.
- Telegram status/report hiển thị Character count, identity backend và số đoạn ASD verify.
- Thêm installer `install_character_identity.ps1`, doctor `tools/check_character_identity.py` và tài liệu `docs/CHARACTER_ID_CONFIG2_WUBY.md`.

## Regression fix nhỏ

`backend/wuby_roles.py` chỉ import OpenAI khi thực sự cần tự gọi API. Khi test truyền mock client, module không còn fail chỉ vì môi trường test chưa cài package `openai`. Logic runtime không đổi.

## Test

- Character ID focused tests: 8 passed.
- Backend + Wuby regression suite: 51 passed.
- Test cố tình cho cùng Character ID có F0 95 Hz và 285 Hz vẫn tạo đúng một character group.
- Test Light-ASD chunking xác nhận chỉ đoạn `ambiguous` được đưa đi ASD.

## Cài trên máy production

```powershell
.\install_character_identity.ps1
```

Sau đó:

```powershell
python tools\check_character_identity.py
```

WeSpeaker model có thể tải checkpoint lần đầu khi gọi `load_model('chinese')`. Light-ASD được installer clone vào `external/Light-ASD`; model weight upstream nằm trong repo theo cấu trúc hiện tại.
