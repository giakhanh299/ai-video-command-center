# Backend PostgreSQL — bằng chứng ngày 2026-10-22

Phạm vi: CPU pilot của Command Center; không là nghiệm thu toàn bộ AI Video Command Center.
Ngôn ngữ báo cáo: tiếng Việt. Không có production deployment hoặc phê duyệt cutover.

## Thay đổi đã thực hiện

- Backend mới trong command_center/: FastAPI, psycopg, migration PostgreSQL schema riêng,
  owner/Agent auth, project/job/task/event/file APIs, registry và manifest validation.
- Queue PostgreSQL có idempotency, version check, claim cạnh tranh, heartbeat/lease,
  fencing completion, giới hạn retry và giữ quarantine khi chưa chắc tiến trình đã dừng.
- Adapter riêng command_center/modules/media.py và basic_render.py. Agent chỉ gọi allowlist;
  render CPU dùng lại builder cũ, không chạy shell string hoặc handler Telegram.
- OpenAPI + JSON schemas xuất sẵn cho frontend. Không thay contract payload version hoặc enum cũ;
  document revision 0.1.1-draft mô tả additions và các giới hạn pilot.
- Venv tách biệt; chỉ cài thêm psycopg ở venv trong đợt này, không nâng Torch/CUDA/model.
- Container ai-video-command-center-postgres-dev, PostgreSQL 16.15, loopback 55439.
  Stack motions-studio-main-* và database của nó không được sửa bởi đợt triển khai này.

## Test tự động

Đã chạy bộ tích hợp PostgreSQL thật, không dùng SQLite hay mock database:

```powershell
$env:CC_TEST_CONFIG = (Join-Path (Get-Location) 'workspace/command_center_dev/credentials.local.json')
& '.\.venv-command-center\Scripts\python.exe' -B -m pytest tests_command_center -q -p no:cacheprovider
```

Kết quả lần đầy đủ sau cùng: **39 passed, 1 warning in 32.61s**.
Trước đó chạy cùng 43 regression tests của subtitle/film-bars/render-storage: **80 passed in 30.10s**
(37 backend cases tại thời điểm đó + 43 regression). Sau đó thêm kiểm tra title override và heartbeat scope,
cùng assertions completion replay. Không cộng các lần chạy lặp thành số test mới.
Tổng coverage đã chạy: 39 backend cases và 43 legacy regression cases, 82 cases phân biệt.

Sau khi cụ thể hóa OpenAPI error-envelope/Range responses, kiểm tra hẹp:

```powershell
& '.\.venv-command-center\Scripts\python.exe' -B -m pytest tests_command_center/test_exported_schemas.py tests_command_center/test_postgres_api.py::test_validation_redacts_client_input_and_limits_body tests_command_center/test_postgres_api.py::test_health_auth_readiness_and_separate_agent_scope -q -p no:cacheprovider
```

Kết quả: **4 passed, 1 warning in 2.31s**. Không có thay đổi renderer legacy sau lượt regression đạt.
Warning là Starlette TestClient thông báo deprecation httpx trong stack hiện hữu;
không sửa/nâng stack chỉ để bỏ warning. Không coi AST parse là lint hoặc typecheck.

Các tình huống có test:

- Auth owner/Agent tách biệt; project/job của principal khác trả 404.
- Validation không echo raw client input; giới hạn body 256 KiB; path traversal bị từ chối.
- Manifest không nhận shell/action/module tùy ý, version lạ, field thừa, cycle hoặc input không bind.
- PostgreSQL outage trả 503, không fallback RAM/SQLite.
- Agent offline vẫn giữ queued job; khởi tạo lại API vẫn đọc được job/input từ PostgreSQL.
- Concurrent create cùng idempotency key tạo đúng một job; body khác trả conflict.
- Sáu claim cạnh tranh chỉ một claim thành công; hai Agent cùng máy không chiếm cùng resource.
- Lease hết hạn -> needs_attention, resource giữ quarantine; stale completion/retry bị chặn.
- Queued cancel/retry; running cancel không nhận completion succeeded khi cancel đã được chấp nhận.
- Completion cần đúng outputs, bytes/hash/role/report; replay cùng digest idempotent, khác digest conflict.
- Retry không reset attempt budget; heartbeat không mạo nhận attempt của Agent khác.
- Log catalogue bỏ nguyên văn message có bí mật; lỗi API không đưa driver/DSN vào response.
- Render CPU thật qua PostgreSQL/Agent; output video kiểm tra dimensions/FPS/audio/frame metadata.
- pg_dump -Fc và pg_restore sang database cc_restore_<UUID>, đối chiếu job/input/hash metadata.

Tests chỉ tạo và xóa database cc_test_<UUID>/cc_restore_<UUID> của chính test;
không truncate/drop database dev chính hoặc database Motion. DB backup không gồm bản sao video storage:
restore test đối chiếu references với artifact vẫn tồn tại, chưa là thử khôi phục toàn hệ thống từ mất ổ đĩa.

## Smoke HTTP thật

Chạy API bằng process Windows riêng, Agent gọi HTTP localhost thật, không phải TestClient:

```powershell
& '.\.venv-command-center\Scripts\python.exe' -B tools/smoke_command_center.py
```

Kết quả sau tích hợp attempt_id và heartbeat:

| Thuộc tính | Bằng chứng |
|---|---|
| Project | fd208a02-0fdb-42ef-86fa-4ac98ac2abaf |
| Job | 0c353de4-1eec-4643-8d18-debec9505149 |
| Pipeline | media.probe -> render.basic, cả hai succeeded |
| Job cuối | needs_review |
| Video file ID | 2a9a290e-18a4-4e8c-884a-1ff2e5fa87a2 |
| Media | H.264, 720x1280, 24/1 fps, 24 frames, 1.000s, có audio |
| GET file có Bearer + Range | HTTP 206, 128 bytes theo range đã yêu cầu |
| Outputs | 3: probe report, render MP4, render report |

Clip dùng test pattern và sóng sine tổng hợp, không phải TTS hoặc video người dùng.
Chưa kiểm tra browser player hoặc duyệt chất lượng bằng mắt/tai; HTTP 206 không chứng minh điều đó.
Summary đầy đủ không chứa credential ở workspace/command_center_dev/smoke-summary.json.

## Secret/syntax và môi trường

- 22 file Python mới/tools/tests đã parse AST thành công.
- Đối chiếu password, owner token, Agent token và DSN thực tế với 59 file source/tests/public-doc/schema/log dev
  tại lần scan cuối: không phát hiện credential. Đây là scan có phạm vi,
  không phải chứng nhận toàn bộ Git/history/frontend của các dự án cũ.
- Dev settings có guard: inherited CC_DATABASE_URL không thể chuyển migration dev sang DB bên ngoài.
- Credential/container env/data/runtime logs nằm dưới workspace đã ignore; venv và backup cũng ignore.
- PostgreSQL portable tải từ EDB trước khi Docker bật đã dừng; API hiện dùng container riêng.
- Sau reload API dev cuối cùng: readiness HTTP 200; OpenAPI đang phục vụ giống chính xác file export;
  job smoke vẫn needs_review và file Range vẫn HTTP 206. Không reload bot hoặc các service Motion.

## Phần chưa hoàn thành

| Hạng mục | Trạng thái |
|---|---|
| Kiểm kê ban đầu | Có; runtime/cloud toàn bộ chưa xác minh |
| API contract được Claude review | Chưa; handoff đã cập nhật |
| PostgreSQL API/queue CPU pilot | Đã chạy/test thực tế |
| Windows Agent | One-shot CPU outbound đã chạy; chưa daemon/recovery AI đầy đủ |
| Wuby/clone/TTS/OCR/GPU render | Chưa tích hợp/test qua backend mới; preset unavailable |
| SQLite legacy migration/cutover | Chưa làm; dữ liệu legacy giữ nguyên |
| Stop receipt verifier / giải quarantine | Chưa làm; fail closed, không tự replay |
| Upload cloud/playback web | Chưa; có API local file auth/Range, chưa UI integration |
| Backup/restore toàn artifact storage | Chưa; mới thử DB staging + metadata references |
| Production/SSO/TLS/rate-limit/retention | Chưa triển khai/chốt |
| Ba vòng Codex/Claude | Chưa PASS; cần frontend review và QA tiếp |
