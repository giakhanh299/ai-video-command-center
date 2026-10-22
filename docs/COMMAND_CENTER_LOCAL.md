# Backend PostgreSQL — chạy local

Ngày 2026-10-22. Bản triển khai CPU pilot; contract payload `0.1.0-draft`, document revision `0.1.1-draft`.
Đây là backend tách biệt trong `command_center/`, chưa thay bot hoặc SQLite legacy.

## Đã có

- FastAPI `/api/v1`, OpenAPI có schema request/response và Bearer auth.
- PostgreSQL 16 trong container riêng `ai-video-command-center-postgres-dev`, cổng loopback 55439.
- Projects CRUD (delete = archive), job/task/event/output metadata, registry/preset, Agent status.
- Idempotency, expected_version, claim cạnh tranh bằng row lock/SKIP LOCKED,
  resource lock theo machine/resource, heartbeat, lease fencing và quarantine khi mất lease.
- Module `media.probe` và `render.basic` chạy thật bằng Agent outbound.
- `render.basic` dùng lại `backend.video_merger.build_render_command`, CPU libx264,
  không gọi AdvancedRenderService nên không append byte ngẫu nhiên hoặc fallback GPU.
- Output technical verification: size/type/hash, dimensions/FPS/duration/audio, frame count nếu có,
  report khớp source và video. Hoàn tất vẫn là needs_review.
- File lớn ở managed workspace; PostgreSQL chỉ giữ metadata. Không có SQLite/RAM fallback.

## Chưa có

Adapter Wuby/clone phim/TTS/OCR/GPU mới; chuyển dữ liệu legacy; xác minh process-stop remote;
identity provider production; upload HTTP/cloud; signed playback; scheduling Agent/service Windows;
frontend review/integration và production deployment.
Wuby/cauhinh2/cauhinh3/cauhinh3_wuby/chidepdicau/song1minhcogivui hiển thị unavailable,
không giả là đã tích hợp chỉ vì file renderer tồn tại.

## Chuẩn bị môi trường

Tại `D:/0.1_FACE_BOOK/Lay video tiktok`, dùng Python hiện có của dự án:

```powershell
python -m venv --system-site-packages .venv-command-center
& '.\.venv-command-center\Scripts\python.exe' -m pip install -r requirements-command-center.txt
powershell -NoProfile -File scripts/run_command_center.ps1 -Action Prepare
```

Đợt hiện tại đã tạo venv theo cách này; chỉ cài thêm psycopg trong venv, không nâng Torch/CUDA.
`--system-site-packages` tận dụng cv2/numpy/FFmpeg của môi trường đã có. Một máy mới phải xác minh
dependencies của renderer cũ; capability enrollment chỉ quảng cáo basic render khi tìm thấy cv2/numpy
và FFmpeg/ffprobe. Không tự tải model hoặc cài CUDA.

Docker Desktop cần chạy. Prepare chỉ thao tác container có nhãn `codex.task=ai-video-command-center`;
không sửa stack `motions-studio-main-*`. Schema migration chạy bằng lệnh explicit, không tự chạy khi import API.
Prepare tạo schema trong database dev mới; không chạy migration lên SQLite hoặc PostgreSQL Motion.

## Chạy API và Agent

```powershell
powershell -NoProfile -File scripts/run_command_center.ps1 -Action API
```

API: `http://127.0.0.1:8016`; Swagger: `http://127.0.0.1:8016/docs`.
Health public: `/api/v1/health`; readiness và dữ liệu cần owner Bearer token.
Trong đợt triển khai có một process API dev chạy ẩn, thông tin tại
`workspace/command_center_dev/api-process.json`. Không mở instance thứ hai trên cùng cổng.
Launcher API trong terminal chạy foreground; Ctrl+C dừng instance đó.
Không dừng process khác chỉ vì trùng cổng.

Credentials riêng trong `workspace/command_center_dev/credentials.local.json` (đã ignore).
Không chép file này vào Git, frontend bundle, screenshot hoặc báo cáo. Owner token và Agent token khác nhau.
Auth hiện là opaque Bearer cho local owner, không phải SSO/session production.
Không dùng query-string token cho player. Frontend local dùng dev proxy `/api` tới cổng 8016;
không bật CORS `*` hay đưa API ra domain công khai để xử lý lỗi tích hợp.

Agent one-shot, mỗi lần nhận tối đa một task:

```powershell
powershell -NoProfile -File scripts/run_command_center.ps1 -Action Agent
```

Preset basic_render có 2 task, cần chạy Agent hai lần. Chưa tạo daemon/lịch chạy mới.
Agent và backend pilot dùng chung storage root trên máy này; chưa hỗ trợ transport file tới Agent remote.
Kết nối Agent remote yêu cầu HTTPS; localhost HTTP chỉ dành phát triển.
Heartbeat 15s theo mục tiêu contract; one-shot gửi khi bắt đầu, heartbeat và renew task mỗi 10s khi đang xử lý.
API tính Agent offline sau 45s không heartbeat. Chưa có heartbeat nền khi Agent idle.

### Agent chờ lệnh qua 443 (mô hình mới, 2026-10-22)

Từ đợt này Agent có chế độ vòng lặp chờ lệnh (`--loop`): PC không mở cổng vào,
Agent tự gọi ra tới API bằng HTTPS cổng 443, mỗi vòng đều gửi heartbeat rồi claim việc,
nghỉ `CC_AGENT_POLL_SECONDS` (mặc định 5 giây) khi rảnh và backoff khi lỗi.
URL API từ xa khác cổng 443 hoặc dùng http sẽ bị từ chối (`OUTBOUND_443_ONLY` / `TLS_REQUIRED`);
loopback vẫn giữ cho dev local như trên.

Trên PC chạy bằng `CHAY_AGENT_443.bat` ở thư mục gốc, với biến môi trường
`CC_API_URL=https://<api-host>`, `CC_AGENT_ID`, `CC_AGENT_TOKEN` (chỉ lưu tại PC)
và `CC_STORAGE_ROOT`. API + PostgreSQL production phải đặt trên máy chủ ngoài PC
sau HTTPS 443; xem `DEPLOY_CLOUDFLARE.md`. Chưa tạo Windows service/lịch chạy tự khởi động cho vòng lặp này.

## Tạo input/job để frontend thử

1. POST `/api/v1/projects` với owner Bearer + `Idempotency-Key`, body `{ "name": "Dự án" }`.
2. Import MP4 đã chọn bằng CLI trên máy, không gửi local path từ frontend:

```powershell
& '.\.venv-command-center\Scripts\python.exe' -B -m command_center.dev import-input --project-id PROJECT_UUID --path 'D:\video\sample.mp4'
```

3. CLI trả file_id. POST `/api/v1/jobs`:

```json
{
  "schema_version": "0.1.0-draft",
  "project_id": "PROJECT_UUID",
  "preset_id": "basic_render",
  "preset_version": "1.0.0",
  "input_refs": ["FILE_UUID"],
  "overrides": {}
}
```

PROJECT_UUID/FILE_UUID ở ví dụ là placeholder, phải thay bằng UUID thật.
Pilot chưa nhận title override; gửi title khác rỗng bị 422, không âm thầm bỏ qua.
Lấy registry từ `/api/v1/modules` và `/api/v1/presets`; không dùng version `fixture-1` của mock cũ để tạo job thật.
4. Chạy Agent. Xem job/events/outputs. GET `/api/v1/files/{id}/content` có Bearer và Range.
`playback_url` vẫn null; frontend có thể fetch có auth rồi tạo blob URL local, revoke khi đóng player.
Không coi Range 206 là bằng chứng người dùng đã xem/duyệt nội dung video.

## Cancel, retry, sự cố

Queued job cancel ngay; running job -> cancelling. Không tự báo cancelled chỉ từ một boolean.
Remote stop verifier chưa có nên completion cancelled bị 409 STOP_NOT_VERIFIED;
Agent chuyển needs_attention nếu bị cancel trong lúc chạy. Resource giữ quarantine, retry trả
RECONCILIATION_REQUIRED. Hiện chưa có CLI giải quarantine an toàn; không sửa DB thủ công để replay.
Job failed/cancelled đã xác nhận an toàn có thể retry có giới hạn 3 attempts, giữ các task succeeded.
Database lỗi -> 503, không tạo job trong RAM hoặc SQLite.

## Kiểm thử / contract

```powershell
powershell -NoProfile -File scripts/run_command_center.ps1 -Action Test
& '.\.venv-command-center\Scripts\python.exe' -B tools/smoke_command_center.py
& '.\.venv-command-center\Scripts\python.exe' -B tools/export_command_center_contract.py
```

Test PostgreSQL tạo database `cc_test_<UUID>` riêng, chỉ cho config loopback dev 55439,
và dọn đúng database đó sau test. Backup/restore test tạo `cc_restore_<UUID>` riêng bằng pg_dump/pg_restore
trong container; không drop/truncate database dev chính hoặc database Motion.
Không chạy test với DATABASE_URL production.
Smoke HTTP tạo project/job và video tổng hợp mới trong dev, không gọi TTS/LLM/cloud hay publish.

Contract xuất sẵn: `docs/openapi.command-center.json`, `docs/schemas/*.json`.
Test evidence: `docs/COMMAND_CENTER_TEST_REPORT.md`.

## Backup và khôi phục

Backup source/tài liệu trước đợt backend: `VAN_HANH/04_BACKUP/command_center_backend_20261022_e1356345`.
Container data: `workspace/command_center_dev/docker_pgdata`; đây là dữ liệu có trạng thái, không xóa như cache.
Backup logic dùng pg_dump -Fc vào nơi riêng, restore DB staging rồi kiểm tra; không copy data directory đang mở.
Backup DB không bao gồm video: cần lưu cả storage + mapping/checksum và thử khôi phục artifact.
Chưa chốt retention hoặc lịch backup, không tự prune. Không có cutover production để rollback trong đợt này.
PostgreSQL portable đã được tải trước khi Docker bật và đã dừng; backend hiện dùng container 16.
