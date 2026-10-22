# QUY CHUẨN KỸ THUẬT & KIẾN TRÚC HỆ THỐNG VIDEO AI (BẢN CHÍNH THỨC)

**Dự án:** Hệ thống tự động dịch, bóc tách nhân vật, che chữ và lồng tiếng phim/video ngắn  
**Phần cứng đích:** Windows 11, GPU NVIDIA CUDA (GeForce RTX, VRAM 16 GB), Python 3.10

---

## 1. QUY TẮC CỐT LÕI (BẤT DI BẤT DỊCH)

1. **TTS ENGINE ĐỘC TÔN:** **`OmniVoice` (`kjanh/KhanhTTS-OmniVoice`)**
   - **Tuyệt đối CẤM sử dụng các engine khác** (như Edge-TTS, Google TTS, Kokoro hay các model thử nghiệm).
   - Mô hình được lưu trữ tại cache cục bộ: `D:\0.1_FACE_BOOK\DUNG_CHUNG\MODELS\HF_CACHE\hub\models--kjanh--KhanhTTS-OmniVoice`.
   - Sinh giọng trực tiếp trên CUDA bằng FP16, thời gian suy luận cực nhanh (~1.3s / câu).

2. **KHO MẪU GIỌNG (VOICE SAMPLES):**
   - Nằm tại: `D:\0.1_FACE_BOOK\Lay video tiktok\voice_samples`
   - Gồm các file audio mẫu và text chuẩn:
     - `3_nu_tram_am.mp3`: Giọng nữ trầm ấm, đứng tuổi (dành cho vai Bà lão, Lão thái thái, người lớn tuổi).
     - `giongnucute.wav`: Giọng nữ trẻ trung, trong trẻo, hoạt bát (dành cho Nữ chính, thiếu nữ).
     - `giongnu_ngoctrinh_235hz.wav`: Giọng nữ thanh nhẹ (dành cho Nữ phụ).
     - `laivansam_short.wav`: Giọng MC Lại Văn Sâm (trầm ấm, triết lý, từng trải).
     - `danchuongtrinhvip_short.wav`: Giọng Dẫn chương trình VIP (hào sảng, kể chuyện phim).
     - `giongtauthao_short.wav`: Giọng Tào Tháo (nam trung niên uy nghiêm, khí phách, phản diện).
     - `chautinhtri_short.wav`: Giọng Châu Tinh Trì (hài hước, dí dỏm).
     - `giongdocconhan_short.mp3`: Giọng đọc cổ nhân (phim kiếm hiệp, tu tiên).

3. **CẤM CAN THIỆP TẦN SỐ (PITCH = 0Hz):**
   - **Tuyệt đối CẤM chỉnh pitch** (như `+12Hz`, `-18Hz`, v.v.) vì làm méo mó âm thanh thành tiếng robot.
   - Mọi nhân vật đều giữ nguyên tần số gốc tự nhiên của mẫu giọng được clone.

4. **TỐC ĐỘ ĐỌC MẶC ĐỊNH:** **`1.5x`**
   - Áp dụng bộ lọc `atempo=1.5` trên âm thanh sau khi sinh bởi OmniVoice để tăng tốc độ nói lên 1.5x (+50%) mà bảo toàn 100% cao độ và âm sắc.

5. **MÔ HÌNH NHẬN DIỆN GIỌNG NÓI (ASR):** **`Whisper Large-v3 (Full)`**
   - Chỉ dùng duy nhất `Systran/faster-whisper-large-v3` (`float16` trên CUDA).
   - Đã xoá bỏ hoàn toàn các model yếu/nhỏ hơn (Turbo, Medium, Small, Base, Tiny) khỏi hệ thống.

6. **MÔ HÌNH PHÂN TÁCH NGƯỜI NÓI (SPEAKER DIARIZATION):** **`Pyannote 3.1`**
   - Sử dụng `pyannote/speaker-diarization-3.1` trên CUDA để tự động nhận diện và gán nhãn từng câu thoại cho từng nhân vật (`SPEAKER_00` đến `SPEAKER_07`).

7. **BÓC TÁCH ÂM THANH GỐC (VOCAL REMOVAL):** **`UVR-MDX-NET-Inst_HQ_3.onnx`**
   - Cơ chế: `Hard Replace` triệt tiêu 100% tiếng thoại gốc tiếng Trung, giữ nguyên vẹn 100% nhạc nền và sound effects gốc của phim.

8. **HIỆU ỨNG CHE PHỤ ĐỀ CŨ:** **`blur_sub_black` (Kính mờ trong suốt Frosted Glass)**
   - Vùng mờ tự nhiên: Chiều cao thon gọn ~92px ôm sát dòng chữ Trung.
   - Cấu hình: `Alpha = 0.0` (trong suốt hoàn toàn), `BorderStyle = 1` (outline sắc nét không tạo mảng đen sau chữ).

---

## 2. DANH SÁCH MÔ HÌNH ĐÃ DỌN DẸP (Xoá vĩnh viễn)

Nhằm tối ưu dung lượng và tránh nhầm lẫn trong các phiên làm việc tiếp theo, toàn bộ các mô hình yếu hoặc không đạt chuẩn đã được xoá sạch khỏi `D:\0.1_FACE_BOOK\DUNG_CHUNG\MODELS\HF_CACHE\hub` (giải phóng hơn 16.5 GB ổ đĩa):
- ❌ `models--facebook--mms-tts-vie`
- ❌ `models--contextboxai--Kokoro-Vietnamese`
- ❌ `models--pnnbao-ump--VieNeu-TTS-v3-Turbo` (lỗi treo upstream)
- ❌ `models--pnnbao-ump--VieNeu-TTS-v3-Nano`
- ❌ `models--k2-fsa--OmniVoice` (bản thô, đã thay bằng KhanhTTS)
- ❌ `models--deepdml--faster-whisper-large-v3-turbo-ct2`
- ❌ `models--openai--whisper-large-v3-turbo`
- ❌ `models--Systran--faster-whisper-medium`
- ❌ `models--Systran--faster-whisper-small`
- ❌ `models--Systran--faster-whisper-base`
- ❌ `models--Systran--faster-whisper-tiny`
