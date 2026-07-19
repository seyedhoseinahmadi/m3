@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python prepare_fonts.py
if errorlevel 1 goto :failed
if errorlevel 1 exit /b 1
python make_build_config.py
if errorlevel 1 exit /b 1
python hozoor_customer_app.py
pause
