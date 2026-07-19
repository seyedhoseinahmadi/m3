@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python prepare_fonts.py
if errorlevel 1 exit /b 1
python make_build_config.py
if errorlevel 1 exit /b 1
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller --noconfirm --clean --onefile --windowed --name HiMateSync hozoor_customer_app.py
if errorlevel 1 exit /b 1
if not exist "dist\HiMateSync.exe" (
    echo ERROR: dist\HiMateSync.exe was not created.
    pause
    exit /b 1
)

echo.
echo EXE:
echo %cd%\dist\HiMateSync.exe
pause
