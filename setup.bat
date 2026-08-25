@echo off
echo ============================================
echo   School Management System - First Setup
echo ============================================
echo.
echo This script will:
echo   1. Check Python installation
echo   2. Create virtual environment
echo   3. Install all dependencies
echo   4. Run database migrations
echo   5. Seed default Cameroon subjects
echo   6. Collect static files
echo   7. Generate the activation wizard shortcut
echo.
pause

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/7] Checking Python version...
python --version

:: Create virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo [2/7] Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [2/7] Virtual environment already exists. Skipping.
)

:: Activate and install
call .venv\Scripts\activate.bat

echo [3/7] Installing dependencies...
.venv\Scripts\pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [4/7] Running database migrations...
python manage.py migrate
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Migration failed.
    pause
    exit /b 1
)

echo [5/7] Seeding default Cameroon subjects and configuration...
python manage.py seed_default_config --auto
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Seed data skipped (may already exist).
)

echo [6/7] Collecting static files...
python manage.py collectstatic --noinput

echo [7/7] Setup complete!
echo.
echo ============================================
echo   NEXT STEPS
echo ============================================
echo   1. Open http://127.0.0.1:8000 in your browser
echo      (Run: start_server.bat)
echo   2. The activation wizard will appear.
echo   3. Enter your product key to activate.
echo   4. Configure your school name and details.
echo   5. Create your admin account.
echo   6. Start entering student data!
echo.
echo For WiFi hotspot sharing:
echo   Run: wifi_hotspot.bat
echo.
echo For automatic daily backups:
echo   Run: backup.bat
echo.
pause
