# Quyết định tích hợp

Document revision 0.1.1-draft, payload version 0.1.0-draft, ngày 2026-10-22. Chưa được Claude review.

| ID | Quyết định | Cơ sở / trạng thái |
|---|---|---|
| D001 | PostgreSQL cho mọi dữ liệu có cấu trúc của backend/queue mới | Người dùng yêu cầu trực tiếp; không fallback SQLite |
| D002 | Ưu tiên module Lay video tiktok | Người dùng xác định phạm vi; các dự án khác chỉ tham khảo |
| D003 | Tách theo chức năng render, không suy diễn thành chia clip | ASR, voice, OCR, background, compose, QC là các ranh giới chính |
| D004 | Giữ facade/import/signature legacy khi tách | Giảm nguy cơ phá bot/adapter hiện có |
| D005 | Không dùng handle_video_download làm worker API | Handler có thông báo và bàn giao ngoài render |
| D006 | Phân biệt Wuby overlay và Wuby editorial | Bridge editorial có fps=12, accept_legacy_clone; không tương đương đường trực tiếp |
| D007 | Preset lấy từ registry thực tế | cauhinh2 hiện là film_review_black; README cũ không là nguồn hợp đồng |
| D008 | Job render hoàn tất ở needs_review | Chưa phải đã duyệt nội dung hay được phép publish |
| D009 | Không mở listener điều khiển Windows công khai | Agent kết nối outbound đã xác thực |
| D010 | Pilot chỉ bật media.probe/render.basic | Có tests và HTTP render thật; Wuby/TTS/OCR/GPU chưa bật |
| D011 | PostgreSQL Docker riêng cho dev | Người dùng đã bật Docker; không sửa postgres Motion |
| D012 | Không âm thầm bỏ title ở pilot | Override khác rỗng trả 422; registry form object rỗng |

## Vấn đề cần xử lý trước cutover

- R01 HIGH: queue SQLite trong wuby_studio có thật và bền vững; báo cáo ban đầu đã bỏ sót.
  Không xây queue RAM mới; chuyển semantics sang PostgreSQL và thử migration staging.
- R02 HIGH: bridge.py ép 12fps khác README source FPS. Lưu profile version, không sửa FPS ngầm.
- R03 HIGH: renderer.py append 16 byte ngẫu nhiên sau os.replace; output checksum có thể khác
  khi render lại cùng nội dung. Không dùng checksum output làm idempotency duy nhất;
  xem xét bỏ hành vi này trong thay đổi riêng sau baseline/duyệt, không tự sửa đợt này.
- R04 HIGH: process_video_sub_and_mute có cache dựa tồn tại/kích thước/mtime ở một số nhánh.
  Adapter mới phải bind source/config/module hash, không tin kết quả cache chỉ vì file lớn.
- R05 HIGH: hai prepare_dialogue_replacement khác module. Registry phải chỉ định implementation,
  strategy và fallback thực tế, không chỉ tên hàm.
- R06 HIGH: khóa GPU giữa Studio, bot và Autopilot chưa hợp nhất.
- R07 HIGH: import module có thể nạp model/config hoặc khởi động tác vụ; thử trong môi trường cô lập.
- R08 MEDIUM: junction lay_video_tiktok trỏ D:/Lay video tiktok không tồn tại ở lần kiểm tra;
  root thật D:/0.1_FACE_BOOK/Lay video tiktok vẫn có. Chưa sửa junction.
- R09 DEV_VERIFIED: PostgreSQL Docker riêng đã kết nối/migrate và thử dump/restore staging.
  Production database, retention và lịch backup vẫn chưa chốt.
- R10 BLOCKED: cloud upload/playback, Access, domain và object storage chưa xác minh.

## Quản lý thay đổi hợp đồng

Mỗi thay đổi endpoint/field/enum ghi version, lý do, ảnh hưởng, migration/compatibility và người review.
Không âm thầm đổi sau khi frontend bắt đầu. Chuyển bản handoff qua người dùng;
chưa có bằng chứng Codex và Claude Code trao đổi trực tiếp tự động.
