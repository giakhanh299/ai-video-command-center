# HƯỚNG DẪN CẤU HÌNH 4 & SỔ TAY XỬ LÝ LỖI HỆ THỐNG VIDEO AI

> **Phiên bản:** Cấu hình 4 Hoàn Thiện (Chị Đẹp Đi Câu @chidepdicau)  
> **Cập nhật ngày:** 05/10/2026  
> **Đặc trưng:** Giọng clone OmniVoice Nữ Cute (`giongnucute.wav`), Tốc độ 1.45x, Chuẩn hóa chữ số tiếng Việt, Hòa âm 3 luồng (Sông nước 70% + Tiếng Trung 30% + Thuyết minh 100%), Subtitle Karaoke viền đen canh giữa, Title Banner tự động 2.5s.

---

## 1. THÔNG SỐ CHUẨN CẤU HÌNH 4 (`chidepdicau`)

### A. Cấu hình Preset trong `backend/channels_config.json`:
```json
"chidepdicau": {
  "name": "Cấu hình 4 (Chị Đẹp Đi Câu @chidepdicau - Sub Karaoke & Giọng Nữ Cute)",
  "hashtags": [
    "#chidepdicau",
    "#cauca",
    "#chidep",
    "#gaidepcauca",
    "#fishing"
  ],
  "workflow": "gaidep_cauca",
  "render_profile": "gaidep_blur",
  "voice": "omni_nu_cute",
  "speed": 1.45,
  "drive_folder": "Đã Render/Chi_Dep_Di_Cau",
  "mask_mode": "blur_sub_black",
  "burn_sub": true,
  "show_title_card": false,
  "keep_bg_audio": true,
  "bg_volume": 0.30,
  "vocal_cut": true,
  "mlev": 0.04,
  "slev": 0.30,
  "mute_original_speech": false,
  "original_volume": 0.30
}
```

### B. Cấu hình Profile Giọng `omni_nu_cute`:
```json
"omni_nu_cute": {
  "label": "OmniVoice - Nữ Cute (giongnucute.wav)",
  "engine": "omnivoice",
  "mode": "clone",
  "model": "kjanh/KhanhTTS-OmniVoice",
  "ref_audio": "OmniVoice/voices/giongnucute.wav",
  "ref_text": "Chào mọi người nha! Mình thấy câu chuyện này cực kỳ thú vị và hài hước luôn.",
  "language": "vi",
  "num_step": 20,
  "guidance_scale": 2.0,
  "require_clone": true,
  "fallback_voice": "nu_tre",
  "speed": 1.45,
  "duration_match": {
    "adaptive": true,
    "max_speedup": 1.8,
    "minimum_gap_sec": 0.05
  }
}
```

---

## 2. NGUYÊN TẮC HÒA ÂM 3 LUỒNG TỰ ĐỘNG

Khi render video câu cá ngoài trời / vlog:
1. **Âm thanh sông nước thiên nhiên (Instrumental stem):** `70%` (`volume=0.70`)
2. **Âm thanh tiếng Trung của nhân vật gốc (Vocals stem):** `30%` (`volume=0.30`)
3. **Giọng thuyết minh tiếng Việt (OmniVoice Nữ Cute):** `100%` (`volume=1.00`)
4. **Sidechain Compression:** Nén nền tự động khi có giọng thuyết minh phát lên (`threshold=0.025:ratio=6:attack=15:release=250`), giúp giọng nói luôn nổi bật và trong trẻo.

Lệnh FFmpeg hòa âm tiêu chuẩn:
```bash
ffmpeg -y -i inst.wav -i vocal.wav -i voice.wav -filter_complex \
"[0:a]volume=0.70[ainst]; \
 [1:a]volume=0.30[avoc]; \
 [ainst][avoc]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[abackground]; \
 [abackground][2:a]sidechaincompress=threshold=0.025:ratio=6:attack=15:release=250[abg_ducked]; \
 [abg_ducked][2:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]; \
 [aout]alimiter=limit=0.92:attack=5:release=50:asc=1[afinal]" \
-map "[afinal]" -c:a pcm_s16le mixed_audio.wav
```

---

## 3. BẢNG TỔNG HỢP CÁC LỖI HAY GẶP & CÁCH XỬ LÝ

| # | Hiện tượng lỗi | Nguyên nhân gốc rễ | Cách xử lý & File liên quan |
|---|----------------|-------------------|-----------------------------|
| **1** | **Giọng AI đọc sai số** (đọc tiếng Anh như *zero four*, *one to one*, hoặc bỏ qua số) | Mô hình neural acoustic (OmniVoice/KhanhTTS) không có bộ text normalizer tích hợp như cloud TTS (Edge-TTS). Khi gặp số `04`, `5m4`, `0.4`, `1:1`, AI đọc sai. | Đã tích hợp `backend/vi_text_normalizer.py`. Toàn bộ số, kích thước cần câu (`5m4` ➔ *năm mét bốn*), số thập phân (`0.4` ➔ *không phẩy bốn*), tỉ lệ (`1:1` ➔ *một một*) được chuyển tự động sang chữ tiếng Việt trước khi tổng hợp. |
| **2** | **Sửa code nhưng giọng cũ vẫn phát ra** | Engine `voice_router` và `wuby_voice_v7` có cơ chế cache audio chunk theo hash text. Nếu text trước đó chưa qua normalizer, nó lấy file wav cũ từ cache. | Xóa cache: Xóa thư mục `workspace/.cache/wuby_voice_v7/` hoặc chạy script với `force=True`. |
| **3** | **OmniVoice bị treo khi tải mô hình** | Mô hình `kjanh/KhanhTTS-OmniVoice` kiểm tra kết nối HuggingFace Hub hoặc tải weights khi chạy trong môi trường sandbox chặn mạng. | Cho phép quyền mạng (`BypassSandbox: true`) hoặc đảm bảo weights đã được cache sẵn trong thư mục huggingface của máy. |
| **4** | **Phụ đề tiếng Việt bị lệch khỏi dải làm mờ** | Vùng nhận diện OCR phụ đề gốc nằm ở tọa độ `y=1300..1408` (CenterY = 1354px), nếu đặt MarginV mặc định (30-50px) chữ sẽ tụt xuống đáy video. | Tính MarginV chuẩn ASS: `dialogue_mv = int(round(1920 - 1354 - (42 * 0.45)))` = `547px`. Phụ đề sẽ nằm chính xác giữa dải blur. |
| **5** | **Tiêu đề gốc tiếng Trung ở đầu video không bị che** | Quét OCR chỉ tìm ở đáy màn hình mà không quét toàn màn hình ở 3-8 giây đầu. | Bật `intro_banner_service.generate_prerender_preview` quét toàn màn hình `0.0s - 8.0s` ➔ tự động tạo `banner.png` che khít tiêu đề gốc và hiển thị tiêu đề tiếng Việt. |
| **6** | **Âm thanh gốc quá to lấn át giọng thuyết minh** | Tách stem chưa cân bằng hoặc âm lượng vocal gốc để quá cao (> 50%). | Giảm âm lượng vocal gốc xuống `30%` (`volume=0.30`) và dùng sidechain compressor tự động giảm nền khi có tiếng nói. |
| **7** | **Lỗi `RuntimeWarning: Couldn't find ffmpeg or avconv` từ pydub** | Pydub không thấy ffmpeg trong PATH môi trường thực thi. | Sử dụng trực tiếp `video_merger._ffmpeg_executable()` hoặc chỉ định đường dẫn ffmpeg binary trong `sub_processor.py`. |

---

## 4. CÁCH THAY ĐỔI MẪU GIỌNG KHÁC TRONG TƯƠNG LAI

Nếu bạn muốn đổi sang một giọng nói mẫu khác (ví dụ: giọng nam trầm, giọng nữ miền Nam, giọng hài hước):
1. Chuẩn bị 1 file âm thanh mẫu `.wav` (từ 3 đến 8 giây, âm thanh sạch không dính nhạc nền).
2. Lưu file vào thư mục: `OmniVoice/voices/<ten_giong_moi>.wav`.
3. Mở file `backend/channels_config.json`, tìm đến `omni_nu_cute` (hoặc tạo profile mới):
   ```json
   "ref_audio": "OmniVoice/voices/<ten_giong_moi>.wav",
   "ref_text": "<Nội dung chính xác từng chữ được nói trong file wav mẫu>"
   ```
4. Chạy render lại, hệ thống sẽ tự động học ngữ điệu từ file mới.

---

## 5. THÔNG TIN BACKUP DỰ ÁN

* **Thư mục chứa backup:** `D:\0.1_FACE_BOOK\Lay video tiktok\backups\`
* **Lệnh tạo backup nhanh:**
  ```bash
  python tools/create_full_backup.py
  ```
* **Khôi phục (Restore):** Giải nén file zip trong thư mục `backups/` vào thư mục gốc `lay_video_tiktok` khi cần hoàn nguyên mã nguồn và cấu hình chuẩn.
