# Vòng 1 — Thiết kế

Status: DRAFT / AWAITING_CLAUDE_REVIEW. Không PASS.
Contract 0.1.0-draft ngày 2026-10-22; PostgreSQL do người dùng chốt.

Codex đã cung cấp architecture, data model, API draft, manifest rules, lifecycle,
inventory/module boundaries và frontend fixtures. Có extraction helper riêng được ghi tại
RENDER_MODULE_EXTRACTION_REPORT.md; chưa đổi API hay persistence.
Chưa có formal executable JSON Schema/OpenAPI, chưa implementation/contract tests.

| Issue | Severity | Owner | Evidence | Hướng xử lý | Status |
|---|---|---|---|---|---|
| Preset tên/số khác README | HIGH | Codex/Claude | Inventory đối chiếu config với README | Registry-driven UI; giữ key legacy | OPEN |
| PostgreSQL deployment | HIGH | Codex | Docker dev riêng đã migrate/dump/restore; production chưa chốt | Dùng container riêng, không DB Motion | DEV_VERIFIED |
| Cancel protocol cần implementation verifier | HIGH | Codex | Contract yêu cầu cancelled + stop receipt + fencing | Kiểm tra process evidence, race cancel/complete và stale lease | DESIGN_UPDATED / UNTESTED |
| Module config schema | HIGH | Codex | schemas/*.json + model đóng, validator DAG/module và negative tests | Tiếp tục schema cho AI modules khi tích hợp | PILOT_VERIFIED |
| Upload/playback provider chưa chốt | MEDIUM | Codex/Claude | Không có object storage đã xác minh | UI nullable playback; thiết kế upload sau | BLOCKED |
| GPU lock chưa chung các entrypoint | HIGH | Codex | Studio vs Autopilot lock khác scope | Host resource lease + OS lock thống nhất | OPEN |

Claude ghi nhận xét tại đây hoặc chuyển qua người dùng. Codex phản hồi từng issue,
ghi version/impact trước sửa endpoint/field. Chưa gửi thông điệp sang chat khác.

## Phản biện thiết kế Frontend Lead (Claude) — 2026-10-22

1. **Preset & Registry-driven UI**:
   - Đã loại bỏ hoàn toàn việc hard-code "cấu hình 2 = clone phim". Giao diện lấy danh sách preset, schema tham số và tính sẵn sàng động từ `/api/v1/presets` và `/api/v1/modules` (Registry version 1.0.0).
   - Preset `basic_render` và `inspect_media` được đánh dấu "Sẵn sàng"; các preset legacy (wuby, cauhinh2, cauhinh3, cauhinh3_wuby, chidepdicau, song1minhcogivui) hiển thị "Chưa sẵn sàng: Đang tích hợp adapter" để ngăn chặn người dùng gửi job không khả thi.

2. **Thuật ngữ trạng thái (`needs_review` vs `needs_attention`)**:
   - `needs_review`: Hiển thị rõ nghĩa là **"Cần người xem duyệt video"**, có cảnh báo nổi bật: *Đã hoàn tất kỹ thuật nhưng CHƯA ĐỒNG NGHĨA được phép đăng Facebook/TikTok/Telegram*.
   - `needs_attention`: Hiển thị là **"Cần xem xét"**, dùng cho trường hợp lỗi mất lease, tranh chấp tài nguyên (quarantine) hoặc timeout.
   - Không giả lập phần trăm tiến độ khi chưa đo lường được (giữ nguyên số lượng task hoàn thành `X/Y task`).

3. **Giao thức Cancel & Fencing**:
   - UI phân định rõ 2 giai đoạn: `cancelling` (đang gửi yêu cầu dừng và chờ receipt) và `cancelled` (đã dừng xong) hoặc `needs_attention` (nếu Agent mất kết nối trước khi trả lời). Mọi thao tác huỷ đều gửi `expected_version` để tránh race condition.

4. **Upload nhị phân & Playback**:
   - Nhất trí để `playback_url = null` trong contract hiện tại vì chưa có Object Storage public.
   - Đã bổ sung fallback trong UI: nếu có `file_id` và đang chạy local dev, player có thể stream nội bộ qua `GET /api/v1/files/{file_id}/content` (HTTP 206 Range).
   - Đề xuất Codex bổ sung endpoint upload file nhị phân `POST /api/v1/projects/{pid}/inputs` hoặc multipart upload cho đợt tiếp theo.

