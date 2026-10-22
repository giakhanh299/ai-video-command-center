@echo off
chcp 65001 >nul
echo ======================================================================
echo 🚀 CÀI ĐẶT MÔI TRƯỜNG CHO MODULE TIỂU WUBY (IN-PLACE OCR & SUB OVERLAY)
echo ======================================================================

echo.
echo [1/3] Kiểm tra Python...
python --version
if errorlevel 1 (
    echo [LỖI] Chưa cài đặt Python! Vui lòng cài Python 3.10 trở lên.
    pause
    exit /b 1
)

echo.
echo [2/3] Cài đặt các thư viện từ requirements.txt...
pip install -r requirements.txt

echo.
echo [3/3] Kiểm tra FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [CẢNH BÁO] Chưa tìm thấy FFmpeg trong PATH!
    echo Vui lòng tải FFmpeg tại https://ffmpeg.org và thêm vào biến môi trường PATH.
) else (
    echo [OK] FFmpeg đã sẵn sàng!
)

echo.
echo ======================================================================
echo ✅ CÀI ĐẶT HOÀN TẤT! Bạn có thể chạy: python run_demo.py
echo ======================================================================
pause
