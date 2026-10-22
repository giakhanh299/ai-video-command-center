# Lệnh sửa batch render Wuby

Hãy làm việc trực tiếp trong dự án:

`D:\0.1_FACE_BOOK\Lay video tiktok`

Mục tiêu: sửa pipeline Wuby để video chỉ được đưa vào
`G:\My Drive\Video titok Trinh\Đã Render\Wuby` khi chữ trên hình, phụ đề Việt,
giọng đọc và timeline đã được kiểm tra. Tự triển khai và kiểm thử đến khi đạt; ghi lại
mọi thay đổi và bằng chứng. Không xóa video nguồn hoặc ghi đè video đã render lỗi.

## Việc phải làm ngay

1. Xác định tiến trình `workspace\render_all_wuby_batch.py` đang chạy. Dừng đúng tiến
   trình batch đó và các tiến trình con của nó trước khi sửa. Không dừng bot Telegram,
   scheduler hoặc dịch vụ khác. Ghi PID và thời điểm dừng vào báo cáo.
2. Không tiếp tục copy sản phẩm mới vào thư mục `Đã Render\Wuby` cho tới khi QC mới đạt.
3. Giữ nguyên các file lỗi hiện tại để đối chiếu; không xóa hoặc đổi tên nếu chưa tạo
   bản sao lưu/báo cáo rõ ràng.

## Lỗi đã xác nhận

Đã đối chiếu video nguồn trong `WUBYCHUA RENDER` và video đầu ra:

- `tap_1.mp4` / nguồn `7312744725788822793.mp4`:
  chữ Trung giải thích tình huống bị xóa nhưng không có bản dịch Việt thay thế;
  vẫn sót chữ Trung màu vàng khoảng giây 6. ASS mới chỉ có sự kiện tiêu đề `TẬP 1`.
- `tieng_cuoi_bi_an.mp4` / nguồn `7337606983551388937.mp4`:
  SRT chỉ có `Ha, ha` và `ha, ha, haha` do Whisper nhận tiếng cười. Hệ thống gán
  `Ha, ha` lên một vùng chữ Trung có nội dung khác ở khoảng 2,79–4,33 giây;
  các dòng chữ giải thích trên đầu bị xóa mà không được dịch.
- Thời lượng không bị cắt: hai cặp gốc/render lần lượt dài 23,5 giây và 15,625 giây,
  đều 24 fps, 1080x1920. Lỗi nằm ở nội dung, OCR/translation/overlay và luồng TTS.

Bằng chứng hình ảnh và thông số nằm tại:

`C:\Users\w\Documents\Codex\2026-09-26\d-youtube-reviewsach\outputs\wuby_review_20260930`

Nhật ký bàn giao nằm tại:

`D:\02_CONG_CU\99Tool A Can\fanpage-bitbrowser-poster\NHAT_KY_HO_TRO_ANTIGRAVITY.txt`

## Nguyên nhân trong code cần xử lý

- `workspace\render_all_wuby_batch.py` là luồng riêng và đang bỏ qua pipeline chuẩn.
- Script chỉ lấy nội dung từ Whisper/SRT. Chữ Trung chỉ xuất hiện trên hình không được
  dịch độc lập, nhưng `clean_video_ocr_backgrounds` vẫn xóa OCR track có box.
- `match_ocr_events_with_subtitles` đang gán câu theo độ gần thời gian; chưa xác minh
  nội dung OCR và lời nghe có cùng vai trò. Vì vậy tiếng cười có thể bị dùng làm bản
  dịch của chữ mô tả.
- ASS chỉ vẽ track có `vi_text`; kết quả là có thể xóa chữ mà không vẽ chữ thay thế.
- Batch tự tổng hợp mọi câu bằng `giongnucute.wav`, bỏ qua `generate_dubbed_audio`
  và `wuby_roles.render_roles`.
- Batch bắt lỗi TTS từng câu rồi vẫn render; nó chép mẫu âm thanh trực tiếp vào mảng,
  có thể cắt hoặc ghi đè câu dài và vẫn báo thành công.
- Batch copy thẳng đầu ra sang Drive, chưa có cổng QC bắt buộc.

## Hành vi bắt buộc sau khi sửa

### 1. OCR và dịch chữ trên hình

- Tách rõ hai nguồn nội dung:
  - lời nghe được từ audio/Whisper;
  - chữ Trung nhìn thấy trên hình từ OCR.
- OCR track có chữ Trung mang nghĩa phải được dịch riêng sang tiếng Việt khi không có
  câu audio tương ứng.
- Chỉ xóa một OCR track khi đã có một trong các phương án thay thế hợp lệ:
  bản dịch Việt đã kiểm tra, hoặc quy tắc rõ ràng xác định đó là watermark/trang trí
  cần xóa. Không được xóa chữ nội dung rồi để trống.
- Không gán tiếng cười, tiếng đệm, âm thanh nền hoặc Whisper hallucination vào OCR
  text khác nội dung chỉ vì gần nhau về thời gian.
- Giữ OCR overlay theo đúng vị trí và thời gian của chữ gốc; chữ Việt phải nằm gọn,
  dễ đọc, không che nhân vật quá mức và không để sót chữ Trung.

### 2. Hai giọng Wuby đúng yêu cầu

- Lời nhân vật: `voice_samples\giongnucute.wav`.
- Người dẫn chương trình/lời dẫn: `voice_samples\2_nu_tre_trung.mp3`.
- Cấu hình narrator phải trỏ tới `omni_nu_tre`, không phải `omni_nu_tram`.
- Batch phải đi qua cùng luồng phân vai và tổng hợp chuẩn đang dùng trong
  `generate_dubbed_audio` / `wuby_roles`; không tự dựng một luồng TTS khác.
- Không fallback sang Edge hoặc giọng khác. Nếu clone/role classification/TTS thất bại,
  đánh dấu job failed/needs review và không xuất bản video.
- Không cắt audio im lặng, không chồng câu và không nuốt câu. Cần báo cáo theo từng cue.

### 3. Cổng QC trước khi copy sang Drive

Trước khi copy video vào `Đã Render\Wuby`, bắt buộc kiểm tra:

- video mở được, đủ thời lượng, fps và kích thước hợp lệ;
- số cue dự kiến so với cue đã vẽ/đọc;
- không còn chữ Trung nội dung trong các frame kiểm tra, ngoại trừ watermark được cho phép;
- mọi OCR track bị xóa đều có lý do và trạng thái thay thế;
- không có track nội dung bị xóa mà `vi_text` rỗng;
- không gán hallucination/tiếng cười vào chữ OCR khác nội dung;
- voice report xác nhận từng vai dùng đúng reference audio;
- không có cue TTS lỗi, overlap hoặc truncated cue;
- tạo contact sheet/frame audit theo các mốc và lưu JSON report cạnh video.

Nếu bất kỳ kiểm tra nào không đạt: giữ sản phẩm trong thư mục review/quarantine,
không copy sang `Đã Render\Wuby`, ghi lý do rõ ràng và tiếp tục job tiếp theo an toàn.

## Cách triển khai mong muốn

- Thu gọn `render_all_wuby_batch.py` thành bộ điều phối gọi pipeline chuẩn; không duy trì
  bản sao logic OCR/TTS riêng.
- Bảo vệ dữ liệu và thay đổi hiện có của người dùng. Không sửa lan sang cấu hình 2/3/4.
- Không đưa secrets, API key, cookie hoặc token vào log/test/report.
- Tạo test hồi quy có dữ liệu mô phỏng cho:
  1. OCR text không có speech vẫn được dịch/vẽ trước khi xóa;
  2. tiếng cười không được gán vào OCR text khác;
  3. track thiếu bản dịch không bị xóa và job không pass QC;
  4. hai vai dùng đúng hai file reference theo thứ tự timeline;
  5. TTS cue lỗi khiến job fail và không copy sang Drive;
  6. QC pass mới cho phép publish.

## Kiểm thử thực tế bắt buộc

Sau unit test, render lại bản thử nghiệm của chính hai nguồn:

- `G:\My Drive\Video titok Trinh\WUBYCHUA RENDER\7312744725788822793.mp4`
- `G:\My Drive\Video titok Trinh\WUBYCHUA RENDER\7337606983551388937.mp4`

Xuất thử vào thư mục review mới, không ghi đè file hiện có. Kiểm tra khung hình trước/sau
ở tối thiểu các mốc 1, 3, 6, 10 giây; nghe toàn bộ audio; đối chiếu SRT/ASS, OCR report,
role report và voice report. Chỉ khởi động lại batch sau khi hai mẫu này đạt QC.

## Báo cáo hoàn tất

Khi xong, ghi rõ:

- PID batch đã dừng và batch mới đã/ chưa khởi động lại;
- danh sách file đã sửa;
- nguyên nhân cuối cùng;
- test đã chạy và kết quả;
- đường dẫn hai video thử, contact sheet và JSON QC;
- giới hạn còn lại nếu có;
- cập nhật `NHAT_KY_HO_TRO_ANTIGRAVITY.txt` bằng kết quả thực tế.

Không tuyên bố “đạt 100%” chỉ dựa trên unit test. Cần bằng chứng render và nghe thực tế.
