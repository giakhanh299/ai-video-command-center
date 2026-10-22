# ZeroTTS Voice Integration - V3

## Mục tiêu

Pipeline giờ có thể tự đọc `*.srt` tiếng Việt và sinh một WAV khớp timeline bằng ZeroTTS. Nếu `voice_audio=None`, voice sẽ được tạo tự động theo `config/channels/*.json`, cache theo từng câu, rồi mix với audio nền khi render video.

## Chế độ 1 - Local cute voice (mặc định)

`config/channels/wibu_cute.json` dùng:

```json
"voice": {
  "engine": "zerotts",
  "backend": "local",
  "voice": "hamy",
  "auto_generate_from_srt": true
}
```

`hamy` là preset nữ trẻ / hoạt hình / cao / biểu cảm và được dùng làm profile cute mặc định.

Chạy thử voice riêng:

```bash
python render_voice.py sample_data/subtitles_vi.srt output/test_zerotts.wav
```

Chạy cả video:

```bash
python run_demo.py
```

Lần đầu ZeroTTS local sẽ tải weights về cache của Hugging Face. Các lần sau dùng lại model cache và cache từng câu TTS của project.

## Chế độ 2 - Local cloned voice pack (khuyến nghị khi đã clone)

ZeroTTS public không có voice encoder để tự biến WAV tham chiếu thành clone. Sau khi tạo voice trong ZeroWeight Audio Studio, runtime mới có thể dùng voice pack tải về.

Nếu bạn tải được pack dạng ZIP, đặt vào project, ví dụ:

```text
voices/my-voice.zip
```

Dùng config mẫu:

```text
config/channels/wibu_cute_clone_local_pack.example.json
```

với:

```json
"custom_voice_pack": "voices/my-voice.zip"
```

Pipeline sẽ gọi `tts.add_voices(...)`, cài pack một lần vào runtime và dùng voice đó cho các cue. Nếu runtime ZeroTTS đang dùng chưa có `add_voices()`, cập nhật `zerotts` hoặc dùng `.npz` như chế độ tương thích bên dưới.

### Tương thích `.npz`

Nếu bạn đã có trực tiếp latent `voice.npz`, dùng:

```text
config/channels/wibu_cute_clone_local_npz.example.json
```

```json
"custom_voice_npz": "voices/my_speaker/voice.npz"
```

Cả `custom_voice_pack` và `custom_voice_npz` đều ưu tiên hơn `voice: hamy`.

## Chế độ 3 - Hosted cloned voice ID

Nếu đã tạo voice trong ZeroWeight Audio Studio, dùng voice ID đó qua hosted streaming API.

1. Đặt API key trên Windows PowerShell:

```powershell
$env:ZEROWEIGHT_API_KEY="YOUR_KEY"
```

2. Copy file:

```text
config/channels/wibu_cute_cloned_api.example.json
```

thành một config riêng và thay:

```json
"backend": "api",
"voice_id": "vc_xxxxx"
```

3. Chạy:

```bash
python run_batch.py input_videos output_videos --config config/channels/my_clone.json
```

API key không được ghi cứng trong source code hay commit vào Git.

## Duration matching

Mỗi cue SRT được sinh riêng. Nếu câu đọc dài hơn slot subtitle, pipeline dùng FFmpeg `atempo` để tăng tốc vừa phải mà không đổi pitch. Mặc định không cố kéo dài những câu ngắn vì kéo quá nhiều thường nghe giả.

```json
"duration_match": {
  "enabled": true,
  "target_fill_ratio": 0.92,
  "base_speed": 1.04,
  "max_speedup": 1.4,
  "max_slowdown": 1.1,
  "stretch_short": false
}
```

Nếu câu vẫn quá dài sau giới hạn `max_speedup`, phần vượt slot sẽ bị cắt khi đặt lên timeline. Tốt nhất là làm câu dịch ngắn gọn trước TTS.

## Cache

Audio từng câu được cache theo nội dung + voice + sampling parameters. Đổi font/title/OCR không làm ZeroTTS đọc lại. Đổi voice hoặc thông số TTS sẽ tự tạo cache key mới.

## Override bằng WAV có sẵn

Nếu gọi `process_wuby_video(..., voice_audio="abc.wav")`, WAV đó luôn được ưu tiên và ZeroTTS không chạy.

Trong batch, mặc định không dùng sidecar WAV. Nếu muốn dùng `name.wav` thay ZeroTTS:

```bash
python run_batch.py input output --use-sidecar-wav
```
