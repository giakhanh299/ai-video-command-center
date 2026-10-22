# Tách helper render — đợt 1

Ngày 2026-10-22. Đây là code refactor cục bộ, không là hoàn thành backend/Agent/pipeline.

## Thay đổi

- backend/render_modules/config_values.py: _to_bool, _to_float, _to_int, _file_exists.
- backend/render_modules/subtitle_text.py: format_ass_timestamp, parse_srt_file_to_events,
  _ass_color, format_balanced_sub_text, make_karaoke_ass_text.
- backend/render_modules/__init__.py: package không khởi chạy worker/model.
- backend/video_merger.py: import/re-export các tên trên cho cả backend.video_merger và
  video_merger khi backend nằm trong sys.path. Các caller cũ không cần đổi tên hàm.

Không đổi body/default/signature của helper. Các nhánh compose, OCR, TTS, audio mixing,
FPS, preset và cache vẫn giữ nguyên code. Chưa reload tiến trình đang chạy.
Chưa di chuyển create_master_subtitles_ass hoặc process_video_sub_and_mute trong đợt này.

## Backup và rollback

Backup trước thay đổi:
`VAN_HANH/04_BACKUP/render_modules_20261022_b9ccbb04/video_merger.py`.
Manifest cùng thư mục có checksum gốc/sau sửa và checksum từng module mới.

- SHA256 gốc: 17689ccb9944e60ba14d95ea6f268e75953f6453542d078a9bebe0ebbea3f074
- SHA256 sau sửa: 981e8b0e6b0c3600fed1f40bb31129dc06cb7d44c4d5cef97d78afe7d555f927

Rollback trong cửa sổ bảo trì đã duyệt: kiểm tra file hiện hành còn khớp hash sau sửa,
không có chỉnh sửa mới, rồi khôi phục bản backup. Không tự xóa module nếu caller mới đã dùng.
Không restart dịch vụ hoặc rollback queue/job như một phần của refactor này.

## Bằng chứng kiểm tra

Baseline trước sửa:

```powershell
python -B -m pytest backend/tests/test_subtitle_regions.py backend/tests/test_precise_subtitle_detection.py backend/tests/test_film_bars.py backend/tests/test_render_storage.py -q -p no:cacheprovider
```

Kết quả thực tế: 42 passed in 0.94s.

Sau sửa, chạy tại root Lay video tiktok:

```powershell
python -B -m pytest backend/tests/test_subtitle_regions.py backend/tests/test_precise_subtitle_detection.py backend/tests/test_film_bars.py backend/tests/test_render_storage.py tests_v7/test_hallucination_and_ass_polish.py::test_format_balanced_sub_text -q -p no:cacheprovider
```

Kết quả thực tế: 43 passed in 0.94s.

Kiểm tra độc lập bằng AST trên backup và code mới:
25 top-level hàm/class gốc đều có AST body/default/signature giống nhau sau extraction,
9 hàm đã chuyển file. Backup hash đã đối chiếu. Cả hai đường import cũ có đủ callable.
Import riêng helper trong process mới không nạp cv2, torch, faster_whisper, sqlite3, telegram_bot.
Đây là kiểm tra import, không phải chứng minh toàn bộ ứng dụng không có tác dụng phụ.

4 fixture JSON đọc được và ID/project/status liên kết nhất quán; không phải receipt thực thi.

## Chưa xác minh / phần tiếp theo

PostgreSQL deployment, driver, migration, backup/restore, API mới, Agent và render thật chưa chạy.
Không thêm SQLite mới. SQLite legacy vẫn còn trong code và dữ liệu đang dùng;
phải chuyển có kiểm thử, không thể coi đã loại bỏ chỉ bằng đổi tài liệu.
Đợt tiếp theo tách ASS writer/encoder/compose adapters, giữ compatibility facade và test từng preset;
đưa queue/data có cấu trúc sang PostgreSQL sau khi xác minh database đích.
