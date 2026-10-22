@echo off
setlocal
cd /d "%~dp0"
rem Agent outbound 443: PC mo NO inbound port. Agent chi goi ra HTTPS 443
rem toi Command Center API de cho/nhan lenh (claim). Xem DEPLOY_CLOUDFLARE.md.
if not exist ".venv-command-center\Scripts\python.exe" (
  echo Chua co .venv-command-center. Xem docs\COMMAND_CENTER_LOCAL.md muc chuan bi moi truong.
  pause & exit /b 1
)
if not defined CC_API_URL set "CC_API_URL=https://api.giakhanh.xyz"
if not defined CC_AGENT_ID (
  echo Thieu bien moi truong CC_AGENT_ID ^(UUID cua Agent tren he thong^).
  pause & exit /b 1
)
if not defined CC_AGENT_TOKEN (
  echo Thieu bien moi truong CC_AGENT_TOKEN. Token chi luu tai PC, khong dua len Git hay frontend.
  pause & exit /b 1
)
if not defined CC_STORAGE_ROOT set "CC_STORAGE_ROOT=%CD%\workspace\command_center_dev\storage"
".venv-command-center\Scripts\python.exe" -B -m command_center.agent --loop --url "%CC_API_URL%" --agent-id "%CC_AGENT_ID%" --storage-root "%CC_STORAGE_ROOT%"
pause
