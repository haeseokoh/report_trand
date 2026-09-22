@echo off
chcp 65001 > nul
title Report Trend Intelligence

echo ========================================================
echo   Report Trend Intelligence Dashboard
echo ========================================================
echo.

cd /d "%~dp0"

set PYTHON_CMD=
if exist "%USERPROFILE%\.pyenv\pyenv-win\versions\3.12.10\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\.pyenv\pyenv-win\versions\3.12.10\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
) else (
    set PYTHON_CMD=python
)

echo [*] Starting Web Dashboard at http://localhost:8000 ...
echo [*] Please wait a moment...
echo.

call "%PYTHON_CMD%" main.py --server-only --port 8000

if errorlevel 1 (
    echo.
    echo [ERROR] Server encountered an error.
    pause
)
