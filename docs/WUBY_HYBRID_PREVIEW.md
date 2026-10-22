# Wuby hybrid — bản thử và tích hợp Cấu hình 1

Mục tiêu: giữ nguyên video/âm thanh đã xử lý bởi **pipeline Wuby hiện hữu**
(OCR/che chữ, phụ đề Việt, giọng), chỉ đặt kết quả vào bố cục V7. Mẫu CLI 2 giây
dùng đầu ra của bộ Wuby V4; điều đó chưa chứng minh bot hiện hành chạy toàn bộ
bộ nguồn V4 trích xuất.
Chỉ Cấu hình 1 được bật bước đóng khung sau render; Cấu hình 2/3/4 không đổi.
Wuby V4 ở đây là phiên bản Wuby, không phải nút "Cấu hình 4" của bot Telegram.

## Luồng bot hiện tại

`Cấu hình 1 → OCR/che chữ + sub Việt + lồng tiếng hiện có → MP4 hoàn chỉnh →
khung V7 (chỉ hình và giữ audio) → Drive/Telegram`. Bật bằng
`presets.wuby.wuby_studio.hybrid_frame.enabled` hoặc cấu hình kênh Wuby tương ứng
trong `backend/channels_config.json`. Nút Cấu hình 1 nhận cùng cờ từ preset.
Các nhánh Cấu hình 2/3/4 trả lại MP4 sau render như trước. Nếu bước đóng khung
lỗi, bot báo lỗi và không gửi nhầm bản chưa đóng khung. Khi hybrid bật, lỗi kỹ
thuật ở bước OCR cũng dừng job thay vì âm thầm đi tiếp; vẫn cần kiểm tra thủ
công chữ còn sót. Không có bước đăng công khai.

Khi bot xử lý job, file trung gian nằm trong workspace và được dọn sau khi giao
thành công. Chế độ này không tạo sidecar/visual packet vì nguồn trung gian sẽ bị
xóa; muốn giữ report và ảnh QC thì chạy CLI độc lập dưới đây. Cần khởi động lại
bot lúc rảnh để nạp code và cấu hình mới, không khởi động lại giữa job.

## Cách dùng

Đầu vào phải là MP4 **đã xử lý hoàn chỉnh** từ Wuby V4. Lệnh mặc định chỉ in
kế hoạch, không render:

```powershell
python -m wuby_studio.hybrid --processed-video "C:\path\c4_output.mp4" --output "C:\path\wuby_hybrid.mp4" --title "Tiêu đề"
```

Sau khi kiểm tra đường dẫn/tiêu đề, thêm `--render` để xuất thử một file riêng.
Có thể chọn `--theme peach|mint|lavender`. Đường dẫn output không được trùng input.
Nếu nguồn đã có dải đen lớn, có thể thêm `--crop "0,0.22,1,0.56"` sau khi **xem
toàn bộ video** để chắc chắn không cắt mất chữ/nhân vật. Không tự crop theo ảnh tối.

Hybrid tự khớp kích thước vùng video theo tỷ lệ khung hình sau crop, trong giới
hạn 86% chiều rộng và 80% chiều cao khung;
âm thanh đầu vào được giữ nguyên. V7 không gọi OCR/TTS lần hai, không sinh lớp
phụ đề thứ hai. Renderer chấp nhận input đã burn chữ chỉ khi tắt OCR mới và
phụ đề mới; đầu vào vẫn cần người xem kiểm tra chữ cũ và giọng.

## Trạng thái kiểm chứng

- Unit config/CLI dry-run: 5/5 PASS trên Python local của Codex.
- AST parse `renderer.py` và `hybrid.py`: PASS.
- Kiểm tra nhánh input đã xử lý: passthrough khi không thêm phụ đề; bật phụ đề
  lần hai bị chặn (audio module được stub vì máy local thiếu dependency).
- Python local thiếu `soundfile`/`scipy` của môi trường Wuby. Đã render thử
  2 giây từ MP4 Wuby V4 với audio module stub ở chế độ preserve, chỉ xác nhận
  đường hình FFmpeg. Mẫu xem tại `examples/wuby_hybrid_preview_2s.mp4` và
  `examples/wuby_hybrid_preview_frame.jpg`. Crop dùng riêng cho mẫu này là
  `0,0.22,1,0.56`, không phải cấu hình mặc định cho mọi video.
- Đã nối sau renderer hiện hữu của bot cho Cấu hình 1, nhưng chưa chạy một job bot
  thật từ OCR/clone đến Drive/Telegram. Chưa kiểm thử clone mới từ Wuby V4, chưa nghiệm thu
  hình/giọng trên video người dùng mới. Demo giữ âm thanh sẵn có của đầu vào.
- Sau tích hợp: 11/11 unit tests (hybrid và channel profiles) PASS; `py_compile`
  bot, merger, hybrid, renderer PASS; chọn Cấu hình 2/3/4 không bật hybrid.
- `ffprobe` xác nhận preview cũ dài 2 giây, 1080×1920, có video và audio;
  đây không phải bài test end-to-end cho code mới.
- SHA-256 `EAD96D51C93CECDC7142019029C8AE8F11F7F66F935FC10BE500AFCCF41A24DD`
  là mốc trước khi bật hybrid Cấu hình 1; hash toàn file hiện đã đổi.

Rollback code renderer: `backups/wuby_hybrid_20260924/renderer.py`.
