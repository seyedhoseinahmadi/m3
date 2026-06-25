\
@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install -r requirements.txt
python make_build_config.py
python -m PyInstaller --noconfirm --clean --onefile --windowed --name HozoorSyncCustomer hozoor_customer_app.py

echo.
echo EXE:
echo %cd%\dist\HozoorSyncCustomer.exe
pause
