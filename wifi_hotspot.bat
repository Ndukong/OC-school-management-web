@echo off
title School Management System - WiFi Hotspot Setup
cd /d "%~dp0"
echo ============================================
echo   WiFi Hotspot Setup
echo ============================================
echo.
echo This creates a WiFi hotspot that phones can
echo connect to in order to access the system.
echo.
echo Requirements:
echo   - Windows 10/11 with WiFi adapter
echo   - Run this script as Administrator
echo.
echo Press any key to continue (as Admin)...
pause >nul

:: Check if running as admin
net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] This script must be run as Administrator.
    echo Right-click and select "Run as administrator".
    pause
    exit /b 1
)

echo.
echo Configuring WiFi hotspot...
echo.

:: Stop any existing hosted network
netsh wlan stop hostednetwork >nul 2>&1

:: Create hosted network
netsh wlan set hostednetwork mode=allow ssid=SchoolManager key=school123
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Could not create hosted network.
    echo         Your WiFi adapter may not support hosted networks.
    echo         Try using a USB WiFi adapter instead.
    pause
    exit /b 1
)

echo.
echo Hosted network created successfully!
echo   Network name: SchoolManager
echo   Password:     school123
echo.
echo Starting the hosted network...
netsh wlan start hostednetwork

echo.
echo ============================================
echo   WiFi Hotspot is now ACTIVE
echo ============================================
echo.
echo   Phones connect to: SchoolManager
echo   Password:          school123
echo.
echo   Then open browser and go to:
echo   http://192.168.137.1:8000
echo.
echo   (192.168.137.1 is the default hotspot IP)
echo.
echo   To stop the hotspot: netsh wlan stop hostednetwork
echo.
echo Press any key to stop the hotspot...
pause >nul
netsh wlan stop hostednetwork
echo Hotspot stopped.
pause
