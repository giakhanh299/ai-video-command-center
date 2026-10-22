# Vòng 2 — Triển khai và tích hợp

Status: BACKEND_PILOT_IMPLEMENTED / AWAITING_CLAUDE_INTEGRATION_REVIEW. Không PASS cả vòng.
Contract document revision 0.1.1-draft; payload vẫn 0.1.0-draft.

Codex cung cấp API thật, OpenAPI typed, schemas, fixtures cũ, lệnh local và test evidence.
Endpoint /api/v1 đang phục vụ tại loopback 8016; PostgreSQL riêng trong Docker cổng 55439.
Đã thử media.probe + render.basic qua Agent outbound trên clip tổng hợp, không chỉ mock.
43 regression tests của helper/renderer cũ đã đạt. Chi tiết mới tại ../COMMAND_CENTER_TEST_REPORT.md.

| Issue | Severity | Owner | Evidence / hướng xử lý | Status |
|---|---|---|---|---|
| Chưa có frontend review API thật | HIGH | Claude | Đối chiếu OpenAPI/form/loading/error và báo mismatch | REVIEW_COMPLETED |
| Upload HTTP chưa có | MEDIUM | Codex/Claude | Input import CLI; UI không tạo endpoint giả | OPEN |
| Wuby/clone adapters chưa tích hợp | HIGH | Codex | Registry unavailable, không thực thi nhầm preset | OPEN |
| Running cancel chưa có stop verifier | HIGH | Codex | STOP_NOT_VERIFIED; needs_attention + quarantine | BLOCKED_ON_IMPLEMENTATION |
| Auth production chưa có | HIGH | Codex | Local owner Bearer, loopback; không public | OPEN |
| Mock version khác registry thật | MEDIUM | Claude | Đã đồng bộ version 1.0.0 và presets registry vào cc-api.js | RESOLVED |

Không âm thầm đổi hợp đồng cho frontend chạy; mọi nhận xét thêm version/impact và người phụ trách.

## Nhận xét Tích hợp & Đối chiếu API Thật của Frontend Lead (Claude) — 2026-10-22

1. **Đối chiếu OpenAPI (`docs/openapi.command-center.json`) vs Frontend Client**:
   - **Mismatch 1 (GET Jobs Global)**: OpenAPI chỉ cung cấp endpoint `GET /api/v1/projects/{pid}/jobs` (danh sách job theo dự án), **không có endpoint `GET /api/v1/jobs` toàn cục**. Để hiển thị danh sách job gần đây trên màn hình Tổng quan, Frontend Client phải gọi `GET /api/v1/projects` trước, sau đó truy vấn song song jobs của từng project. *Đề xuất Codex: bổ sung `GET /api/v1/jobs?status=...&cursor=...&limit=...` trong contract revision tiếp theo.*
   - **Mismatch 2 (Overrides & Validation Error 422)**: Backend pilot `basic_render` yêu cầu tham số `width` (360|720|1080) và `height` (640|1280|1920) theo schema, **không nhận `title`**. Gửi `title` sẽ bị trả về 422 `VALIDATION_ERROR`. Frontend đã bổ sung parser dynamic schema để sinh đúng form độ phân giải cho `basic_render` và chỉ gửi trường được phép trong schema.
   - **Mismatch 3 (Xác thực Owner Bearer Token)**: Backend yêu cầu header `Authorization: Bearer <owner_token>` với độ dài tối thiểu 32 ký tự. Frontend đã bổ sung modal "Cấu hình API" cho phép nhập và lưu token cục bộ trong trình duyệt (localStorage), không đóng gói hardcode vào bundle.
   - **Mismatch 4 (Idempotency-Key)**: Các thao tác `POST /projects`, `POST /jobs`, `POST /cancel`, `POST /retry` đều đã được `RealApiClient` tự động sinh và đính kèm UUIDv4 `Idempotency-Key` (36 ký tự) hợp lệ.

2. **Giải quyết Mismatch Mock Version (ISSUE-018)**:
   - File `frontend/cc-api.js` đã được cập nhật toàn bộ từ `fixture-1` sang **`version: 1.0.0`**, đồng bộ tuyệt đối với `command_center/registry.py`.
   - Các preset `basic_render` (v1.0.0) và `inspect_media` (v1.0.0) là `available: true`. Các preset AI/GPU khác là `available: false` kèm lý do cụ thể.
   - Bổ sung job `jobPilotComplete` (`basic_render` v1.0.0 hoàn tất kỹ thuật, trạng thái `needs_review`) lấy từ kết quả thực tế của smoke test CPU Pilot.

