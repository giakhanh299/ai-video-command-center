@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Keo file video vao BAT nay hoac chay:
  echo   TEST_CLONE_PHIM_GIONG.bat "D:\duong_dan\phim.mp4"
  pause
  exit /b 1
)
python test_movie_clone_voice_match.py "%~1"
pause
