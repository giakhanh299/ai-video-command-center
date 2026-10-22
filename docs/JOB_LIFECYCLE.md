# Vòng đời job/task — DRAFT 0.1.0

Các trạng thái sau dành cho API mới; không sửa enum SQLite/Autopilot hiện hành.

| Trạng thái | Ý nghĩa |
|---|---|
| queued | Đã lưu PostgreSQL; chưa có task chạy |
| running | Có attempt đang chạy hoặc pipeline đang tiến hành |
| cancelling | Đã nhận cancel; chờ dừng/đối soát process |
| needs_review | Artifact/QC đã tạo, cần người duyệt video |
| needs_attention | Thiếu model/quyền/approval hoặc kết quả sau sự cố chưa chắc chắn |
| failed | Lỗi đã xác định, không còn retry tự động hợp lệ |
| cancelled | Đã dừng được task và không còn attempt thực thi |

Task có queued, leased, running, succeeded, failed, cancelled, needs_attention.
Job needs_review là render hoàn tất; task succeeded chỉ là bước kỹ thuật thành công.
Agent online/offline/disabled là trạng thái riêng, không đổi job queued thành failed.

## Chuyển trạng thái

- Job queued -> running / cancelled / needs_attention.
- running -> needs_review / failed / cancelling / needs_attention.
- cancelling -> cancelled / needs_attention; không công bố cancelled khi process chưa dừng.
- needs_attention / failed / cancelled -> queued chỉ qua retry được phép, version match,
  budget attempt còn lại, input/config không đổi và đã đối soát attempt cũ.
- needs_review không retry nguyên job; render lại hình là job mới tham chiếu packet.
- Task queued -> leased -> running -> succeeded / failed / needs_attention.
- leased -> needs_attention khi mất liên lạc không xác minh được process;
  queued -> cancelled, running -> cancelled chỉ sau xác nhận dừng; failed -> queued khi được retry.
- Cancel lặp là idempotent; cancel terminal needs_review/failed trả 409, cancelled trả trạng thái cũ.

## Lease, retry và output

Mục tiêu heartbeat 15s, lease 90s, max_attempts 3 (giá trị DRAFT).
Backend dùng thời gian database và fencing token; Agent không tự quyết định lease còn hiệu lực.
Không suy ra process chết chỉ từ heartbeat timeout. Reconciliation chứng minh process tree đã dừng
và kiểm tra output staging trước khi retry; không cần mở cổng điều khiển inbound.
attempt riêng, output key riêng; unique task/attempt/logical output; commit output và completion
trong transaction, bỏ completion stale bằng 409. Không retry task succeeded không cần thiết.
Cancel/complete tranh chấp được serialize bằng row lock + expected version;
kết quả hoàn thành sau khi cancel đã được chấp nhận phải đối soát, không tự publish hoặc ghi đè.
Idempotency key cùng request trả cùng resource; khác body trả 409.
Không giả định execution exactly-once cho TTS API hoặc upload: dùng receipt và reconciliation.

## Mapping legacy cần giữ

Studio pending/retry -> queued; running -> needs_attention khi migration;
review -> needs_review; needs_attention/failed/cancelled giữ nguyên ngữ nghĩa.
Lưu legacy_state và attempts gốc; mapping không được tự làm mất giới hạn retry.
WAIT_EXISTING_REVIEW_IMPORT trong queue Autopilot không tự chuyển queued: giữ blocked import,
đối soát review/output trước khi đưa vào hệ thống mới.
