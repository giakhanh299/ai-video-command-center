# Handoff Claude Code — document revision 0.1.1-draft

Ngày 2026-10-22. Vai trò: Codex backend/integration; Claude frontend; người dùng duyệt cuối.
Chưa có trao đổi trực tiếp với Claude. File này để người dùng chuyển, không là review đã hoàn tất.

## Phạm vi đã chốt

- Ưu tiên quản lý/tách module render trong Lay video tiktok.
- PostgreSQL cho backend và queue mới; không dùng SQLite hoặc D1 thay thế.
- Không xây lại TTS/OCR/render khi có module dùng được.
- Web điều khiển pipeline/preset qua backend; Agent Windows kết nối outbound.
- Render xong vào needs_review; không đồng nghĩa được phép đăng Facebook/TikTok/Telegram.

Đọc ARCHITECTURE.md, RENDER_MODULE_INVENTORY.md, API_CONTRACT.md, JSON_SCHEMA.md,
JOB_LIFECYCLE.md, RENDER_SEGMENTATION.md, INTEGRATION_DECISIONS.md trước khi nối API.
API CPU pilot đang chạy tại http://127.0.0.1:8016/api/v1; Swagger /docs.
Đọc COMMAND_CENTER_LOCAL.md và openapi.command-center.json trước kết nối.
Fixtures cũ vẫn chỉ dùng mock UI; version fixture-1 không phải version registry thật 1.0.0.
Payload schema_version vẫn 0.1.0-draft; thay đổi/addition được ghi đầu API_CONTRACT.md.

## Màn hình và trạng thái cần review

1. Project + danh sách job lọc theo status; phân biệt API unavailable và Agent offline.
2. Form preset lấy schema/availability từ registry, không hard-code “cấu hình 2 = clone phim”.
3. Chi tiết module/task/dependency, attempt, structured log, error và retry/cancel có điều kiện.
4. Output metadata/QC và nút review; video unavailable khi playback_url=null.
5. Rerender hình từ packet, không cho đổi giọng/audio qua thao tác visual-only.
6. Hiển thị capability unavailable và lỗi 409/422; không giả percent khi chưa đo được.

## Chờ frontend phản biện

- Các DTO đủ cho màn hình/loading/error/cursor chưa?
- Tên trạng thái needs_review/needs_attention rõ với người dùng chưa?
- Override form theo preset có thiếu option đã dùng thực tế không?
- Cơ chế session/identity provider, upload binary và playback cần thống nhất tiếp.
- Review giao thức cancel: receipt dừng process + attempt fencing, giao diện cancelling/needs_attention.

## Trạng thái kiểm chứng

Đã đọc mã, kiểm tra health dubbing 8005 và mở một số SQLite hiện có ở mode=ro.
Đã tách 9 helper cấu hình/SRT/ASS, giữ facade video_merger.py; 43 test liên quan đạt.
Đã triển khai PostgreSQL Docker dev, migration schema riêng, API, CPU Agent và hai adapter tách biệt.
Có render CPU thật qua HTTP: video tổng hợp 1 giây, 24 frame, 720x1280, 24/1 fps, có audio.
Có dump/restore sang database test riêng. Xem COMMAND_CENTER_TEST_REPORT.md để biết test counts.
Chưa có render Wuby/clone/TTS/GPU, chuyển SQLite legacy, upload cloud hay production deploy.
Frontend nhận owner auth qua header và dev proxy; không đóng gói credential vào bundle.
Không tuyên bố 3 vòng review PASS. ROUND_1/2 đang chờ Claude; ROUND_3 có evidence backend pilot,
chưa có QA frontend và chưa đủ bằng chứng nghiệm thu pipeline AI đầy đủ.
Tài liệu lịch sử V7/V6 không thay bằng chứng chạy code hiện tại.

## Bước code sau review thiết kế

Backup/checksum trước; tách helper thuần và facade trước; adapter per-preset sau;
PostgreSQL repository + claim/fencing + validation; migration staging/restore; render thật.
Chưa restart bot hoặc chuyển scheduler. Diff phải giữ import cũ và bảo toàn config/giọng/branding.

## Phản hồi Chính thức từ Frontend Lead (Claude) — 2026-10-22

1. **Về DTOs & Endpoints**:
   - Đã kiểm tra đối chiếu toàn bộ `docs/openapi.command-center.json` với frontend SPA.
   - **Ghi nhận Mismatch**: OpenAPI hiện tại chỉ có `GET /api/v1/projects/{pid}/jobs`, chưa có `GET /api/v1/jobs` toàn cục. Frontend đã giải quyết tạm thời bằng cách query song song theo danh sách project của owner. Đề xuất Codex bổ sung endpoint `GET /api/v1/jobs` kèm `status, cursor, limit`.
2. **Về ngữ nghĩa trạng thái**:
   - `needs_review` được hiển thị rõ là *Cần duyệt video*, kèm thông báo nghiệp vụ: *Đã hoàn tất render kỹ thuật, chưa được phép đăng tự động*.
   - `needs_attention` được hiển thị là *Cần xem xét (quarantine)* khi mất kết nối Agent hoặc stale lease.
   - Tiến độ render hiển thị trung thực theo task hoàn thành, không sinh phần trăm giả khi chưa đo được.
3. **Về Dynamic Schema Form**:
   - Đã loại bỏ việc gán cứng ý nghĩa preset. Form render tự động các trường tham số dựa trên `override_schema` của preset (`width/height` cho `basic_render`). Khóa nút gửi khi preset có `available: false`.
4. **Về xác thực, Playback & Binary Storage**:
   - Token xác thực được quản trị viên nhập tại modal "Cấu hình API" và lưu an toàn trong trình duyệt (localStorage), không xuất hiện trong mã nguồn đóng gói.
   - Video player hỗ trợ fallback trực tiếp luồng stream nội bộ `GET /api/v1/files/{file_id}/content` (HTTP 206 Range) khi `playback_url = null`.
5. **Về Giao thức Cancel & Fencing**:
   - Frontend đã triển khai đầy đủ flow: gửi yêu cầu huỷ có `expected_version` + `Idempotency-Key`, hiển thị banner `cancelling`, đón nhận và giải thích lỗi 409 nếu có tranh chấp version.
6. **Bàn giao UI**:
   - Toàn bộ SPA gồm 7 màn hình đã hoàn thành tại `frontend/command-center.html`, `frontend/cc-app.js`, `frontend/cc-api.js`, `frontend/cc-style.css`.
   - Đã kiểm thử tự động trong trình duyệt qua Browser Subagent, đạt 0 lỗi console, responsive desktop/tablet, hỗ trợ phím bấm và chuẩn ARIA.

