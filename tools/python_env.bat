@echo off
if defined WUBY_PYTHON goto check
if exist "%~dp0..\.venv\Scripts\python.exe" set "WUBY_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if defined WUBY_PYTHON goto check
if exist "%~dp0..\venv\Scripts\python.exe" set "WUBY_PYTHON=%~dp0..\venv\Scripts\python.exe"
if defined WUBY_PYTHON goto check
if defined VIRTUAL_ENV set "WUBY_PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
if defined WUBY_PYTHON goto check
echo No project venv found. Set WUBY_PYTHON to your existing environment python.exe.
echo This installer will not guess a global Python and replace your CUDA environment.
exit /b 2
:check
if not exist "%WUBY_PYTHON%" (echo WUBY_PYTHON does not exist. & exit /b 2)
exit /b 0
