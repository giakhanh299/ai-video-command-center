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

## Che do Agent outbound 443 (quyet dinh 2026-10-22, khuyen nghi cho Command Center)

PC khong mo cong vao nao cho Command Center: khong can Named Tunnel tro vao 8005/8016,
khong mo port tren router/firewall. PC chi chay Agent o che do cho lenh va tu goi ra
bang HTTPS cong 443 toi API de nhan (claim) cong viec, bao tien do va ket qua.

1. API + PostgreSQL phai dat tren may chu NGOAI PC (VPS/Docker) sau HTTPS cong 443
   (reverse proxy, hoac Tunnel gan tren chinh may chu do). Frontend Cloudflare Pages
   dat `apiBase` ve `https://<api-host>/api/v1`.
2. Tren PC, dat bien moi truong: `CC_API_URL=https://<api-host>`, `CC_AGENT_ID=<UUID>`,
   `CC_AGENT_TOKEN=<token cua Agent, chi luu tai PC>`, tuy chon `CC_STORAGE_ROOT`
   va `CC_AGENT_POLL_SECONDS` (mac dinh 5 giay).
3. Chay Agent cho lenh tren PC: `CHAY_AGENT_443.bat` (goi
   `python -m command_center.agent --loop`). Agent tu choi URL http tu xa va
   URL https dung cong khac 443 (`OUTBOUND_443_ONLY`); http chi con duoc chap nhan
   cho loopback khi phat trien local.
4. Tunnel `tiktok-dubber` (cong 8005) chi con phuc vu trang long tieng cu.
   Tat ingress cua tunnel khi da chuyen han sang mo hinh nay.

Gioi han con lai: Agent va API hien van phai dung chung storage root, transport file
cho Agent remote chua lam (xem `docs/ARCHITECTURE.md`). Chua coi mo hinh nay la
production cho video lon cho toi khi co duong truyen file qua 443.
