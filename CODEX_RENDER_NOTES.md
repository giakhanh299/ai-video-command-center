# Ghi chú đọc dự án render TikTok — Codex, 16/10/2026

Phạm vi: đọc source/config và tài liệu hiện có, chưa chạy render hay thay preset. Cấu hình trên đĩa không chứng minh tiến trình đang chạy đã nạp bản đó.

## Kết luận về hai cấu hình phim

| Lựa chọn | Key preset | Workflow thật trong JSON | Kiểu hình/âm thanh | Đầu ra tương đối trong cấu hình |
|---|---|---|---|---|
| Cấu hình 1 Wuby | wuby | wuby | Overlay trong video, clone Wuby, xử lý giữ nền/5.1 | Đã Render/Wuby |
| Cấu hình 2 Review Phim | cauhinh2 | film_review_black | Dải đen, subtitle Việt, nu_tre tốc độ 1.3, bg_volume 0.10 | Đã Render/Review_Phim |
| Cấu hình 3 Clone Phim | cauhinh3 | movie_clone | Che vùng subtitle; 1 giọng hoaimy tốc độ 1.3; nền 0.70, TTS gain 1.15 | Đã Render/Clone_Phim |
| Cấu hình 4 trên nút bot | chidepdicau | gaidep_cauca | gaidep_blur, preset JSON hiện tts_enabled=true, omni_nu_cute tốc độ 1.45, nền 0.30 | Đã Render/Chi_Dep_Di_Cau |
| Preset nhãn Vũ Trụ Phim | vu_tru_phim | film_review_black | Nhánh review dải đen, omni_nam_review tốc độ 1.3, logo/cover riêng | Đã Render/Vu_Tru_Phim |

Hai cấu hình PHIM hiện hữu cần phân biệt là cauhinh2 (Review Phim) và cauhinh3 (Clone Phim). vu_tru_phim là preset branding của film_review_black, không phải bằng chứng nó thực hiện movie_clone. Chưa có căn cứ tự gán K2 dùng loại nào, K5 dùng loại nào chỉ từ tên kênh; phải đối chiếu manifest các job và yêu cầu hiện có trước khi nối adapter.

## Các chỗ dễ gọi nhầm

1. README_CLONE_PHIM_F0.md và docs/MOVIE_CLONE_PATCH_TEST_REPORT.md nói bot chỉ có Wuby + Clone phim, loại bỏ cấu hình 3/4. Source bot hiện lại có bốn nút và JSON vẫn có các preset đó. Không dùng README lịch sử làm kết luận cấu hình hiện tại.
2. Key JSON `cauhinh4` là một preset Wuby cũ (wuby_overlay, Clone_Phim_51_Smart). Nhưng handle_video_download khi nhận override_workflow=cauhinh4 lại đổi key thành `chidepdicau`. Gọi trực tiếp get_channel_config('cauhinh4') khác đường đi override qua bot. Adapter K8 nên phân biệt key `chidepdicau`, không suy rằng mọi key cauhinh4 giống nhau.
3. Nút bot mô tả cấu hình Chị Đẹp giữ âm gốc, không AI thuyết minh, nhưng JSON hiện tts_enabled=true/voice omni_nu_cute. Đây là mâu thuẫn cần kiểm tra bằng config đã resolve và render thật, chưa thể tuyên bố âm thanh thực tế giữ nguyên.
4. README phim còn mô tả F0 đa giọng; preset cauhinh3 hiện movie_voice_match.enabled=false, ghi chú 1 giọng nữ suốt phim. F0 matching cũng không phải xác minh danh tính người nói.
5. Preset/label registry trong fanpage-control-center không có nghĩa adapter đã gọi đúng các engine này. Phải kiểm chứng entrypoint, snapshot config và đầu ra.

## Đường gọi và trách nhiệm file

- backend/channels_config.json: default, workflows, render_profiles, presets, channels; không ghi đè bằng config mẫu.
- backend/channel_manager.py::get_channel_config: default -> workflow settings -> render profile -> channel/preset -> hashtag presets -> inline overrides. Đọc config resolved cho từng job, không chỉ nhìn tên preset.
- backend/telegram_bot.py::handle_video_download: chọn override, download, xử lý thoại/subtitle/preflight, render; có side effects Telegram/Sheets và kiểm tra preview. Không gọi cả bot như hàm render sạch khi triển khai adapter headless.
- backend/video_merger.py cùng sub_processor, subtitle_regions, audio_processor, dialogue_replace: các bước media/audio cần tách thành adapter không gửi tin/không sửa Sheet ngoài phạm vi.
- wuby_studio/job_runner.py::channel_profile: chỉ nhận workflow wuby; từ chối phim/book. Không đẩy cauhinh2/cauhinh3 vào queue Wuby rồi coi là hỗ trợ đầy đủ.
- wuby_studio/queue.py + worker.py: hàng đợi SQLite, một worker render, kiểm tra job gián đoạn; không tạo thêm worker chạy chồng.
- tools/python_env.bat: ưu tiên WUBY_PYTHON/.venv/venv/VIRTUAL_ENV; không tự thay môi trường Torch/CUDA bằng Python global.

## Nguồn và đầu ra của dự án liên kết

Yêu cầu user về nguồn Douyin và chữ riêng K7: D:/0.1_FACE_BOOK/coordination/VIDEO_INPUTS_USER_2026-10-15.md.
K7 dùng cách render Wuby nhưng nhãn/title/branding của Sống Một Mình Có Gì Vui, không làm đổi K6.
Kho tập trung mới theo A94: D:/0.1_FACE_BOOK/videos_upload/<kênh>/<stage>. Các drive_folder trong bảng là cấu hình backend gốc, không tự đồng nhất với kho publisher mới. Adapter phải ghi nhận đường ra thật rồi commit có kiểm chứng về review_output_dir trong VIDEO_PIPELINES.json.
Không lấy video test/preview/audio_* làm ứng viên đăng chỉ dựa vào tên hoặc ffprobe hợp lệ; cần nội dung, nguồn và render proof.

## Điều kiện hoàn tất việc nối tự động

- Resolve cấu hình thật cho từng kênh và ghi fingerprint config/job.
- Tách renderer headless khỏi callback Telegram/Sheets/preview; không bypass các approval còn hiệu lực.
- Giữ đầu ra tạm, media proof, không overwrite, duplicate/HOLD và phục hồi có kiểm chứng.
- Phân biệt code mới, tiến trình đã nạp code, render thật và soak tự nhiên. Không tăng % từ số test.
- Ghi chú này chỉ là kết quả đọc code/config, không phải nghiệm thu render hoặc publishing.

## Fingerprint source đã đọc

- `backend/channels_config.json`: `2d34ad0e268d5032fd65fc23b61c2bbd21c385b38df8c00fe9cab64f692930b0`
- `backend/channel_manager.py`: `cce94e1ab252c53927d19ecdfdf4fe30389ac8f9bac48081793d5a5dd400d8a7`
- `backend/telegram_bot.py`: `3f20f1f61b4e1f07c77c094f0018edfee332673a625355b469f5740953f2e4f4`
- `backend/video_merger.py`: `8dd9fc27216ed0766788cb4646f316c5a62a6615a65eb50982b68b3a056ff759`
- `wuby_studio/config.py`: `29d66ec4d611f3b11d28a654d6d693835b20a2c08d18d4e5210d86c3119d7e14`
- `wuby_studio/job_runner.py`: `72a3cc3b881a44e47b63493f2c50dfa5a89d7ddef353ea26654a2cfddd258aaa`
- `README_CLONE_PHIM_F0.md`: `5947d174784e246647cca227e7f19b1c006bcb8d049f515f9d0d72ae05033be2`
- `README_CAU_HINH_3_4_AUDIO.md`: `3c5ae3048e4e2ee7b0293adc60451a702c79d825d1761dd99e5c83dfa03b02e8`

## Sửa theo bug từng kênh — 18/10/2026

Đọc bản đồ mới tại `D:/0.1_FACE_BOOK/videos_upload/HUONG_DAN_SUA_LOI_TUNG_KENH.md` và bug.txt + BUG_STATUS.json trong review từng kênh. Báo cáo ngày 16/10 phía trên là lịch sử, không thay thế config đã resolve của job mới.

K5/K8 đang chuyển mask tĩnh sang OCR theo thời gian, cấm mask ước lượng khi thiếu box; tall-caption K5 cần nhận chữ 91px/1080. K8 bật burn_sub trở lại. K7 dùng tên tiêu đề + ID và route theo channel/branding. Preset thử `chuyen_hai_dua` tách khỏi publisher/K6. Voice plan phải đối chiếu actual multivoice report; cache clone bind transcript + sample + thông số, lỗi clone phải dừng thay vì dùng file cũ.

Source mới không có nghĩa bot cũ đã nạp: bot dùng cache config trong memory. Các CLI sửa cục bộ nạp source mới riêng, giữ chờ xác nhận và publish NONE. Không restart publishing runtime để nạp bản vá. K5 lần thử đầu bị QC chặn vì chưa tìm được box; không xuất/duyệt video đó. Hồ sơ source/tests/đầu ra tại `coordination/render_bugfix_20261018`.
