# Báo Cáo Bàn Giao Frontend — AI Video Command Center

**Vai trò:** Frontend Lead (Antigravity)  
**Ngày:** 2026-10-22  
**Hợp đồng API:** `0.1.0-draft` · **Registry Schema:** `1.0.0`  
**Ngôn ngữ giao diện & báo cáo:** Tiếng Việt  

---

## 1. Tổng Quan Kiến Trúc & Công Nghệ

Tuân thủ nguyên tắc bảo toàn hệ thống và stack hiện có:
- **Ngôn ngữ & Cấu trúc:** HTML5 Semantic + Vanilla JavaScript (ES2022) + Vanilla CSS hiện đại. Không tự ý cài đặt thêm framework nặng (React/Vue/Next/Tailwind).
- **Thiết kế Thẩm mỹ:** Dark mode chuyên nghiệp (`#0c0f14`), màu nhấn xanh ngọc (`#2dd4bf`), độ tương phản cao, typography hiện đại (`Inter` & `JetBrains Mono`).
- **Phân tách Trạng thái:**
  - `MockApiClient`: Đọc dữ liệu mô phỏng đồng bộ registry 1.0.0, phục vụ phát triển giao diện độc lập.
  - `RealApiClient`: Gọi trực tiếp FastAPI `/api/v1` với `Authorization: Bearer <token>`, `Idempotency-Key` (UUIDv4) và xử lý `expected_version` fencing.
  - **Không tự động chuyển sang mock khi API lỗi**: Đảm bảo hiển thị đúng bản chất lỗi kỹ thuật (401, 404, 409, 422, 503, network error).
- **Bảo tồn mã cũ:** Không xóa hoặc sửa đổi các luồng cũ tại `index.html` (Tải video) và `reel.html` (Đăng Reel Facebook). Đã bổ sung liên kết hai chiều mượt mà giữa các trang.

---

## 2. Danh Sách 7 Màn Hình Đã Triển Khai

| STT | Màn hình | Tính năng chính | Trạng thái |
|---|---|---|---|
| 1 | **Tổng quan (Overview)** | 4 khối thẻ thống kê (Đang chạy, Đang chờ, Cần duyệt, Cần xử lý); Danh sách Agent trực tuyến; Danh sách job cần duyệt/xử lý nhanh; Bảng job gần nhất. | ĐÃ HOÀN TẤT |
| 2 | **Dự án (Projects)** | Danh sách dự án kèm phiên bản (v1, v2...); Nút "Tạo dự án mới" có modal nhập tên và sinh `Idempotency-Key`. | ĐÃ HOÀN TẤT |
| 3 | **Chi tiết Dự án (Project Detail)** | Thanh lọc job theo trạng thái (`queued`, `running`, `needs_review`, `needs_attention`, `failed`, `cancelled`); Đổi tên dự án có kiểm tra `expected_version`. | ĐÃ HOÀN TẤT |
| 4 | **Tạo Job Render (New Job)** | Chọn dự án; Nhập UUID File input đã verified; Danh sách preset lấy từ Registry 1.0.0; Tự động kích hoạt form override theo schema (`width`/`height` cho `basic_render`); Khóa nút gửi khi preset chưa sẵn sàng. | ĐÃ HOÀN TẤT |
| 5 | **Chi tiết Job & Pipeline (Job Detail)** | Chi tiết từng task (probe, render.basic...), số lần thử (attempt), trạng thái từng bước; Nút Huỷ job (kèm receipt confirmation); Nút Thử lại (retry budget); Bảng log sự kiện có lọc theo cấp độ (Info, Warning, Error). | ĐÃ HOÀN TẤT |
| 6 | **Duyệt Video & QC (Job Review)** | Trạng thái `needs_review` hiển thị cảnh báo nghiệp vụ rõ ràng; Video player hỗ trợ `playback_url` hoặc fallback stream HTTP 206 Range qua API; Thẻ thông số QC (kích thước, FPS, codec, audio, frames, thời lượng). Khóa visual rerender kèm hướng dẫn. | ĐÃ HOÀN TẤT |
| 7 | **Module Registry & Agent Status** | Bảng tra cứu toàn bộ module đã đăng ký (tài nguyên CPU/GPU, phiên bản, action); Danh sách máy Agent thực thi, trạng thái trực tuyến/ngoại tuyến, capabilities và heartbeat. | ĐÃ HOÀN TẤT |

---

## 3. Đối Chiếu Hợp Đồng API (OpenAPI vs Frontend)

Qua việc đối chiếu chi tiết với `docs/openapi.command-center.json` do Codex xây dựng, Frontend ghi nhận các điểm sau:

### 3.1. Các điểm đã khớp hoàn toàn:
1. **Model Dự án**: CRUD `/api/v1/projects` khớp chuẩn DTO, có `expected_version` cho PATCH và DELETE (archive).
2. **Model Job & Lifecycle**: Nhận diện đúng các trạng thái `queued -> running -> cancelling -> cancelled / needs_attention / needs_review`.
3. **Registry & Presets**: Đã đồng bộ với `command_center/registry.py` (Registry version `1.0.0`, Module version `1.0.0`).
4. **Fencing & Idempotency**: Mọi request đột biến đều gửi kèm header `Idempotency-Key` (UUIDv4) và xử lý lỗi xung đột `409 CONFLICT`.

### 3.2. Mismatch và Đề xuất cho Backend (Codex):
1. **Thiếu endpoint `GET /api/v1/jobs` toàn cục**:
   - *Hiện trạng:* Backend chỉ có `GET /api/v1/projects/{pid}/jobs`. Để hiển thị job gần đây trên màn hình Tổng quan, Frontend phải duyệt qua danh sách dự án rồi query song song từng dự án.
   - *Đề xuất:* Bổ sung endpoint `GET /api/v1/jobs?status=...&cursor=...&limit=...` trong contract revision tiếp theo.
2. **Override Schema của `basic_render`**:
   - *Hiện trạng:* Schema của `basic_render` chỉ nhận `{ "width": int, "height": int }`. Gửi trường khác (như `title`) sẽ bị backend trả về lỗi `422 VALIDATION_ERROR`.
   - *Đã xử lý:* Frontend đã xây dựng form sinh động theo schema, chỉ gửi đúng các thuộc tính được khai báo trong `override_schema`.
3. **Upload tệp nhị phân từ trình duyệt**:
   - *Hiện trạng:* `POST /api/v1/jobs` nhận `input_refs` là UUID của file đã đăng ký. Chưa có endpoint HTTP để người dùng kéo-thả tệp video từ trình duyệt lên backend.
   - *Đề xuất:* Xây dựng endpoint upload (multipart hoặc presigned URL) cho đợt tiếp theo.
4. **Streaming Video (Playback)**:
   - *Hiện trạng:* `playback_url = null` do chưa có Object Storage đám mây.
   - *Đã xử lý:* Frontend bổ sung cơ chế fallback stream trực tiếp qua endpoint `/api/v1/files/{file_id}/content` (đã kiểm chứng hỗ trợ HTTP 206 Range trong smoke test của Codex).

---

## 4. Hướng Dẫn Chạy & Thử Nghiệm

### Cách 1: Chạy trực tiếp trong trình duyệt (Chế độ Mô phỏng & API Thật)
1. Mở file HTML trong trình duyệt bất kỳ (Chrome, Edge, Firefox):
   ```
   file:///D:/0.1_FACE_BOOK/Lay%20video%20tiktok/frontend/command-center.html
   ```
2. Mặc định trang sẽ mở ở chế độ **Mô phỏng (Mock)** với toàn bộ fixture chuẩn registry 1.0.0.
3. Để kết nối API backend thật:
   - Nhấn nút **"Chế độ: Mô phỏng"** ở góc phải trên cùng của thanh header (hoặc nút **"Cấu hình API"** trên banner).
   - Chọn mục **"API thật (/api/v1)"**.
   - Nhập URL API (mặc định: `http://127.0.0.1:8016/api/v1`).
   - Nhập `Owner Bearer Token` (lấy từ `workspace/command_center_dev/credentials.local.json`).
   - Nhấn **"Kiểm tra kết nối"** -> Nhấn **"Lưu và Áp dụng"**.

### Cách 2: Chạy qua Live Server hoặc Dev Proxy
Khi chạy qua HTTP server cục bộ tại thư mục `frontend`:
```powershell
# Chạy HTTP server đơn giản tại cổng 8000
python -m http.server 8000 -d "D:\0.1_FACE_BOOK\Lay video tiktok\frontend"
```
Truy cập: `http://localhost:8000/command-center.html`.

---

## 5. Danh Sách Tệp Đã Thay Đổi & Tạo Mới

1. `frontend/command-center.html` (Tạo mới): Trang chính SPA điều khiển toàn bộ pipeline AI video.
2. `frontend/cc-app.js` (Tạo mới): Logic ứng dụng SPA, quản lý điều hướng 7 màn hình, xử lý modal, kiểm soát lỗi, phím tắt và ARIA accessibility.
3. `frontend/cc-api.js` (Tạo mới): Client API phân tách rõ MockApiClient và RealApiClient, tích hợp Bearer auth, UUIDv4 Idempotency-Key và đồng bộ registry 1.0.0.
4. `frontend/cc-style.css` (Tạo mới): Hệ thống design tokens, bố cục CSS Grid/Flexbox, dark theme, trạng thái chip màu, responsive layout cho mobile/tablet/desktop.
5. `frontend/index.html` (Cập nhật): Bổ sung liên kết điều hướng sang Command Center mà không sửa logic cũ.
6. `docs/reviews/ROUND_1.md` (Cập nhật): Bổ sung phản biện thiết kế của Frontend Lead.
7. `docs/reviews/ROUND_2.md` (Cập nhật): Bổ sung nhận xét tích hợp API thật và giải quyết mismatch mock version.
8. `docs/reviews/ROUND_3.md` (Cập nhật): Bổ sung bằng chứng kiểm thử QA trong trình duyệt.
9. `docs/CLAUDE_HANDOFF.md` (Cập nhật): Phản hồi đầy đủ 5 câu hỏi của Codex về DTO, thuật ngữ trạng thái, cancel protocol và playback.
10. `docs/FRONTEND_INTEGRATION_REPORT.md` (Tạo mới): Tài liệu tổng kết bàn giao chi tiết này.

---

## 6. Kết Quả Nghiệm Thu (Evidence)

- **Trình duyệt tự động (Browser Subagent):** Đã mở và kiểm thử toàn bộ các màn hình, không phát hiện lỗi console nào (`0 console errors`).
- **File ghi hình phiên làm việc:** `verify_command_center_ui_1792633558621.webp`.
- **Ảnh chụp màn hình nghiệm thu:**
  - `command_center_overview_1792633569082.png` (Tổng quan)
  - `command_center_projects_1792633577087.png` (Danh sách dự án)
  - `command_center_create_job_1792633583822.png` (Form tạo job theo schema)
  - `command_center_modules_1792633638727.png` (Module registry 1.0.0)
  - `command_center_agents_1792633657189.png` (Agent status)
