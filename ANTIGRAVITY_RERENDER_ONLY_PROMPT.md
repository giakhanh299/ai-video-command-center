# LỆNH CHO ANTIGRAVITY — CHỈ RENDER LẠI WUBY

Bạn chỉ được vận hành pipeline Wuby hiện có. **Không sửa code, không sửa cấu hình, không refactor, không thay dependency và không thay kiến trúc.**

## Mục tiêu

Render lại toàn bộ video trong:

`G:\My Drive\Video titok Trinh\WUBYCHUA RENDER`

Kết quả review phải nằm trong:

`G:\My Drive\Video titok Trinh\Wuby Review`

Pipeline hiện đã được cấu hình:

- OCR quét 24 fps.
- Cửa sổ đè chữ bắt đầu sớm 0,15 giây và kết thúc muộn 0,15 giây, tổng mở rộng tối đa 0,3 giây.
- Không vượt điểm chuyển cảnh và không cho hai caption cùng vị trí chồng nhau.
- Nhân vật dùng `voice_samples\giongnucute.wav`.
- Người dẫn dùng `voice_samples\2_nu_tre_trung.mp3`.
- Video chỉ được đưa vào thư mục Review khi QC đạt.

## Cách chạy

Mở PowerShell và chạy đúng lệnh sau:

```powershell
Set-Location -LiteralPath 'D:\0.1_FACE_BOOK\Lay video tiktok'
python '.\workspace\render_all_wuby_batch.py'
```

Không thêm `--publish`. Không chép thủ công video sang `Đã Render`.

## Quy tắc bắt buộc

1. Không chỉnh sửa bất kỳ file `.py`, `.json`, `.env`, model, voice sample hoặc test nào.
2. Không đổi tên thư mục nguồn/đích và không xóa video nguồn.
3. Không bỏ qua OCR preflight hoặc QC gate.
4. Không tiếp tục bằng cách thủ công nếu một job báo lỗi.
5. Video QC thất bại phải giữ nguyên trong quarantine; không được chép sang Review hoặc `Đã Render`.
6. Không chạy nhiều batch Wuby đồng thời.
7. Không dùng lại các video cũ trong `Đã Render` để giả làm kết quả mới.

## Kiểm tra sau render

Với từng video, đọc các file trong `Wuby Review`:

- `*_qc_report.json`
- `*_voice_report.json`
- `*_ocr_matched.json`
- `*_contact_sheet.jpg`

Chỉ ghi nhận đạt khi:

- `passed = true` và không có `errors`.
- Thời lượng, độ phân giải và fps khớp video nguồn.
- `overlap_count = 0` và `truncated_cues = 0`.
- Không có `UNTRANSLATED_OCR`, `LINGERING_CHINESE`, `BLANK_WIPEOUT` hoặc `LAUGHTER_ASSIGNED_TO_OCR`.
- Mỗi track có `lead_extension_sec <= 0.15`, `tail_extension_sec <= 0.15`, tổng không quá `0.30` giây.
- Nếu có vai `character`, audio phải là `giongnucute.wav`.
- Nếu có vai `narrator`, audio phải là `2_nu_tre_trung.mp3`.

## Báo cáo cuối

Chỉ báo cáo:

- Tổng số video nguồn.
- Số video PASS và FAIL.
- Tên file đầu ra của từng video PASS.
- Với video FAIL: tên video, thông báo lỗi và đường dẫn báo cáo/quarantine.
- Xác nhận rõ: `Không sửa code hoặc kiến trúc`.

Nếu gặp lỗi, dừng và báo lại nguyên văn lỗi. Không tự sửa pipeline.
