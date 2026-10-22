@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

REM Dedicated processes: FastAPI backend, Cloudflare Tunnel, and Telegram Bot
start "TikTok Backend 8005" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_backend.ps1"
start "TikTok Dedicated Tunnel" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_tunnel.ps1"
start "TikTok Telegram Bot" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_bot.ps1"
endlocal
