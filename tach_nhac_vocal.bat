@echo off
chcp 65001 >nul
title Tach Vocal va Nhac Nen - Audio Separator GPU
echo ===================================================================
echo     HE THONG TACH VOCAL / NHAC NEN (AUDIO-SEPARATOR GPU)
echo     Moi truong: D:\0.1_FACE_BOOK\Lay video tiktok\MOI_TRUONG\audio_sep_env
echo     Model: UVR-MDX-NET-Inst_HQ_3.onnx (MDX-Net ONNX GPU)
echo ===================================================================

if "%~1"=="" (
    echo.
    echo Huong dan:
    echo   1. Keo tha truc tiep file Audio/Video vao file batch nay.
    echo   Hoac
    echo   2. Nhap duong dan file can tach ben duoi:
    echo.
    set /p "INPUT_FILE=Nhap duong dan file: "
) else (
    set "INPUT_FILE=%~1"
)

if "%INPUT_FILE%"=="" (
    echo Khong co file nao duoc chon.
    pause
    exit /b 1
)

cd /d "%~dp0"
python separate_audio_cli.py "%INPUT_FILE%"

pause
