@echo off
setlocal
cd /d "%~dp0"
echo STOP the bot, scheduled tasks and all render workers first.
echo Extract this patch OUTSIDE the existing project. Do not copy over settings blindly.
set /p "TARGET=Existing project ROOT (contains backend): "
set /p "PYEXE=Full path to that project's existing python.exe: "
"%PYEXE%" apply_wuby_v7.py --target "%TARGET%"
if errorlevel 1 (pause & exit /b 1)
set /p "CONFIRM=Type APPLY after reviewing the dry run: "
if /I not "%CONFIRM%"=="APPLY" exit /b 0
"%PYEXE%" apply_wuby_v7.py --target "%TARGET%" --apply
pause
