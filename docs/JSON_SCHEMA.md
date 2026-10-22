# JSON schema và manifest — document revision 0.1.1-draft

Hai lớp: CreateJob do client gửi; Manifest do backend tạo sau xác thực quyền/registry.
Backend và Agent đã dùng model đóng + kiểm tra semantic trong command_center/models.py và registry.py.
Schema xuất tại schemas/create-job.schema.json và schemas/manifest.schema.json;
DAG, ownership, file integrity và module availability vẫn cần semantic validation.
Payload schema_version giữ 0.1.0-draft để tương thích bản draft trước.
Không nhận manifest server-owned từ client để sửa status, task graph hay attempt.

## CreateJob

Object đóng, required: schema_version, project_id, preset_id, preset_version, input_refs, overrides.

| Field | Type / điều kiện |
|---|---|
| schema_version | const "0.1.0-draft" |
| project_id | UUID; resource thuộc principal |
| preset_id | allowlist key từ /presets, không phải chuỗi import Python |
| preset_version | immutable version string 1..64 ký tự từ registry |
| input_refs | 1..8 UUID file đã đăng ký và verified, cùng project |
| overrides | object đóng; model chung có title <=200 nhưng pilot inspect_media/basic_render chỉ chấp nhận rỗng; xem override_schema từng preset |

Không nhận source URL tự do trong phiên bản đầu; tải/import được giải quyết thành File trước.
Không nhận channel_cfg, path tuyệt đối, source SRT path, _voice_profile_snapshot hoặc shell/filter string.
Đối với bản triển khai đầu, chỉ preset available=true mới tạo job được.

## Manifest (server-owned)

Object đóng: schema_version const như trên; project_id UUID; job_id UUID;
created_at RFC3339; pipeline 1..32 task; input_refs file UUID[]; output_refs file UUID[].
Mỗi task là object đóng:

| Field | Type / điều kiện |
|---|---|
| task_id | UUID duy nhất trong manifest |
| task_key | regex ^[a-z][a-z0-9_]{0,63}$; unique |
| module | ID registry xem RENDER_MODULE_INVENTORY.md; không suy ra import từ chuỗi |
| action | enum theo module; ban đầu đề xuất run, rerender dùng module riêng |
| module_version | version bất biến khớp registry |
| depends_on | task UUID[] unique; tất cả cùng pipeline; không self/cycle |
| config | object theo config_schema của module version; unknown field bị từ chối |
| input_refs / output_refs | file UUID[], tối đa 32 mỗi loại; quyền/scope kiểm tra server |
| status | enum task trong JOB_LIFECYCLE.md; snapshot, không là lệnh chuyển trạng thái |
| attempt | integer >=0; task chưa claim bằng 0 |

Backend sinh snapshot config từ preset đã resolve; không serialize secret từ channels_config.json.
Giọng dùng profile ID/version + reference artifact có quyền, không nhúng credential/ref_text riêng tư vào UI.
Agent kiểm tra lại module/action/version, graph, artifact checksum và root containment trước thực thi.

## Kiểm tra không thể chỉ dùng JSON Schema

DAG không cycle; UUID/file ownership; input bytes đúng MIME/codec; max size/duration/resolution;
module installed/model ready; no symlink/junction escape; version/hash binding;
FPS/timebase rational và cue/audio continuity; CPU/GPU resource budget.
Client không được override registry module/action để chạy process tùy ý.

Giới hạn DRAFT: JSON request <=256 KiB; 32 task/job; 8 input/job;
video <=500 MiB và <=1 giờ trước khi decode, giải mã còn có giới hạn frame/pixel/time.
Existing yt-dlp limit không thay kiểm tra Drive/local inputs. Agent và backend dùng cùng policy version.
Các giới hạn request/task/input được enforce trong API mới; video <=500 MiB, <=1 giờ,
dimensions <=4096 mỗi cạnh và FPS 1..60 được kiểm tra bằng ffprobe trước nhận input/thực thi.
Không tuyên bố đã enforce các giới hạn đó trong runtime legacy.

## Cache / retry

Cache key gồm input hashes, normalized config, module/model/profile versions và output role.
Không dùng tên file hoặc chỉ checksum output để nhận diện request.
Packet rerender giữ source/voice hash và ràng buộc audio timeline; đổi giọng là job khác.
File thành công chỉ register sau probe/hash/commit; staging file lỗi không thành output verified.
Manifest hash và attempt fencing ngăn hoàn tất stale; idempotency do PostgreSQL giữ.
