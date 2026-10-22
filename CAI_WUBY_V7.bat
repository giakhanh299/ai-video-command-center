@echo off
setlocal
cd /d "%~dp0"
call tools\python_env.bat
if errorlevel 1 (pause & exit /b 1)
"%WUBY_PYTHON%" tools\install_dependencies.py
set /p "CONFIRM=Install the listed missing packages? Type INSTALL: "
if /I not "%CONFIRM%"=="INSTALL" exit /b 0
"%WUBY_PYTHON%" tools\install_dependencies.py --apply
if errorlevel 1 (pause & exit /b 1)
"%WUBY_PYTHON%" tools\install_free_assets.py --font
if errorlevel 1 echo Font download failed. Configure font_path to your licensed local font.
"%WUBY_PYTHON%" -m wuby_studio.cli doctor
pause
