@echo off
title School Management System - Starting Server
cd /d "%~dp0"
echo ============================================
echo   School Management System v1.0
echo ============================================
echo.
echo Starting server on all network interfaces (port 8000)...
echo.
echo   Laptop URL:  http://127.0.0.1:8000
echo   Phone URL:   http://[your-laptop-ip]:8000
echo
echo   To find your laptop IP: run ipconfig
echo   (Look for "IPv4 Address" under WiFi adapter)
echo.
echo Press Ctrl+C to stop the server.
echo ============================================
echo.
call .venv\Scripts\activate.bat
python manage.py runserver 0.0.0.0:8000
pause
