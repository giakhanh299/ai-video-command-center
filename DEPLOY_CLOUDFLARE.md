# Cloudflare deployment

## Backend qua Named Tunnel

Backend: `backend/main.py`, FastAPI/uvicorn tại `127.0.0.1:8005`.

1. Bảo đảm Named Tunnel `tiktok-dubber` đã tồn tại và DNS route của `api-tiktok.giakhanh.xyz` trỏ vào tunnel.
2. Sao chép `cloudflare/config.yml.example` sang thư mục cấu hình cloudflared, thay `TUNNEL_UUID`, `YOUR_USER`; giữ credentials JSON ngoài project.
3. Chạy backend: `uvicorn main:app --host 127.0.0.1 --port 8005` trong `backend`.
4. Chạy tunnel: `cloudflared tunnel --config <duong-dan-config.yml> run tiktok-dubber`.
5. Kiểm tra: `https://api-tiktok.giakhanh.xyz/api/health` trả `{"status":"ok"}`.

`startup.bat` hiện khởi động backend và Named Tunnel theo tên `tiktok-dubber`.

## Frontend Cloudflare Pages

Frontend tĩnh: thư mục `frontend`; không có build step.

- Git integration: Build command để trống; Build output directory: `frontend`.
- Direct Upload: tải nội dung thư mục `frontend` lên Pages.
- Gắn custom domain mong muốn trong Pages. Preview/production Pages được backend chấp nhận qua `*.pages.dev`; `giakhanh.xyz` và `www.giakhanh.xyz` được chấp nhận.
- Nếu dùng domain frontend khác, đặt `CORS_ORIGINS` khi chạy backend, ví dụ `CORS_ORIGINS=https://app.example.com` (nhiều origin phân tách bằng dấu phẩy).

Frontend production gọi cố định `https://api-tiktok.giakhanh.xyz`; localhost dùng same-origin để giữ cách chạy backend phục vụ frontend hiện tại.

## Bao mat secret (ban cap nhat 2026-09)

Khong de token/secret truc tiep trong `wrangler.jsonc`. Chay trong `cloudflare/bot-worker`:

```powershell
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TIKHUB_API_TOKEN
npx wrangler secret put GDRIVE_CLIENT_SECRET
npx wrangler secret put GDRIVE_REFRESH_TOKEN
```

`wrangler.jsonc` chi giu cac bien khong nhay cam. File ZIP cap nhat cung khong kem `backend/.env` hay `gdrive_token.json`; giu lai cac file secret hien tai tren may cua ban khi copy cap nhat.
