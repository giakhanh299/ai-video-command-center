# API contract — document revision 0.1.1-draft

Payload schema_version giữ **0.1.0-draft**.
CPU pilot đã triển khai tại http://127.0.0.1:8016/api/v1 với PostgreSQL Docker riêng.
API cũ cổng 8005 không thực hiện hợp đồng này. Đọc COMMAND_CENTER_LOCAL.md trước tích hợp.
OpenAPI thực tế: openapi.command-center.json; nguồn runtime là command_center/api.py.

## Những điểm được cụ thể hóa ở revision 0.1.1

- Không đổi tên endpoint/enum/field của draft cũ. Thêm GET /files/{id}/content có Bearer/Range;
  thêm Claim.attempt_id và Claim.input_files cho Agent; resource nhận thêm cpu:0.
- Auth hiện là opaque Bearer local owner và credential Agent riêng, chưa có identity provider/session production.
- Preset thực thi: inspect_media và basic_render version 1.0.0; module media.probe và render.basic.
  Wuby/clone presets vẫn unavailable. Preset.available nói adapter sẵn sàng, Agent có thể đang offline.
- Input import qua CLI; chưa có binary upload từ web. Agent/backend dùng chung managed storage local.
- File registration đồng bộ xác minh bytes và trả verification=verified khi đạt, không chỉ nhận metadata.
  Pilot chỉ hỗ trợ video/mp4 và report application/json; audio/subtitle/packet trả FILE_KIND_NOT_SUPPORTED.
- Cancel queued hoạt động; running cancel được nhận nhưng final cancelled bị chặn STOP_NOT_VERIFIED.
  Chưa có verifier remote process-stop hoặc thao tác giải quarantine; UI cần needs_attention.
- Event.message phía Agent không được lưu nguyên văn; backend dùng catalogue an toàn theo code.
- Pilot preset không hỗ trợ title override, schema preset trả object rỗng; khác rỗng bị 422 OVERRIDE_NOT_SUPPORTED.
- Idempotency trả cùng resource; response có thể phản ánh trạng thái hiện tại của resource đó.
- TTL 7 ngày chưa prune, chưa có rate limiter production; API chỉ bind loopback, không public.

Ảnh hưởng frontend: dùng registry thật, token qua header, dev proxy khi khác origin;
không dùng fixture-1 làm preset_version thật; không bật upload/duyệt/publish chưa có API.
Chưa có Claude review; nhận xét phải ghi trong reviews/ROUND_2.md.

## Quy ước chung

User auth mục tiêu: Bearer session đã được backend xác minh; pilot dùng owner token local; kiểm tra owner/project mọi request.
Agent auth: credential riêng, rotate/revoke được, scope theo máy/module; không dùng token frontend.
Không lưu secret trong job config. Identity provider production chưa chốt; CLI dev provision credential riêng.
Error: {"error":{"code":"INVALID_MANIFEST","message":"Manifest không hợp lệ","request_id":"req_demo","details":[]}}.
Các lỗi chung: 401 thiếu/sai auth; 403 thiếu scope; 404 resource không thuộc principal hoặc không tồn tại;
413 body quá lớn; 422 schema/validation; 429 rate limit; 503 dependency chưa sẵn sàng.
Không trả raw exception/path/credential; details chỉ có field/code/message đã lọc.
Timestamp RFC3339 UTC, ID UUID, cursor opaque; limit 1..100 mặc định 25.
Mutation dùng expected_version nếu đụng resource hiện hữu; mismatch 409.
POST tạo/retry cần Idempotency-Key (8..128 ký tự); khác request cùng key -> 409 IDEMPOTENCY_CONFLICT.
Key scope principal+method+route; TTL dự kiến 7 ngày, chỉ prune sau khi retention được chốt.

## Endpoints đề xuất

| Method / path | Auth | Request | Response thành công | Lỗi riêng |
|---|---|---|---|---|
| GET /health | public | none | 200 {status:"ok",api_version:"0.1.0-draft"} | không tiết lộ config |
| GET /ready | user | none | 200 {status:"ready",database:"ready"} | 503 NOT_READY; Agent offline không làm API unready |
| GET /agents | user | cursor,limit | 200 {items:Agent[],next_cursor:null|string} | lỗi chung |
| GET /projects | user | cursor,limit | 200 {items:Project[],next_cursor:null|string} | lỗi chung |
| POST /projects | user | {name:string 1..120} | 201 Project | 422 INVALID_PROJECT |
| GET /projects/{id} | user | none | 200 Project | 404 |
| PATCH /projects/{id} | user | {name,expected_version} | 200 Project | 409 VERSION_CONFLICT |
| DELETE /projects/{id} | user | {expected_version} | 200 Project archived_at set; archive, không xóa artifact | 409 ACTIVE_JOBS |
| GET /modules | user | none | 200 {items:Module[]} | chỉ module được phép cho principal |
| GET /presets | user | none | 200 {items:Preset[]} | không trả secret/local config |
| POST /jobs | user | CreateJob xem JSON_SCHEMA.md | 201 Job (queued) | 409 MODULE_NOT_READY; 422 INVALID_MANIFEST |
| GET /projects/{id}/jobs | user | cursor,limit,status | 200 {items:Job[],next_cursor:null|string} | 422 INVALID_STATUS |
| GET /jobs/{id} | user | none | 200 Job + tasks:Task[] | 404 |
| GET /jobs/{id}/events | user | cursor,limit | 200 {items:Event[],next_cursor:null|string} | 422 INVALID_CURSOR |
| GET /jobs/{id}/outputs | user | none | 200 {items:File[]} | URL xem chỉ có sau xác minh storage |
| POST /jobs/{id}/cancel | user | {expected_version} | 202 Job; cancelled lặp trả 200 | 409 INVALID_TRANSITION |
| POST /jobs/{id}/retry | user | {expected_version} | 202 Job cùng id, attempt mới khi được claim | 409 INVALID_TRANSITION / RECONCILIATION_REQUIRED / RETRY_LIMIT |
| POST /agent/heartbeat | agent | {agent_id,capability_version,active_attempt_ids} | 200 {server_time,lease_seconds:90} | 409 AGENT_DISABLED; không tự gia hạn task |
| POST /agent/claims | agent | {agent_id,resource:"cpu:0" hoặc "gpu:0"} | 200 Claim hoặc 204 hết việc | 409 RESOURCE_BUSY |
| POST /agent/tasks/{id}/renew | agent | {attempt,lease_token} | 200 {lease_expires_at,cancel_requested} | 409 STALE_LEASE |
| POST /agent/tasks/{id}/events | agent | {attempt,lease_token,event_id,level,code,message} | 201 Event; event_id lặp trả 200 | 409 STALE_LEASE |
| POST /agent/tasks/{id}/complete | agent | {attempt,lease_token,status,output_ids,error_code,stop_receipt_id} | 200 Task | 409 STALE_LEASE / OUTPUT_UNVERIFIED / STOP_NOT_VERIFIED |
| POST /agent/files | agent | FileRegistration | 201 File pending_verification | 422 INVALID_FILE |

Không có endpoint thực thi shell, đăng module tùy ý hoặc sửa raw registry JSON từ frontend.
Config module thông qua preset version + overrides đã allowlist; cập nhật registry là thay đổi code/admin
được review. Preset endpoint cung cấp config schema để frontend dựng form.

## DTO dự kiến

- Project: id, name, version>=1, archived_at nullable, created_at, updated_at.
- Agent: id, status online/offline/disabled, last_seen_at nullable, capabilities[], active_task_count.
  Không trả executable path, model path hoặc credential.
- Module: id, version, actions[], config_schema, available, unavailable_reason nullable.
- Preset: id (key legacy), version, label, available, modules[], override_schema.
- Job: id, project_id, preset_id, preset_version, status (JOB_LIFECYCLE.md), version,
  created_at, updated_at, progress {completed_tasks,total_tasks,percent:null|number},
  current_task_id nullable, error {code,message}|null. Percent chỉ tính từ tiến độ có chứng cứ.
- Task: id, task_key, module, action, module_version, status, attempt, depends_on[], error nullable.
- Event: id, sequence, job_id, task_id nullable, timestamp, level info/warning/error, code, message.
- File: id, kind, media_type, size_bytes, sha256, verification pending/verified/rejected,
  playback_url nullable, expires_at nullable. Không có local absolute path trong DTO.
- FileRegistration: project_id, job_id, task_id, attempt, lease_token, logical_name (basename),
  kind video/audio/subtitle/report/packet, media_type, size_bytes, sha256, storage_key.
  Backend cấp/quyết định storage_key theo attempt; Agent không được đăng key của tenant khác.
- Claim: task:Task, manifest:Manifest, attempt, attempt_id UUID, lease_token, lease_expires_at,
  input_files [{id,storage_key,kind,media_type,size_bytes,sha256}];
  chỉ trả input bindings cho Agent đúng scope qua kết nối TLS.

Trường DTO ở trên là danh sách đóng cho contract draft, ngoài trường bị từ chối ở request.
Các object Claim/manifest không được đưa nguyên sang frontend.
Complete status nhận succeeded/failed/needs_attention/cancelled. output_ids là UUID[] unique;
error_code nullable string từ allowlist; stop_receipt_id nullable UUID file report đã xác minh.
cancelled chỉ hợp lệ khi backend đã ghi cancel_requested=true, output_ids rỗng và receipt chứng minh
process tree của đúng attempt đã dừng. Agent cấp receipt qua /agent/files; verifier đối soát attempt,
PID + process creation time + child process evidence, không chỉ tin một boolean từ client.
Lease/token stale vẫn trả 409; job chuyển needs_attention để reconciliation, không công bố cancelled.
Lặp cùng completion digest trả kết quả cũ; thay status/output/receipt sau completion trả 409.

## Ví dụ và fixture

POST /jobs dùng fixtures/command-center/create-job.json; response mock ở job-queued.json.
GET /jobs/{id} có job-needs-review.json; lỗi mẫu ở error-module-not-ready.json.
Fixtures minh họa hợp đồng, không phải receipt render thật hay module đã sẵn sàng.
HTTP upload binary/presigned URL chưa chốt vì object storage chưa xác minh; metadata API không thay thế
kiểm tra object bytes/size/type/checksum. playback_url=null khi chưa có đường phục vụ được xác thực.
