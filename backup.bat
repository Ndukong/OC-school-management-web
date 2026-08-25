@echo off
title School Management System - Backup
cd /d "%~dp0"
echo ============================================
echo   Creating Backup
echo ============================================
echo.

call .venv\Scripts\activate.bat

echo Backing up database and media files...
python manage.py create_backup --type full --notes "Manual backup from backup.bat"
echo.
echo Backup files are saved in the 'backups' folder.
echo.

:: Also create a dated copy for safety
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set datetime=%%I
set FILEDATE=%datetime:~0,4%%datetime:~4,2%%datetime:~6,2%
set FILETIME=%datetime:~8,2%%datetime:~10,2%%datetime:~12,2%
echo Latest backup timestamp: %FILEDATE%_%FILETIME%
echo.
pause
