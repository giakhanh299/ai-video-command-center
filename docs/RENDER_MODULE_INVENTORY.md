# Kiểm kê và kế hoạch tách module render

Ngày: 2026-10-22 (Asia/Bangkok). Trạng thái: kiểm kê mã nguồn + thiết kế DRAFT 0.1.0.
Phạm vi chính: `D:/0.1_FACE_BOOK/Lay video tiktok`.
Đợt đầu đã thêm tài liệu/fixture và tách 9 helper từ video_merger.py sang render_modules;
chưa restart dịch vụ, đổi queue/database hay triển khai. Xem RENDER_MODULE_EXTRACTION_REPORT.md.

## Bằng chứng và giới hạn

| Thành phần | Vị trí | Đã xác minh | Tái sử dụng / việc còn lại | Rủi ro |
|---|---|---|---|---|
| API đơn giản | backend/main.py | `/api/process`, `/api/status/{job_id}`, `/api/health`; job trong dict RAM; health local 8005 trả 200 | Không dùng dict làm queue mới; giữ tương thích khi chuyển | Không có auth trong handler đã đọc; restart mất job |
| Bot sản xuất | backend/telegram_bot.py | handle_video_download ghép config, tải, sub, chọn giọng, TTS, render và giao kết quả | Trích orchestration ra khỏi adapter Telegram sau khi có baseline | Gọi nguyên handler sẽ gửi Telegram/cập nhật luồng ngoài render |
| Renderer chính | backend/video_merger.py | process_video_sub_and_mute dài 936 dòng theo AST trước/sau extraction | Tách từng nhánh qua adapter, giữ hàm cũ làm facade | OCR, audio, phụ đề, encoder và cache đang gắn chặt |
| Renderer đơn giản | backend/video_merger.py | build_render_command, AdvancedRenderService, merge_video_audio | Đăng ký riêng, không coi tương đương renderer chính | API 8005 không đại diện toàn bộ pipeline bot |
| Phụ đề / giọng | backend/sub_processor.py | ASR, dịch, xử lý cue, TTS một/đa giọng, title/caption cùng file | Tách ASR, dịch, timeline, voice synthesis theo artifact | Import có thể nạp model; API dịch có tác dụng phụ/chi phí |
| Phân tích | backend/wuby_preflight.py, movie_voice_matcher.py, character_identity.py | Có preflight, matching và Character ID | Dùng report/hash làm đầu vào bước sau | F0 không chứng minh danh tính người nói |
| Nền / mix | backend/audio_voice_switch.py, dialogue_replace.py | Có hai hàm cùng tên prepare_dialogue_replacement trong hai file | Module ID phải xác định rõ implementation | Không thay lẫn AI separation, 5.1 và center-cancel |
| Wuby Studio | wuby_studio/queue.py, worker.py, job_runner.py | Queue SQLite bền vững; worker hỗ trợ Windows, heartbeat/cancel/retry/recover | Tái sử dụng hành vi và renderer; thay persistence bằng PostgreSQL trong thiết kế mới | channel_profile chặn workflow ngoài Wuby; khóa worker theo queue, không phải khóa GPU toàn máy |
| Visual Wuby | wuby_studio/renderer.py, bridge.py | render, packet/hash, rerender; bridge ép fps=12 | Giữ nhánh Wuby editorial riêng với overlay trong video | README nói fps source nhưng bridge khác; chưa đổi chính sách FPS |
| QC và lưu | backend/wuby_qc.py, render_review_policy.py, render_storage.py | Report, binding kênh, copy độc quyền và chống ghi đè | Dùng sau render; đưa output về REVIEW | File tồn tại không chứng minh chất lượng hoặc đã được người dùng duyệt |
| PostgreSQL có sẵn trong mã Motion | ../Video Control/motions-studio-main/motions-studio-main/api/src/db.js | pg.Pool và DATABASE_URL | Tham khảo pool/migration; không lấy nguyên backend lớn để thay dự án | Chưa xác minh server/quyền/database hoạt động |

Môi trường: Python PATH 3.10.11; có tiến trình dùng Python 3.14 và venv khác.
Node PATH 24.15.0; FFmpeg 8.1.2; GPU RTX 5060 Ti 16311 MiB; CUDA Toolkit 13.2.
Đây không phải bằng chứng các model inference được trong interpreter đang dùng.
Không thấy psql/pg_dump/pg_restore trong PATH hoặc Windows service tên postgres ở lần kiểm tra;
có docker.exe. Chưa kết luận PostgreSQL không tồn tại ở container/remote.

## Preset: dữ liệu thực tế khác tài liệu cũ

Chỉ đọc các trường không nhạy cảm từ channels_config.json, không xuất toàn bộ cấu hình.

| Preset key | workflow trong cấu hình hiện tại | Ghi chú |
|---|---|---|
| wuby | wuby | apply_job_preset đặt in_video_overlay |
| cauhinh2 | film_review_black | Không đồng nhất với README_CLONE_PHIM_F0 gọi cấu hình 2 là clone phim |
| cauhinh3 | movie_clone | movie_clone_blur, blur_sub_black |
| cauhinh3_wuby | wuby | wuby_overlay, AI dialogue removal |
| chidepdicau | gaidep_cauca | gaidep_blur, blur_sub_black |
| song1minhcogivui | wuby | Cần giữ cấu hình/kênh riêng |

Alias hiện tại: cauhinh4 -> chidepdicau; cauhinh5 -> song1minhcogivui.
Không đổi preset key hay diễn giải lại cấu hình 2 theo README cũ.
Frontend phải lấy danh sách preset từ registry backend; không hard-code suy luận từ số nút.

## Ranh giới module đề xuất

| ID dự thảo | Chức năng | Implementation hiện có | Artifact đầu ra |
|---|---|---|---|
| media.probe | Thông số video/audio/FPS rational | wuby_studio/media.py | media report |
| subtitles.transcribe | Trích audio + ASR | sub_processor.extract_and_transcribe_to_srt | source SRT + cue JSON |
| subtitles.translate | Dịch cue đã có | sub_processor.translate_srt_to_vietnamese_srt | Vietnamese SRT + cue JSON |
| analysis.preflight | OCR/scene/geometry và kiểm tra Wuby | wuby_preflight.analyze_wuby_preflight | preflight report |
| voice.assign | Matching một/đa giọng | movie_voice_matcher + character_identity | assignment report |
| voice.synthesize | TTS khớp timeline | generate_dubbed_audio[_multivoice] | WAV + voice manifest |
| audio.prepare_background | Chuẩn bị nền theo strategy đã chọn | audio_voice_switch hoặc dialogue_replace qua adapter riêng | background WAV + strategy report |
| render.compose | Hình, subtitle, logo, encoder | process_video_sub_and_mute hoặc wuby_studio.renderer.render | MP4 + render report/packet nếu nhánh hỗ trợ |
| render.rerender | Đổi hình từ packet, giữ narration | wuby_studio.renderer.rerender | MP4 + report |
| quality.verify | Media integrity + QC theo preset | wuby_qc, ffprobe, render_review_policy | QC report, needs_review |
| outputs.register | Commit metadata, giao thư mục review | render_storage qua wrapper | output record + checksum |

Các ID trên là đề xuất, CHƯA phải module có thể gọi qua API.
Không tách riêng audio.prepare_background rồi để legacy renderer tách nền lại lần hai.
Trước khi đưa bước đó ra DAG, adapter phải chứng minh renderer tiêu thụ artifact đã chuẩn bị.
Tương tự, legacy compose có thể chạy OCR/QC nội bộ: capability phải khai báo bước nào đã tích hợp.
Giai đoạn chuyển tiếp chỉ cho task render.compose gọi nguyên renderer đã được kiểm soát,
không quảng cáo có thể resume từng bước bên trong khi chưa trích xong.

## Thứ tự thay đổi và khôi phục

1. Chốt DRAFT với frontend; lưu snapshot/checksum các file runtime sẽ sửa, cấu hình và dependencies.
2. Chọn interpreter thực tế, test baseline trong thư mục cô lập; không chạy handler Telegram khi import.
3. Tách module thuần trước: media metadata, timestamp/ASS và config normalization; facade cũ giữ signature.
4. Tạo adapter render.compose theo từng preset, test cùng input/config/output tách biệt.
5. Thêm PostgreSQL repositories/queue + manifest validation; không tạo SQLite mới hoặc fallback SQLite.
6. Tách ASR/TTS/audio/OCR từng bước; cache gắn input/config/model hash và version module.
7. Chuyển entrypoint web/worker sang PostgreSQL sau migration staging + restore test.
8. Cutover có cửa sổ dừng nhận job; không để queue cũ và mới thực thi cùng một job.

Trước sửa runtime: backup ngoài cây source chia sẻ, hash manifest không chứa secret;
snapshot database đang dùng qua API backup phù hợp, không copy mù file SQLite đang mở/WAL.
Rollback code không tự replay job: đối soát process tree, claim, output checksum trước.
Nếu PostgreSQL đã nhận job mới, rollback phải giữ ledger/mapping và ngăn hai scheduler cùng chạy.

## Tiêu chí trước nghiệm thu

- Test khác biệt giữa legacy và adapter: layout, FPS, audio/subtitle timeline, logo, preset binding.
- Invalid schema/action/path bị từ chối trước nạp model hoặc spawn process.
- PostgreSQL claim cạnh tranh, idempotency, lease fencing, offline/restart và retry có evidence.
- Không gửi Telegram/Sheet/upload/publish trong render-only adapter.
- Render thật từng preset với source được duyệt; kiểm tra frame/audio, không chỉ exit code.
- Backup/restore PostgreSQL vào database staging và đối chiếu row/checksum.
- 42 test baseline đạt trước extraction; 43 test liên quan đạt sau extraction.
  Đây không phải render thật hay kiểm chứng PostgreSQL/Agent; xem báo cáo extraction.
