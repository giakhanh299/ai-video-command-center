# Character ID for Config 2 + Wuby

## Mục tiêu

Một nhân vật phải giữ **một Character ID và một giọng Việt đã khóa** xuyên suốt video, kể cả khi nhân vật hét, thì thầm, khóc hoặc thay đổi cao độ.

## Luồng mới

```text
Whisper / đoạn thoại gốc
        ↓
WeSpeaker Chinese diarization + speaker identity
        ↓
Character ID toàn video: CHAR_01, CHAR_02, ...
        ↓
đo độ chắc chắn theo từng câu
        ├─ chắc chắn → dùng luôn
        └─ mơ hồ → Light-ASD chạy đúng clip ngắn đó
                     ↓
                face đang nói → tie-break
        ↓
Character ID khóa
        ↓
1 Character ID = 1 Vietnamese voice profile trong video
        ↓
TTS/render như workflow hiện tại
```

## Luật quan trọng

- **F0/pitch không được tạo hoặc đổi Character ID.**
- Không pitch-shift giọng đầu ra.
- F0 cũ chỉ còn là gợi ý một lần để chọn màu giọng Việt gần với nhân vật khi cần dùng bank giọng có sẵn.
- Sau khi đã chọn profile cho `CHAR_XX`, mọi câu của nhân vật đó phải dùng cùng profile.
- Light-ASD không chạy full 30 phút; chỉ chạy các cửa sổ quanh câu bị đánh dấu `ambiguous`.
- Nếu WeSpeaker hoặc Light-ASD chưa cài, pipeline không chết: hệ thống rơi về spectral/timbre fallback cục bộ và ghi rõ backend trong report.

## Cấu hình đã bật

Áp dụng cho:

- `presets.cauhinh2.movie_voice_match.character_identity`
- `presets.wuby.wuby_preflight.voice_match.character_identity`
- workflow `movie_clone`
- workflow `wuby`

Do Cấu hình 3/4 hiện dùng chung workflow Wuby trong bản V5, chúng cũng nhận được tầng Character ID dùng chung; thay đổi này không làm đổi renderer/audio mode riêng của từng cấu hình.

## Cài một lần trên Windows

Chạy PowerShell ở thư mục dự án:

```powershell
.\install_character_identity.ps1
```

Script sẽ:

1. cài WeSpeaker;
2. clone Light-ASD vào `external/Light-ASD` nếu chưa có;
3. giữ nguyên PyTorch/CUDA đang dùng thay vì ép cài lại torch;
4. chạy `tools/check_character_identity.py`.

Có thể kiểm tra lại bất kỳ lúc nào:

```powershell
python tools\check_character_identity.py
```

## Report để debug

`*_movie_voice_match.json` và `*_wuby_preflight.json` có thêm:

- `identity_backend`
- `character_count`
- `identity_ambiguous_count`
- `identity_method` từng câu
- `active_track_id` / `active_track_score` khi Light-ASD được dùng
- `light_asd.status/chunks/verified/overrides`
- `identity_uses_f0: false`

Nếu một nhân vật bị tách sai, xem `speaker_id`, `identity_method`, `speaker_confidence` trước; không chỉnh ngưỡng F0 để sửa Character ID.
