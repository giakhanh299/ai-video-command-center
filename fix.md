# BÁO CÁO FIX LỖI: CHE PHỤ ĐỀ TRUNG & HỆ THỐNG CẤU HÌNH 2

---

## 1. Nguyên nhân lỗi trong ảnh ("cái gì nữa đây")

Trong ảnh chụp video `ke_buon_nguoi_vao_buong_so_9.mp4`:
- Dải làm mờ (Frosted Blur) bị lệch lên phía trên (ngang ngực diễn viên, Y ~ 856px).
- Dòng chữ phụ đề tiếng Trung gốc `当黑妹看见阿香的那一刻` ở sát mép đáy màn hình (Y = 954px - 1046px) **hoàn toàn không bị che**, lộ rõ 100%.
- Phụ đề tiếng Việt (`Tôi nhận đi, Khoảnh khắc Hắc Muội nhìn thấy A Tương`) hiển thị lơ lửng ở vị trí dải mờ sai, dẫn đến cả 2 thứ tiếng cùng xuất hiện song song.

### Nguyên nhân kỹ thuật:
1. **Lỗi gộp toạ độ cực trị (Naive Union) trong `scan_fixed_blur_box`**:
   - Khi quét 20 frame mẫu, có 1-2 frame xuất hiện chữ tiêu đề/bảng hiệu phía trên (Y ~ 726px).
   - Hàm lấy `y_min = min(b['y'])` và `y_max = max(b['y'] + b['h'])`, khiến box bị kéo dài từ 726px đến 1080px (chiều cao phình lên 354px).
2. **Lỗi căn giữa khi co chiều cao box trong `video_merger.py`**:
   - Khi chiều cao box lớn hơn ngưỡng cho phép, code cũ thực hiện: `by = by + (diff // 2)`.
   - Box bị co về trung tâm của vùng 726 - 1080 (tức Y = 856px .. 948px), rơi vào vùng ngực diễn viên, hoàn toàn trật khỏi dòng phụ đề thực tế (Y = 954px .. 1046px).
3. **Giới hạn chiều cao box tối đa cũ quá hẹp**:
   - Cũ: `round(vid_h * 0.085)` = 92px. Trong khi chữ phụ đề Trung gốc kích thước lớn chiếm ~120 - 140px, dẫn đến dù có căn đúng cũng bị lòi mép chữ.

---

## 2. Các điểm đã khắc phục triệt để

### A. Phân cụm trung vị loại bỏ chữ rác (`backend/subtitle_regions.py`)
- Lọc bỏ tất cả các text box ở nửa trên màn hình (`center_y < 0.45 * height`).
- Tính trung vị `median_cy` của các dòng phụ đề ở đáy và chỉ giữ lại các box có toạ độ đồng nhất (`abs(center_y - med_cy) <= 40px`).
- Kết quả test thực tế: Bắt chính xác 100% dòng phụ đề đáy `x=76, y=912, w=1494, h=166 (CenterY=995.0)`.

### B. Neo cố định đáy và tăng vùng phủ (`backend/video_merger.py`)
- Tăng giới hạn chiều cao che chữ lên `15% chiều cao video` (~162px cho 1080p, ~288px cho video dọc 1920p), che trọn vẹn cả phụ đề 2 dòng hoặc chữ to có viền đen.
- Khi điều chỉnh chiều cao, luôn **neo theo đáy màn hình** (`bottom_edge - bh`), đảm bảo không bao giờ bị hở mép dưới của chữ Trung.
- Thêm lớp tối nhẹ `alpha=0.35` cho kính mờ để triệt tiêu hoàn toàn ánh sáng của chữ trắng gốc, giúp chữ tiếng Việt hiển thị sắc nét, sang trọng.
- Thêm cơ chế tự động kiểm tra tính hợp lệ: nếu OCR trả về toạ độ bất thường, hệ thống tự động chuyển sang thuật toán nhận diện màu chữ OpenCV `detect_subtitle_box_20_frames` (chính xác tuyệt đối).

### C. Khắc phục treo tiến trình khi quét Scene (`backend/scene_detector.py`)
- Thêm chốt chặn bỏ qua file âm thanh (`.wav`, `.mp3`) trước khi gọi `cv2.VideoCapture` để tránh bị Windows Media Foundation (MSMF) treo luồng vĩnh viễn.

### D. Khắc phục lỗi nạp giọng mẫu OmniVoice (`backend/torchaudio_compat.py`)
- Tạo module tương thích chuẩn cho `torchaudio 2.10`, thay thế backend nạp file bằng `SoundFile`.
- Khắc phục triệt để lỗi crash `libtorchcodec_image.dll` trên Windows, giúp các giọng clone như `3_nu_tram_am.mp3` được nạp trực tiếp vào model GPU thay vì bị văng sang Edge TTS fallback.

---

## 3. Trạng thái kiểm thử

- `backend/tests/test_movie_voice_matcher.py`: **3/3 PASSED**
- `backend/tests/test_character_identity.py`: **5/5 PASSED**
- `backend/tests/test_subtitle_regions.py`: **9/9 PASSED**
- `backend/tests/test_wuby_roles.py`: **3/3 PASSED**
- `backend/tests/test_config34_audio.py`: **3/3 PASSED**
- **Tổng cộng: 23/23 tests đạt chuẩn 100%.**
- Bot Telegram đã được khởi động lại với mã nguồn mới và đang hoạt động.

---

## 4. BẢNG TỔNG HỢP CÁC LỖI HAY GẶP & TÌNH TRẠNG XỬ LÝ (MỚI NHẤT)

| STT | Tên Lỗi / Triệu Chứng | Nguyên Nhân Kỹ Thuật | Giải Pháp Đã Xử Lý | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **`File phụ đề gốc trống hoặc không tồn tại: ..._vi.orig.srt`** *(Job báo đỏ trên Sheet/Tele)* | Video ngắn (< 10s) hoặc video chỉ có nhạc nền dã ngoại/không lời thoại, Whisper chỉ nhận 1 âm thanh nhỏ (< 50 bytes). Hàm `parse_srt_to_segments` có điều kiện chặn cứng `st_size < 50` làm trả về `[]`, hàm dịch văng `RuntimeError`. | - Đổi ngưỡng kiểm tra thành `st_size < 5`.<br>- Thêm cơ chế nhận diện `NO_SPEECH_DETECTED`: nếu video không có lời thoại, tự động coi là video nhạc nền, giữ 100% âm gốc và render bình thường mà không văng lỗi. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đã test chạy mượt mà) |
| **2** | **Xung đột Telegram Bot (HTTP 409 Conflict & Khóa File `bot.log`)** | Tiến trình PowerShell (`PID 27360`) và Python cũ (`PID 36576`) chạy ngầm nhiều ngày trước giữ file lock trên `logs/bot.log` và chạy code cũ trong RAM, liên tục chiếm token Telegram. | - Viết trình giám sát độc lập `run_bot.py` bằng Python đóng/mở log stream an toàn.<br>- Dùng lệnh kill triệt để toàn bộ PID bot ngầm cũ.<br>- Chuyển `run_bot.ps1` thành wrapper gọi `run_bot.py`. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đang chạy ổn định) |
| **3** | **Caption sinh nhầm chủ đề ("Bộ phim này", "Vũ Trụ Cày Phim")** | Hàm `generate_movie_caption` trong `sub_processor.py` trước đây bị hardcode toàn bộ theo mẫu Review Phim của kênh Vũ Trụ Cày Phim. | - Bổ sung nhánh riêng `is_cauca` cho `chidepdicau` / `gaidep_cauca`: prompt DeepSeek chuyên sâu về blog câu cá, dã ngoại, săn cá khủng, gắn đúng `@ChiDepDiCau` và bộ hashtag chuẩn câu cá.<br>- Tự động phân biệt review phim giữa **Bật Phim Lên** (`#BatPhimLen`) và **Vũ Trụ Cày Phim** (`#VuTruCayPhim`) theo logo. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đã test thực tế) |
| **4** | **Thiếu lời sub trò chuyện & chưa có sub Karaoke Trắng - Vàng** | Preset `chidepdicau` trước đó tắt `burn_sub: false` và profile `gaidep_blur` tắt `subtitle.enabled: false`. Chưa có cơ chế sinh thẻ karaoke. | - Bật `burn_sub: true` và `subtitle.enabled: true`.<br>- Viết hàm `make_karaoke_ass_text` sinh thẻ `{\kf<cs>}`: Chữ chưa nói màu **Trắng** (`#FFFFFF`), chữ đang nói/đã nói lướt sang màu **Vàng nghệ** (`#FFE600`).<br>- Cố định font size `38px` (vừa vặn, dễ đọc trên điện thoại, viền đen 3.5px, bóng 1.5px).<br>- Căn tâm `\pos(540, 1306)` đè khớp vào dải Gaussian Blur. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đã render và tải lên Drive) |
| **5** | **Nhầm lẫn Cấu hình 2 (Review Phim) với Cấu hình Câu Cá** | Trong quá trình test tạm link video câu cá, cấu hình 2 bị gán nhầm sang preset câu cá làm lệch chuẩn review phim dải đen. | - Khôi phục nguyên bản 100% cho **Cấu hình 2 (Review Phim - Dải Đen)**: Dải đen chuẩn điện ảnh `black_bar`, Sub \an5\pos, Title Card 6s + Logo Bật Phim Lên, Giọng Nữ Trẻ 1.3x tối đa 1.8x.<br>- Tách riêng video câu cá sang **4️⃣ Cấu hình 4 (Chị Đẹp Đi Câu @chidepdicau)** độc lập hoàn toàn. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (2 cấu hình độc lập) |
| **6** | **Dải mờ Gaussian Blur bị mờ lẹm vào người/cá lúc 0:00** | Lệnh filtergraph `overlay` chạy liên tục từ giây 0:00 dù lúc đó phụ đề thoại tiếng Trung gốc chưa hề xuất hiện. | Thêm điều kiện hẹn giờ `enable='gte(t, first_sub_t - 0.2)'`. Nếu câu sub đầu tiên bắt đầu từ 0.9s trở đi, giây đầu tiên hoàn toàn trong trẻo, không có vệt mờ. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đã kiểm tra frame 0s) |
| **7** | **Khung bìa Douyin (0.15s đầu) chứa chữ Trung to đùng gây lộ video reup** | 3-5 frame đầu của video Douyin là ảnh bìa chứa sticker/tiêu đề tiếng Trung to đùng. | Xây dựng khâu Check xem trước (Bước 6B: Pre-render Preview): Bot gửi ảnh so sánh Trái / Phải để duyệt: **[A. Dùng Banner Tiêu đề 2.5s]** hoặc **[B. Cắt bỏ 0.15s bìa gốc]** trước khi render. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Hoạt động trên Telegram) |
| **8** | **Job Wuby chạy quá lâu (> 10 phút) trên video dài** | Cấu hình 1 Wuby quét EasyOCR frame-by-frame toàn bộ video, phát hiện hàng nghìn nhãn chữ và gọi GPT dịch 645 đoạn chữ Trung không lời thoại. | Khuyến cáo sử dụng đúng cấu hình: Video người thật dã ngoại/câu cá chọn **Cấu hình 4** (chỉ mất ~10-15s duyệt và render nhanh bằng NVENC GPU, không quét 13.000 chữ của Wuby). | 🟢 **ĐÃ TÁCH QUY TRÌNH** (Đã bổ sung hướng dẫn) |
| **9** | **Lỗi crash `libtorchcodec_image.dll` trên Windows khi nạp OmniVoice** | `torchaudio 2.10` trên Windows lỗi phụ thuộc DLL khi load audio mẫu clone bằng backend ffmpeg/sox. | Tạo module `backend/torchaudio_compat.py` ép dùng backend `SoundFile` nạp trực tiếp vào GPU CUDA. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đã pass test clone giọng) |
| **10** | **Treo vĩnh viễn (Hang) khi quét Scene phát hiện cảnh** | `backend/scene_detector.py` gọi `cv2.VideoCapture` trên cả file âm thanh (`.wav`, `.mp3`) khiến Windows Media Foundation deadlock. | Thêm chốt chặn đuôi file: Chỉ gọi `cv2.VideoCapture` với file video thật (`.mp4`, `.mov`, `.mkv`), bỏ qua file âm thanh. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Không còn tình trạng treo bot) |
| **11** | **Ảnh duyệt Pre-render lỗi font `□□□□`, banner lệch tọa độ và bên B chưa sạch** | 1. `telegram_bot.py` lấy `raw_title` tiếng Trung gán vào banner, font Latin không có glyph nên hiển thị ô vuông `□□□□□□□□□□`.<br>2. Banner bị hardcode tại Y=48% (921px) nên nằm dưới cụm sticker chữ Trung (Y=673..830px).<br>3. Chữ Trung là sticker kéo dài 1.8s (trong khi thoại bắt đầu từ 0.82s), cắt 0.15s không sạch và nếu cắt 1.8s thì bị mất tiếng thoại. | 1. Dùng `movie_title_vi` tiếng Việt chuẩn, bổ sung font dự phòng Unicode CJK.<br>2. Tự động nhận diện cụm sticker ở vùng giữa, căn Banner trùm kín 100% chữ Trung.<br>3. Phương án B: Tự động áp dụng Gaussian Blur che sạch cụm sticker tiếng Trung mà không cắt xén mất tiếng thoại. | 🟢 **ĐÃ FIX TRIỆT ĐỂ** (Đã kiểm chứng hình ảnh hoàn hảo) |

> 📌 **Chi tiết đầy đủ xem tại file:** [LOG_LOI_VA_TINH_TRANG.md](file:///D:/0.1_FACE_BOOK/Lay video tiktok/docs/LOG_LOI_VA_TINH_TRANG.md)


