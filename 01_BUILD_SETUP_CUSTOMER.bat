\
@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ==========================================================
echo Hozoor Sync - Final Customer Installer Builder
echo Stable GitHub / Fixed Output
echo ==========================================================
echo.
echo Final output:
echo Output\HozoorSyncCustomer_Setup.exe
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Could not install requirements.
    pause
    exit /b 1
)

python prepare_fonts.py
python make_build_config.py
if errorlevel 1 (
    echo ERROR: Could not generate build config.
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --name HozoorSyncCustomer hozoor_customer_app.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
    where ISCC.exe >nul 2>nul
    if not errorlevel 1 set "ISCC=ISCC.exe"
)
if "%ISCC%"=="" (
    echo ERROR: Inno Setup was not found.
    pause
    exit /b 1
)

if not exist "Output" mkdir "Output"
for /f "usebackq delims=" %%v in ("VERSION.txt") do set "HOZOOR_APP_VERSION=%%v"
"%ISCC%" "installer\HozoorSyncCustomer.iss"
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    pause
    exit /b 1
)

echo.
echo Done:
echo %cd%\Output\HozoorSyncCustomer_Setup.exe
explorer "%cd%\Output"
pause
