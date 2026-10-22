# Channel / Workflow / Render Profile v2

## 1. Moi Telegram Chat ID la mot kenh rieng

Trong `channels_config.json`, them vao `channels`:

```json
"-1001234567890": {
  "name": "Vũ Trụ Phim",
  "workflow": "film_review_black",
  "voice": "omni_nam_review",
  "speed": 1.3,
  "drive_folder": "Đã Render/Vu_Tru_Phim",
  "asset_folder": "Vũ Trụ Phim"
}
```

Sau khi sua JSON, tren Telegram go `/reload_config`.

## 2. Logo + cover tu dong theo kenh

Tao thu muc:

```text
channel_assets/
  Vũ Trụ Phim/
    logo.png
    cover.jpg
```

- `logo.png`: watermark nhe chay suot video, mac dinh bottom-right, opacity 0.12.
- `cover.jpg`: chen full-frame 1.2 giay dau video.
- Thieu logo/cover thi bo qua, khong loi job.

Override rieng kenh:

```json
"render": {
  "logo": {
    "opacity": 0.08,
    "position": "bottom_center",
    "width_ratio": 0.15
  },
  "cover": {
    "duration": 1.8,
    "fit": "cover"
  }
}
```

Vi tri logo ho tro: `bottom_right`, `bottom_left`, `bottom_center`, `top_right`, `top_left`, `top_center`, `center`.

## 3. OmniVoice theo kenh

Voice clone duoc khai bao o `voice_profiles`:

```json
"omni_nam_review": {
  "label": "OmniVoice - Nam review clone",
  "engine": "omnivoice",
  "mode": "clone",
  "ref_audio": "giongnamreviewdao.mp3",
  "ref_text": "",
  "language": "vi",
  "num_step": 24,
  "fallback_voice": "nam_minh"
}
```

`ref_audio` tu dong tim trong `voice_samples/`.

Neu `ref_text` de rong, OmniVoice se tu ASR file mau lan dau, sau do adapter cache voice-clone prompt trong RAM. De khoi dong nhanh hon, co the dien chinh transcript cua audio mau vao `ref_text`.

Lenh Telegram:

```text
/set_voice omni_nam_review
/set_voice omni_nu_tre
/set_voice omni_nu_tram
```

Neu OmniVoice loi/model chua co, pipeline tu fallback ve Edge voice da khai bao trong `fallback_voice`.

## 4. Workflow va render profile

`workflow` chon mot `render_profile`.

Vi du review phim:

```text
film_review_black
  -> review_film_black
  -> che den toan bo dai tren/duoi
  -> title Viet tren dai den
  -> sub Viet tren dai den duoi
  -> logo theo kenh
  -> cover theo kenh
```

Doi workflow cho mot kenh:

```text
/set_workflow film_review_black
/set_workflow film_review_blur
/set_workflow sub_only_clean
```

Hoac chi override mot video:

```text
https://... workflow=film_review_blur voice=omni_nu_tram speed=1.25
```

## 5. Render profile custom

Co the sua cac thong so sau ma khong can sua Python:

- top/bottom black bar ratio
- font title / subtitle
- mau chu
- outline
- title persistent hay 6s
- blur strength
- logo opacity / position / size
- cover duration / fit
- NVENC preset / CQ / bitrate

De tao style moi: copy mot block trong `render_profiles`, dat ten moi, sau do tao/doi `workflow` tro vao profile do.

## 6. Bao mat khi cap nhat

Ban ZIP phan phoi khong kem `.env` va khong nen kem token/API secret. Khi copy code ve `D:/0.1_FACE_BOOK/Lay video tiktok`, GIU LAI file `backend/.env` hien tai cua may ban.
