# OC-011 - Multi Channel Workflow + OmniVoice + Branding

## Da them

1. `channels_config.json` schema v2:
   - `channels`
   - `presets`
   - `voice_profiles`
   - `workflows`
   - `render_profiles`
2. Deep merge nested config, nen moi kenh co the override chi 1-2 thong so ma khong mat phan con lai.
3. OmniVoice clone voice theo tung kenh:
   - sample tu `voice_samples/`
   - cache voice clone prompt
   - GPU concurrency = 1 cho OmniVoice
   - fallback sang Edge voice neu clone/model loi
4. Branding theo kenh:
   - tu tim `channel_assets/<ten kenh>/logo.png`
   - tu tim `channel_assets/<ten kenh>/cover.jpg`
   - logo opacity/position/size custom JSON
   - cover intro duration/fit custom JSON
5. Render profile:
   - font/mau/outline title
   - font/mau/outline subtitle
   - top/bottom bar ratio
   - black/blur/none
   - NVENC preset/CQ/bitrate
6. Telegram:
   - `/set_voice` doc dong tu JSON, gom ca OmniVoice
   - `/set_workflow`
   - `/kenh` hien workflow/render profile/logo/cover
   - inline override `workflow=... voice=... speed=... mask=...`
7. Bao mat:
   - bo hard-coded Telegram token khoi `telegram_bot.py`
   - ban ZIP khong kem `.env`, Google token hoac Cloudflare secrets.

## Cach cap nhat tren Windows

1. Backup `D:/0.1_FACE_BOOK/Lay video tiktok` hien tai.
2. Giu lai `backend/.env` hien tai cua may.
3. Giai nen ZIP cap nhat de ghi de source.
4. Chay neu can OmniVoice:

```powershell
cd "D:\0.1_FACE_BOOK\Lay video tiktok"
.\install_omnivoice.ps1
```

5. Tao logo/cover theo kenh, vi du:

```text
D:\0.1_FACE_BOOK\Lay video tiktok\channel_assets\Vũ Trụ Phim\logo.png
D:\0.1_FACE_BOOK\Lay video tiktok\channel_assets\Vũ Trụ Phim\cover.jpg
```

6. Sua Chat ID trong `backend/channels_config.json` neu them kenh moi.
7. Khoi dong bot va go `/reload_config`.
8. Kiem tra `/kenh`.

## Tinh nang nen lam tiep

- Job DB SQLite: luu chat_id/thread_id/config snapshot cho moi video, restart khong mat job.
- GPU queue: Whisper/OmniVoice/ComfyUI khong tranh VRAM.
- Telegram inline keyboard de chon workflow/voice thay vi go lenh.
- Watch folder theo kenh: moi thu muc Drive map vao 1 Channel Profile thay vi Drive watcher dung chat dau tien.
- Preview 10-15 giay: render nhanh de duyet style truoc khi render ca tap.
- Version render profile: `review_film_black_v1`, `v2` de video cu co the tai lap dung style.
- Auto QC: kiem tra duration, audio, frame den, subtitle bi tran, file size truoc khi bao hoan thanh.
- ComfyUI step: cho workflow sau nay chen `vton`, `upscale`, `background_replace` ma khong doi Telegram bot.
