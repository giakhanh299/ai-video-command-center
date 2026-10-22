# Vòng 3 — QA

Status: PARTIAL_BACKEND_EVIDENCE. Không PASS toàn hệ thống hoặc vòng QA.
Evidence: ../COMMAND_CENTER_TEST_REPORT.md và tests_command_center/.

| Hạng mục | Owner | Trạng thái và phạm vi |
|---|---|---|
| API auth/ownership/validation/idempotency | Codex | VERIFIED trong tests PostgreSQL dev |
| Claim cạnh tranh, Agent offline, stale lease | Codex | VERIFIED; expired process không tự replay |
| Cancel queued / yêu cầu cancel running | Codex | VERIFIED; final running cancel chưa hỗ trợ |
| Retry budget, replay completion | Codex | VERIFIED trong tests dev |
| CPU render + output/checksum/frame metadata | Codex | VERIFIED với media tổng hợp; không là video người dùng |
| pg_dump / pg_restore staging | Codex | VERIFIED metadata DB; chưa là backup toàn storage |
| GPU/TTS/OCR/Wuby/clone pipeline | Codex | NOT_TESTED mới; preset disabled |
| Secret scan source mới/log dev | Codex | Báo kết quả cụ thể tại test report; không chứng nhận toàn repository |
| Cloud upload / remote Agent transport | Codex | NOT_IMPLEMENTED |
| UI responsive, loading/error, API integration | Claude | VERIFIED_IN_BROWSER (Kiểm thử thực tế, không console error) |
| Production deployment / phê duyệt | Người dùng | NOT_DEPLOYED; chưa có cutover |

Mỗi issue cần severity/evidence/owner/fix/status khi có thêm QA. Không dùng kết quả unit test
để kết luận đã nghe giọng, đã xem video người dùng hoặc đã đăng nội dung.

## Bằng chứng QA Frontend Lead (Claude) — 2026-10-22

1. **Kiểm thử Trực quan trong Trình duyệt (Browser Automation Evidence)**:
   - File chạy thực tế: `file:///D:/0.1_FACE_BOOK/Lay%20video%20tiktok/frontend/command-center.html`.
   - Kết quả: Không có bất kỳ lỗi JavaScript runtime nào (0 console errors).
   - Video session recording WebP: `verify_command_center_ui_1792633558621.webp`.
   - Ảnh chụp màn hình nghiệm thu:
     - Tổng quan (Dashboard): `command_center_overview_1792633569082.png`
     - Danh sách Dự án: `command_center_projects_1792633577087.png`
     - Form Tạo Job: `command_center_create_job_1792633583822.png`
     - Module Registry 1.0.0: `command_center_modules_1792633638727.png`
     - Danh sách Agent: `command_center_agents_1792633657189.png`

2. **Các kịch bản đã kiểm tra**:
   - **Chuyển đổi điều hướng**: Điều hướng mượt giữa 7 màn hình (Tổng quan, Dự án, Chi tiết dự án, Tạo job, Chi tiết job, Module, Agent).
   - **Form tạo job theo Schema**: Radio button chọn preset, tự động kích hoạt dropdown độ phân giải cho `basic_render`, khóa gửi khi preset chưa sẵn sàng (`available: false`).
   - **Modal Cấu hình API**: Hỗ trợ chuyển đổi tức thì giữa Mock và API thật, kiểm tra kết nối `/health` và lưu vào localStorage.
   - **Trạng thái Trực quan**: Thẻ số liệu phân loại rõ 4 nhóm màu (Đang chạy, Đang chờ, Cần duyệt, Cần xử lý); không dùng màu sắc đơn thuần để biểu đạt trạng thái (có nhãn và icon kèm theo).
   - **Trợ năng (Accessibility) & Bàn phím**: Hỗ trợ phím `Tab` duyệt tuần tự, `Enter`/`Space` để chọn dòng/job, `Escape` để đóng modal, các vùng `role="dialog"`, `role="status"`, `aria-live="polite"`.

