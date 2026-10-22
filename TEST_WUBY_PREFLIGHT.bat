@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Keo file video Wuby vao BAT nay hoac chay:
  echo   TEST_WUBY_PREFLIGHT.bat "D:\duong_dan\video.mp4"
  pause
  exit /b 1
)
python test_wuby_preflight_video.py "%~1"
pause
