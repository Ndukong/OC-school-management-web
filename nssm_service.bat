@echo off
title School Management System - Windows Service Setup
cd /d "%~dp0"
echo ============================================
echo   Windows Service (NSSM) Setup
echo ============================================
echo.
echo This installs the server as a Windows service
echo that starts automatically on boot.
echo.
echo Requirements:
echo   - NSSM (Non-Sucking Service Manager) installed
echo     Download: https://nssm.cc/download
echo     Place nssm.exe in this folder or add to PATH
echo   - Run this script as Administrator
echo.

:: Check for admin
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Run as Administrator.
    pause
    exit /b 1
)

:: Check for nssm
where nssm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if exist "%~dp0nssm.exe" (
        set "NSSM=%~dp0nssm.exe"
    ) else (
        echo [ERROR] nssm.exe not found.
        echo Download from https://nssm.cc/download
        echo and place nssm.exe in this folder.
        pause
        exit /b 1
    )
) else (
    set "NSSM=nssm"
)

echo Select action:
echo   [1] Install service
echo   [2] Remove service
echo   [3] Start service
echo   [4] Stop service
echo   [5] View service status
echo.
set /p ACTION="Enter choice (1-5): "

set SERVICE_NAME=SchoolManagementSystem

if "%ACTION%"=="1" (
    echo.
    echo Installing service...
    "%NSSM%" install %SERVICE_NAME% "%~dp0.venv\Scripts\python.exe"
    "%NSSM%" set %SERVICE_NAME% AppParameters "%~dp0manage.py runserver 0.0.0.0:8000"
    "%NSSM%" set %SERVICE_NAME% AppDirectory "%~dp0"
    "%NSSM%" set %SERVICE_NAME% DisplayName "School Management System"
    "%NSSM%" set %SERVICE_NAME% Description "School Management System - WiFi Server"
    "%NSSM%" set %SERVICE_NAME% Start SERVICE_AUTO_START
    "%NSSM%" set %SERVICE_NAME% AppStdout "%~dp0logs\service_output.log"
    "%NSSM%" set %SERVICE_NAME% AppStderr "%~dp0logs\service_error.log"
    "%NSSM%" set %SERVICE_NAME% AppRotateFiles 1
    "%NSSM%" set %SERVICE_NAME% AppRotateBytes 10485760
    if not exist "%~dp0logs" mkdir "%~dp0logs"
    echo.
    echo Service installed successfully!
    echo Start it now with option [3]
) else if "%ACTION%"=="2" (
    echo.
    "%NSSM%" stop %SERVICE_NAME%
    "%NSSM%" remove %SERVICE_NAME% confirm
    echo Service removed.
) else if "%ACTION%"=="3" (
    echo.
    "%NSSM%" start %SERVICE_NAME%
    echo Service started.
    echo Open http://127.0.0.1:8000
) else if "%ACTION%"=="4" (
    echo.
    "%NSSM%" stop %SERVICE_NAME%
    echo Service stopped.
) else if "%ACTION%"=="5" (
    echo.
    "%NSSM%" status %SERVICE_NAME%
)
echo.
pause
