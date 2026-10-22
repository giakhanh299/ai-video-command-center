# BẢNG YÊU CẦU NÂNG CẤP & SỬA CODE HỆ THỐNG LỒNG TIẾNG VOICE CLONE (V5)
**Dành cho Developer / AI Audio Engineer tiếp nhận dự án**

---

## 1. TỔNG QUAN BÀI TOÁN & MỤC TIÊU DỰ ÁN

Dự án này là hệ thống tự động hóa **Tải video ngắn (TikTok / Douyin hoạt hình Tiểu Wuby / Quby hoặc Review phim) -> Nhận diện giọng nói -> Dịch thuật phụ đề -> Lồng tiếng tiếng Việt đa vai (Multi-voice AI) -> Render video hoàn chỉnh**.

### 🎯 Mục tiêu cốt lõi của phần GIỌNG NÓI (Voice System):
1. **Phân biệt 2 vai rõ ràng:**
   - **Vai 1: Người dẫn chuyện (Narrator):** Giọng tự nhiên, trong trẻo, nhẹ nhàng, tốc độ chuẩn 1.0x, **KHÔNG gồng cảm xúc**, đọc lời thoại dẫn dắt.
   - **Vai 2: Nhân vật hoạt hình trong video (Wuby):** Cần **CẢM XÚC** hờn dỗi, nũng nịu, dễ thương, đúng chất meme hoạt hình.
2. **Khớp nhịp thời gian (Audio-Video Sync):**
   - Không bị tình trạng giọng trước kéo dài đè lên giọng sau (audio overlap).
   - Không bị ép đọc quá nhanh (1.5x - 2.0x) làm giọng bị biến dạng, méo tiếng hoặc vội vã.
3. **Mute tiếng gốc nhưng giữ lại tiếng cảm xúc / BGM:**
   - Khi câu tiếng Việt cất lên, cần hạ âm lượng hoặc mute tiếng Trung gốc của nhân vật.
   - Khi nhân vật không nói hoặc có âm thanh cảm xúc ("oa", "hừ", "ơ", tiếng khóc, tiếng cười, tiếng thở dài, hiệu ứng âm thanh FX, nhạc nền BGM), **PHẢI GIỮ LẠI ĐƯỢC** để video sống động.
4. **Nhân bản giọng xuyên ngôn ngữ (Cross-Lingual Voice Cloning):**
   - Trích xuất đặc trưng âm học (timbre, vocal tract, cao độ F0) từ file âm thanh tiếng Trung gốc của nhân vật trong video (`sample_data/character_original.ref.wav`) để clone sang câu tiếng Việt.

---

## 2. DANH SÁCH 4 VẤN ĐỀ KỸ THUẬT CẦN BẠN SỬA ĐỔI / TỐI ƯU

### 🔴 Vấn đề 1: Khớp thời gian & Chống chồng đè giọng (Time Sync & Overlap Prevention)
- **Hiện tượng lỗi:**
  - Tiếng Việt dịch từ tiếng Trung thường có số lượng âm tiết dài hơn (ví dụ: `我的目标` 4 âm tiết -> `Mục tiêu của tôi là` 6 âm tiết).
  - Khi đọc ở tốc độ tự nhiên (1.0x - 1.2x), câu 1 kết thúc muộn hơn thời điểm câu 2 bắt đầu, dẫn đến hiện tượng **hai câu thoại nói đè lên nhau cùng lúc**.
  - Nếu cưỡng ép tăng tốc độ đọc (speed = 1.5x - 1.8x) thì giọng đọc bị biến dạng cơ học, nghe gấp gáp, mất tự nhiên.
- **Mong muốn của người dùng:**
  - *"chưa khớp voice giọng trước đè giọng sau, có thể đọc chậm hoặc nhanh hơn"*
  - *"đọc nhanh quá làm sao để khớp lại mà ko nhanh, kéo dài video ra cũng được"*
  - Có khoảng nghỉ thở rõ ràng giữa các câu (ví dụ nghỉ 0.5s - 0.8s sạch sẽ, không đè giọng).
- **Giải pháp đề xuất cho bạn:**
  1. **Phương án A (Co giãn âm thanh chất lượng cao - High Quality Time Stretch):**
     - Thay vì dùng thuật toán ffmpeg `atempo` cơ bản, hãy dùng thuật toán chuyên nghiệp bảo toàn cao độ: **Rubberband** (`pyrubberband`), **WSOLA**, hoặc **SoundTouch** với dynamic stretch: chỉ tăng tốc nhẹ các từ phụ và giữ nguyên tốc độ từ khóa.
  2. **Phương án B (Kéo dãn video thông minh - Video Time Extension / Freeze Frame):**
     - Xem file tham khảo: `solutions_and_experiments/make_perfect_sync_video.py`.
     - Nếu câu tiếng Việt cần 3.5s mà đoạn video gốc chỉ có 2.5s: tự động kéo dài video bằng cách làm chậm nhẹ khung hình (Slow-motion 0.85x) hoặc đóng băng nhẹ (Freeze frame) ở những frame nhân vật đang dừng chuyển động / chớp mắt, để giọng đọc thong thả chuẩn 1.0x mà video vẫn khớp 100%!

---

### 🔴 Vấn đề 2: Xử lý âm thanh nền (Audio Ducking / Muting vs Giữ lại cảm xúc)
- **Hiện tượng lỗi:**
  - Nếu mute toàn bộ audio gốc của video thì video bị "chết" âm thanh nền (mất tiếng cười, tiếng nấc, tiếng khóc dễ thương của Wuby, mất cả nhạc nền BGM).
  - Nếu để âm thanh gốc thì tiếng Trung xì xào bên dưới đè lên tiếng Việt lồng tiếng, nghe rất rối và khó chịu.
- **Mong muốn của người dùng:**
  - *"mute lúc tiếng việt đã đọc lên thì mute tiếng nền cũ đi"*
  - *"mute khúc sub thôi mà hiểu ko, cố gắng giữ lại mấy âm thanh của cảm xúc?"*
- **Giải pháp đề xuất cho bạn:**
  1. **Dynamic Audio Ducking:**
     - Khi giọng lồng tiếng tiếng Việt cất lên (dựa theo timestamp thực tế của voice WAV): giảm âm lượng tiếng gốc xuống -18dB đến -24dB với đường bao Fade-in / Fade-out mượt mà (curve smoothing 50ms - 100ms).
     - Khi giọng tiếng Việt dứt (khoảng nghỉ thở hoặc đoạn reaction): tự động nâng âm lượng tiếng gốc lên 100% để giữ lại trọn vẹn tiếng khóc, tiếng kêu nũng nịu của nhân vật.
  2. **Tách nguồn âm thanh (Vocal Isolation / Stem Separation):**
     - Sử dụng mô hình AI tách giọng nhẹ (ví dụ `demucs`, `MDX-Net`, `UVR5` hoặc `spleeter`):
       - Tách thành 2 track: `Vocal_Trung_Goc` và `BGM_SoundEffects`.
       - Mute `Vocal_Trung_Goc` ở các đoạn sub tiếng Việt, chỉ giữ lại `BGM_SoundEffects` + tiếng Việt lồng tiếng!

---

### 🔴 Vấn đề 3: Tách biệt giọng Người Dẫn (Narrator) và Giọng Wuby cảm xúc
- **Yêu cầu:**
  - Câu 1: Giọng Nữ dẫn nhẹ nhàng, trong trẻo, giọng chuẩn (ví dụ Hoài My / Edge-TTS hoặc Nam Minh 1.0x), không cần gồng cảm xúc.
  - Câu 2 trở đi (hoặc câu thoại của Wuby): Cất lên giọng Wuby đầy cảm xúc hờn dỗi, nũng nịu (dùng mô hình Voice Clone).
- **File tham khảo đã dựng sẵn:**
  - Xem file: `solutions_and_experiments/make_reversed_multivoice.py` và `solutions_and_experiments/run_reversed_multivoice_pipeline.py`.
- **Nhiệm vụ của bạn:**
  - Tối ưu hóa router phân vai trong `core/voice_router.py` để tự động gán role:
    - Cue dẫn chuyện -> Role: `narrator` -> Giọng trong trẻo tự nhiên.
    - Cue thoại Wuby -> Role: `character` -> Giọng clone Wuby cảm xúc cao độ F0 cao.

---

### 🔴 Vấn đề 4: Nâng cấp mô hình Voice Clone (Cross-Lingual Zero-Shot TTS)
- **Hiện trạng:**
  - Hệ thống hiện tại có sẵn cấu trúc hỗ trợ 3 backend:
    1. **KhanhTTS / OmniVoice** (`kjanh/KhanhTTS-OmniVoice` - Higgs Audio Tokenizer 24kHz): Đã đo đạc kiểm nghiệm clone F0 thành công (xem `VOICE_CLONE_DIAGNOSIS.md`).
    2. **VieNeu-TTS v3 Turbo** (`pnnbao-ump/VieNeu-TTS-v3-Turbo` - MOSS Tokenizer 48kHz).
    3. **ZeroTTS / Edge-TTS** (`hamy`, `hoaimy`): Dùng làm cứu hộ (Fallback).
- **Nhiệm vụ của bạn:**
  - Kiểm tra, tinh chỉnh và nâng cấp mô hình voice clone sao cho phát âm tiếng Việt chuẩn xác nhất, không bị lẫn ngữ điệu Hán ngữ, giữ được âm vực cao vút, nũng nịu của Wuby.
  - Bạn có thể tích hợp thêm các mô hình clone giọng mới nhất (như **F5-TTS**, **CosyVoice**, **KikiVoice API**, **ChatTTS**, hoặc fine-tune checkpoint riêng cho nhân vật Wuby).

---

## 3. CẤU TRÚC THƯ MỤC GÓI MÃ NGUỒN

```text
package_voice_clone_v5/
├── README_HUONG_DAN_DEV_SUA_CODE.md   <-- File này (Hướng dẫn chi tiết toàn bộ yêu cầu)
├── VOICE_CLONE_DIAGNOSIS.md           <-- Báo cáo chẩn đoán âm học chi tiết (F0, Timbre, Spectrogram)
├── requirements_voice.txt             <-- Danh sách thư viện Python cần thiết
├── check_voice_backends.py            <-- Script kiểm tra môi trường máy bạn
│
├── core/                              <-- Toàn bộ mã nguồn xử lý âm thanh cốt lõi
│   ├── voice_router.py                <-- Router phân vai đa giọng & cache âm thanh
│   ├── omnivoice_service.py           <-- Service kết nối OmniVoice
│   ├── zerotts_voice.py               <-- Service fallback Edge-TTS
│   ├── audio_processor.py             <-- Cắt ghép, co giãn âm thanh, ducking
│   ├── sub_processor.py               <-- Nhận diện Whisper ngắt câu, dịch DeepSeek
│   ├── wuby_ocr_overlay.py            <-- Module phụ đề OCR in-place
│   └── scene_detector.py              <-- Phát hiện phân cảnh video
│
├── solutions_and_experiments/         <-- Các kịch bản và thử nghiệm đã chạy
│   ├── make_giai_phap_1.py            <-- Thử nghiệm Giải pháp 1: Multi-voice tiêu chuẩn
│   ├── make_giai_phap_2.py            <-- Thử nghiệm Giải pháp 2: DSP Filter / Thêm cảm xúc
│   ├── make_giai_phap_3.py            <-- Thử nghiệm Giải pháp 3: Cross-Lingual Clone
│   ├── make_reversed_multivoice.py    <-- Script phân chia: Nữ dẫn tự nhiên + Wuby cảm xúc
│   ├── run_reversed_multivoice_pipeline.py <-- Pipeline hoàn chỉnh phân vai
│   ├── make_perfect_sync_video.py     <-- Thuật toán kéo dài video để voice đọc tự nhiên 1.0x
│   ├── test_voice_clone.py            <-- Script test clone đơn lẻ
│   ├── test_ab_voice_clone.py         <-- Script đo đạc kiểm chứng A/B F0 vật lý âm thanh
│   └── inspect_voice_reference.py     <-- Phân tích file mẫu tham chiếu
│
├── voice_samples/                     <-- Bộ mẫu giọng thu sẵn chất lượng cao
│   ├── giongnucute.wav                <-- Giọng nữ hoạt hình dễ thương
│   ├── giongnamdanchuongtrinh.mp3     <-- Giọng nam dẫn chương trình truyền hình
│   ├── giongnamreviewdao.mp3          <-- Giọng nam review phim
│   ├── giongdocconhan_short.mp3       <-- Giọng tâm sự cổ nhân
│   └── ref_better_version.mp3         <-- Mẫu giọng sạch đã lọc tạp âm
│
└── sample_data/                       <-- Dữ liệu video và audio test thực tế
    ├── character_original.ref.wav     <-- Giọng gốc nhân vật Wuby bóc tách từ video
    ├── character_fast.ref.wav         <-- Mẫu câu ngắn tốc độ cao
    ├── character_tuned.ref.wav        <-- Mẫu đã tinh chỉnh F0
    ├── voice_vi.wav                   <-- File tiếng Việt mẫu
    ├── input_video.mp4                <-- Video mẫu gốc
    ├── subtitles_vi.srt               <-- File phụ đề SRT mẫu
    └── reference_output.mp4           <-- Video tham chiếu kết quả
```

---

## 4. HƯỚNG DẪN BẮT ĐẦU DÀNH CHO BẠN (QUICK START)

1. **Cài đặt thư viện:**
   ```bash
   pip install -r requirements_voice.txt
   ```
2. **Kiểm tra môi trường backend giọng nói:**
   ```bash
   python solutions_and_experiments/check_voice_backends.py
   ```
3. **Chạy thử kịch bản Nữ Dẫn + Wuby Cảm xúc:**
   ```bash
   python solutions_and_experiments/make_reversed_multivoice.py
   ```
4. **Chạy thử thuật toán kéo dài video khớp giọng không bị đè:**
   ```bash
   python solutions_and_experiments/make_perfect_sync_video.py
   ```
5. **Đọc báo cáo chẩn đoán âm học chi tiết:**
   - Mở file [VOICE_CLONE_DIAGNOSIS.md](VOICE_CLONE_DIAGNOSIS.md) để xem chi tiết cách hoạt động của Higgs Audio Tokenizer và MOSS Tokenizer.

---
*Cảm ơn bạn rất nhiều vì đã hỗ trợ nâng cấp phần giọng nói cho dự án! Chúc bạn code suôn sẻ và đạt kết quả xuất sắc!* 🎙️✨
