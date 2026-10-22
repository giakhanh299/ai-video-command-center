@echo off
setlocal
cd /d "%~dp0"
call tools\python_env.bat
if errorlevel 1 (pause & exit /b 1)
"%WUBY_PYTHON%" -m pytest -q
if errorlevel 1 (pause & exit /b 1)
"%WUBY_PYTHON%" -m wuby_studio.cli doctor
pause
