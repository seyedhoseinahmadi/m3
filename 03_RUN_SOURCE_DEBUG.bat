\
@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -m pip install -r requirements.txt
python prepare_fonts.py
python make_build_config.py
python hozoor_customer_app.py
pause
