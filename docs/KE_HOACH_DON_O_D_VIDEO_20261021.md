# Kế hoạch dọn ổ D cho sản xuất video

Ngày kiểm kê: 21/10/2026. Đây là kế hoạch; chưa xóa, chuyển thư mục hay tắt tiến trình.

## Hiện trạng đã kiểm tra

Ổ D đang dùng khoảng 332,6 GiB, còn khoảng 44,2 GiB. Kích thước thư mục dưới đây là tổng kích thước logic của file, bỏ qua junction/reparse point; chưa trừ hardlink hoặc xác minh trùng bằng hash. Vì vậy không cộng các con số thành dung lượng chắc chắn thu hồi được.

| Vị trí | Dung lượng | Nhận xét |
|---|---:|---|
| `D:\0.1_FACE_BOOK\Lay video tiktok` | 104,27 GiB | Code, cache, workspace và kết quả đang nằm chung |
| `D:\0.1_FACE_BOOK\Video Control` | 91,32 GiB | Gần hết dung lượng ở `motions-studio-main\motions-studio-main\.local` (89,67 GiB); cần phân loại tiếp |
| `D:\0.1_FACE_BOOK\DUNG_CHUNG\MODELS\HF_CACHE` | 29,69 GiB | Model dùng chung, phải xác minh tham chiếu trước khi bỏ revision |
| `D:\CLONE_Lay_video_tiktok` | 16,52 GiB | Có 8,38 GiB audio_stems; chưa xác minh bản clone còn được gọi không |
| `D:\0.1_FACE_BOOK` | 16,20 GiB | Kho video chiếm khoảng 15,78 GiB; đang nối với đồng bộ Drive/Sheet |
| `D:\02_CONG_CU\youtube-reup-pipeline` | 13,04 GiB | Có môi trường Python và credentials đang được dự án khác tham chiếu |
| `D:\02_CONG_CU\youtube-Thread` | 12,17 GiB | Có scheduler đang chạy, không coi là thư mục bỏ hoang |

Trong Douyin:

- `cache\audio_stems`: 34,18 GiB.
- `backend\cache\audio_stems`: 30,44 GiB.
- `workspace`: 30,35 GiB, gồm `douyin_render_jobs` 7,72 GiB và nhiều dữ liệu trung gian khác.
- `recycle`: 4,98 GiB. Đây là thư mục dự án, không mặc định là rác có thể xóa toàn bộ.

Hai cache tách âm tổng khoảng 64,62 GiB. Chúng phát sinh ở hai working directory khác nhau; chưa chứng minh từng file trùng nhau.

Các đường dẫn `D:\0.1_FACE_BOOK\Lay video tiktok` và `D:\0.1_FACE_BOOK\Lay video tiktok` đều trỏ tới `D:\0.1_FACE_BOOK\Lay video tiktok`. Không tính chúng là ba bản vật lý. Nhiều launcher đang sử dụng các đường dẫn liên kết này.

## Thứ tự thực hiện

### 1. Chốt sơ đồ luồng và điểm khởi động

Lập bảng: launcher/task khởi động → interpreter → thư mục code thật → nơi nhận video → khóa GPU → workspace → kết quả → Drive/Sheet. Đối chiếu Scheduled Tasks, Startup, registry Run và tiến trình thực tế. Ghi rõ luồng Douyin/Telegram, Facebook, Video Control, Review Sách và các scheduler khác. Không chạy lại scheduler trong lúc kiểm kê.

Đầu ra: sơ đồ các luồng đang dùng, danh sách tiến trình/khóa và danh sách đường dẫn cần giữ tương thích.

### 2. Dọn dữ liệu trung gian có bằng chứng

Đọc SQLite, receipt và log để gắn mỗi file với job. Chỉ dọn file tạm của job đã kết thúc, đã xác minh PID/create_time và tiến trình con. Với job hoàn tất, kiểm tra MP4 đích có thật, ffprobe và hash trước khi loại WAV/MP4 trung gian. Với FAILED, giữ log, metadata và SRT cần sửa. Job RUNNING, UNKNOWN và đầu ra chưa kiểm chứng phải giữ.

Lập manifest dry-run có đường dẫn, kích thước, job, trạng thái, lý do và hành động. Không xóa cả cây cache theo tuổi. Bản sao trùng chỉ được loại sau khi so hash và xác nhận không còn tham chiếu.

Ưu tiên kiểm tra hai audio_stems và workspace. Đây là vùng ứng viên, không phải cam kết xóa được toàn bộ 64,62 GiB cache hay 30,35 GiB workspace.

### 3. Chuẩn hóa một đường dẫn cache tuyệt đối

Dùng một cache tách âm tại `D:\0.1_FACE_BOOK\Lay video tiktok\cache\audio_stems`, cấu hình tuyệt đối cho Telegram, CLI, renderer và lượt thử. Dùng khóa và ghi file nguyên tử khi tạo cache. Cache cần gắn hash nguồn/model/settings, có kiểm chứng nội dung và không tái sử dụng bản chưa hoàn tất.

Đối chiếu hai cache hiện có, chuyển tham chiếu trước rồi mới loại bản dư. Không di chuyển code hoặc môi trường Python đang chạy chỉ để đổi tên thư mục.

### 4. Gom cấu trúc theo chức năng

- `D:\02_CONG_CU\DUONG_DAN_CU\02_video_ai`: cửa vào cho các dự án qua các liên kết hiện có.
- `D:\0.1_FACE_BOOK\Lay video tiktok`: code và cấu hình Douyin chính thức.
- `D:\0.1_FACE_BOOK\videos_upload\<kênh>`: kho media theo vòng đời, dùng thống nhất cho luồng hiện hành.
- `D:\0.1_FACE_BOOK\DUNG_CHUNG\MODELS\HF_CACHE`: model dùng chung; ghi rõ dự án nào dùng model/revision nào.
- Đề xuất `D:\99_LUU_TRU_VIDEO`: dự án cũ và snapshot đã xác nhận ngừng dùng. Chỉ chuyển sau khi đã sửa launcher và có phương án quay lại.

Giữ nguyên video gốc, video đang chờ duyệt, mẫu giọng, logo, token, khóa GPU và sổ theo dõi chống trùng. SRT/JSON phục vụ kiểm chứng đặt trong thư mục metadata/job, không để tràn cạnh video duyệt.

### 5. Dọn Video Control và bản clone

Phân tích `.local` 89,67 GiB thành model, environment, cache, dữ liệu dự án, downloads và renders. Kiểm tra riêng bản clone Douyin; không xóa vì tên có chữ CLONE. Model dùng chung chỉ được gom sau khi kiểm tra cấu hình loader; môi trường ảo có đường dẫn tuyệt đối không di chuyển tùy tiện.

### 6. Ngăn tái phát và nghiệm thu

Sau mỗi job, hook cleanup bảo toàn dữ liệu gốc/đích và chỉ dọn sau khi worker/encoder đã đóng. Đề xuất log xoay vòng giữ 14–30 ngày; dữ liệu sửa lỗi giữ lâu hơn và cleanup theo trạng thái. Khi ổ còn dưới 40 GiB, ngừng nhận thêm việc tải/render mới cho tới khi đủ chỗ; không ngắt job đang ghi file.

Nghiệm thu: pytest cho thay đổi cleanup/path, một video thử đi đủ luồng, kiểm tra âm thanh/phụ đề/receipt/hash, đường dẫn Drive/Sheet đúng và không có worker GPU trùng. Kiểm tra lại khởi động tự động trong cửa sổ bảo trì. Báo dung lượng trước/sau và manifest file thực sự đã loại.

## Mục tiêu và giới hạn

Ưu tiên đưa dung lượng trống về trên 80 GiB nếu các file đủ điều kiện, sau đó giữ mốc dự phòng phù hợp. Chỉ chốt số GiB thu hồi sau dry-run và xác minh từng nhóm. Di chuyển dữ liệu sang thư mục khác trên cùng ổ D chỉ làm gọn cấu trúc, không giải phóng chỗ; nén snapshot hoặc loại dữ liệu đã xác minh mới giảm dung lượng.

Tài liệu đi kèm: `outputs\d_drive_cleanup_inventory_20261021.json` và `outputs\d_drive_cleanup_detail_20261021.json`.
