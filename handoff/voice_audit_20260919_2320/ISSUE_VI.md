# Báo Cáo Kỹ Thuật: Kiểm Tra Sự Cố Âm Thanh & Voice Clone (D:\0.1_FACE_BOOK\Lay video tiktok)

**Thời điểm thực hiện:** 2026-09-19 23:25 GMT+7  
**Phạm vi:** Kiểm tra nguồn chỉ đọc; không sửa mã backend; không phát sinh cước hay gửi Telegram/dịch vụ ngoài; chỉ dùng model offline tại `D:\0.1_FACE_BOOK\DUNG_CHUNG\MODELS\HF_CACHE`.

---

## 1. Phản Ánh Của Người Dùng & Bằng Chứng Khách Quan

Người dùng phản ánh: **Âm thanh đầu ra nghe rất tệ hoặc không nghe thấy gì (inaudible / terrible).**

Qua phân tích mã nguồn và đo đạc kỹ thuật thực tế, vấn đề do 3 nguyên nhân cốt lõi:

### A. Sinh file WAV hoàn toàn câm khi TTS gặp lỗi (Inaudible Root Cause)
- **Vị trí:** `backend/sub_processor.py` (dòng 535–536, 596–640) và `backend/audio_processor.py` (dòng 92–148).
- **Cơ chế lỗi:** Khi dùng giọng preset Edge-TTS/Google mà các worker gặp sự cố mạng hoặc lỗi runtime, hàm `_render_tts_chunk` trả về `None`. Pipeline khởi tạo sẵn `AudioSegment.silent(...)` nhưng không kiểm tra xem có đoạn thoại nào được overlay hay không. Kết quả là hàm vẫn xuất file WAV thành công nhưng **100% các khung âm thanh là số 0 tuyệt đối (-240 dBFS)**.
- **Thực chứng:** Đã cô lập và tái hiện thành công qua `preset_failed.wav` và `legacy_failed.wav` (RMS = 0.0, Peak = 0.0, silent_frames_pct = 100%). Hơn nữa, thư mục `workspace/tts_chunks/` tồn tại tới hàng trăm file MP3 kích thước 0 byte.

### B. Bộ trộn `amix` làm suy hao 6 dB âm lượng giọng lồng tiếng
- **Vị trí:** `backend/video_merger.py` dòng 1027:
  ```python
  filters.append("[abg][avoice]amix=inputs=2:duration=first:dropout_transition=2[aout]")
  ```
- **Cơ chế lỗi:** Bộ lọc `amix` của FFmpeg khi không truyền `normalize=0` sẽ tự động chia đều biên độ các luồng (mỗi luồng nhân 1/N, tức giảm một nửa biên độ, tương đương **suy hao -6.02 dB**).
- **Thực chứng đo lường:** File thử nghiệm chuẩn với sóng sin `tone.wav` có đỉnh 0.20 (-13.98 dBFS):
  - Qua `amix` mặc định (`mix_default.wav`): đỉnh bị kéo xuống còn 0.10 (-20.00 dBFS, **mất 6.02 dB**).
  - Qua `amix=...:normalize=0` (`mix_off.wav`): đỉnh giữ nguyên 0.20 (-13.98 dBFS).
  Kết hợp với việc âm lượng nền (`bg_volume`) từng có cấu hình lên tới 0.35 - 0.50, giọng đọc bị nhạc nền đè bẹp, gây cảm giác "nghe rất tệ, nghẹt tiếng hoặc không rõ".

### C. Độ ổn định của bộ clone giọng và ngưỡng assert F0
- Chạy thực tế mô hình `kjanh/KhanhTTS-OmniVoice` trên GPU RTX 5060 Ti:
  - Sinh âm thanh tốt với thời gian tải ~1.9s, suy luận ~0.9s - 1.2s.
  - Tuy nhiên, câu thoại hoạt hình ngắn cho kết quả `F0 Median = 292.7 Hz` (trong khi `test_wuby_real_model.py` đặt điều kiện cứng `assert >= 300 Hz`), dẫn đến bài test cũ bị fail dù giọng thực tế vẫn là tông cao nữ/hoạt hình.
  - Mô hình `VieNeu-TTS-v3-Turbo` gặp lỗi checkpoint/loại mô hình khi khởi tạo (`vieneu_v3` vào lớp rỗng) và bị treo vượt quá ngưỡng an toàn 110s.

---

## 2. Lệnh Tái Hiện Sự Cố (Reproduction Commands)

Tất cả lệnh chạy trên Windows PowerShell tại thư mục `D:\0.1_FACE_BOOK\Lay video tiktok`:

1. **Tái hiện lỗi sinh âm thanh câm (Silent Audio Bug):**
   ```powershell
   python -B -X utf8 handoff\voice_audit_20260919_2320\diagnose.py logic
   ```
2. **Kiểm tra suy luận clone trực tiếp trên GPU (Offline):**
   ```powershell
   python -B -X utf8 handoff\voice_audit_20260919_2320\diagnose.py khanh_original
   ```
3. **Chạy lại bộ test tích hợp sub_processor với Wuby clone:**
   ```powershell
   python -B -X utf8 handoff\voice_audit_20260919_2320\integration_safe.py test_sub_processor_wuby.py
   ```
4. **Kiểm tra 22 test OCR, film bars và profiles:**
   ```powershell
   python -B -X utf8 handoff\voice_audit_20260919_2320\diagnose.py unit
   ```

---

## 3. Ma Trận Kiểm Thử Thực Tế (Test Matrix: Expected vs Actual)

| Hạng mục / Bài test | Kỳ vọng | Thực tế đo đạc | Kết luận |
| :--- | :--- | :--- | :--- |
| **OCRHandoffTests & Assignment (10 test)** | 10/10 PASS | 10/10 PASS (thời gian 0.006s) | ĐẠT (Khớp báo cáo 22 test trước) |
| **FilmBlackBarsTests (8 test)** | 8/8 PASS | 8/8 PASS | ĐẠT |
| **ChannelProfiles (4 test)** | 4/4 PASS | 4/4 PASS | ĐẠT |
| **Xác minh file `full_after.mp4`** | Tồn tại, phát bình thường | Tồn tại (12,026,619 bytes, 21.04s, video h264 + audio aac, RMS -25.2 dBFS, Peak -0.99 dBFS) | ĐÃ XÁC MINH |
| **Test câm: TTS rớt toàn bộ câu** | Ném lỗi hoặc cảnh báo | Xuất file WAV 100% im lặng (silent_frames = 100%, RMS = 0) | ĐÃ TÁI HIỆN BUG |
| **Độ suy hao âm thanh qua `amix`** | Giữ nguyên biên độ giọng | Mất chính xác 6.02 dB biên độ nếu không có `normalize=0` | ĐÃ TÁI HIỆN BUG |
| **KhanhTTS: Giọng gốc cartoon** | Clone hoàn tất <= 120s | Sinh WAV 4.84s trong 9.03s; F0 Mean = 316.8 Hz | ĐẠT |
| **KhanhTTS: Giọng hoạt hình tuned** | Clone hoàn tất <= 120s | Sinh WAV 4.84s trong 8.93s; F0 Mean = 314.7 Hz | ĐẠT |
| **KhanhTTS: Giọng nam MC dẫn chuyện** | Clone hoàn tất <= 120s | Sinh WAV 5.86s trong 12.84s; F0 Mean = 146.2 Hz | ĐẠT |
| **OmniVoice: Chế độ Auto** | Sinh âm thanh <= 120s | Hoàn tất trong 9.17s (RMS -11.6 dBFS) | ĐẠT |
| **OmniVoice: Chế độ Voice Design** | Sinh âm thanh <= 120s | Hoàn tất trong 11.22s | ĐẠT |
| **VieNeu-TTS v3 Turbo** | Clone <= 120s | Cảnh báo tương thích checkpoint, vượt ngưỡng 110s (TIMEOUT) | KHÔNG KHẢ DỤNG TRONG NGƯỠNG AN TOÀN |
| **Test `test_wuby_real_model.py`** | F0 Median >= 300 Hz | Đo được 292.7 Hz -> fail ở dòng assert cứng | CẦN ĐIỀU CHỈNH NGƯỠNG HOẶC PROMPT |
| **Test `test_sub_processor_wuby.py`** | PASS trọn vẹn quy trình | PASS (Hoàn thành trong 9.19s, F0 Mean 313.6 Hz) | ĐẠT |

---

## 4. Phân Biệt Báo Cáo Lịch Sử vs Đo Đạc Thực Tế Mới

1. **Báo cáo lịch sử (`VOICE_CLONE_DIAGNOSIS.md`):**
   - Từng ghi nhận: KhanhTTS đạt F0 335.7 Hz trên câu ngắn, VieNeu đã được patch, ZeroTTS là fallback.
2. **Đo đạc thực tế mới (Thực hiện hoàn toàn offline trên máy):**
   - Xác nhận: KhanhTTS hoạt động thực sự trên GPU, phân biệt rõ rệt giữa giọng nam (F0 ~146 Hz) và giọng cartoon/nữ (F0 ~314 - 317 Hz).
   - Tuy nhiên, VieNeu hiện tại bị nghẽn suy luận (chưa an toàn để đưa vào production pipeline tự động).
   - Phát hiện mới chưa từng ghi trong báo cáo cũ: **Bug xuất âm thanh câm khi lỗi TTS** và **suy hao âm lượng do bộ lọc `amix` của FFmpeg**.

---

## 5. Các Vấn Đề Chưa Giải Quyết & Khuyến Nghị Kỹ Thuật

1. **Xử lý triệt để lỗi âm thanh câm:**  
   Cần thêm chốt chặn trong `sub_processor.py` và `audio_processor.py`: nếu toàn bộ các chunk trả về rỗng, phải ném ngoại lệ `AudioGenerationFailedError` thay vì xuất file WAV câm ra đĩa.
2. **Chuẩn hóa bộ lọc trộn âm `amix`:**  
   Trong `video_merger.py` (dòng 1027), đổi `amix=inputs=2:duration=first:dropout_transition=2` thành có thêm tham số `:normalize=0` để tránh bị dìm âm lượng giọng đọc xuống một nửa.
3. **Mô hình VieNeu:** Tạm thời đặt `enabled: false` trong router để tránh trường hợp pipeline bị treo chờ quá lâu; ưu tiên sử dụng `khanh_omnivoice` đã được chứng minh ổn định.
4. **Vệ sinh cache tts_chunks:** Xóa các file rác 0 byte đang tồn đọng trong `workspace/tts_chunks/`.
