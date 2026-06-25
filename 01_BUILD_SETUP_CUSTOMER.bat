\
@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ==========================================================
echo Hozoor Sync - Final Customer Installer Builder
echo Version: CUSTOMER-FINAL-INSTALLER-0.2.5
echo ==========================================================
echo.
echo Output will be a market-ready Windows installer:
echo Output\HozoorSyncCustomer_Setup_v0_2_5.exe
echo.
echo This app is server-bound, not device-bound.
echo Device code is read from the hardware device.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python 3.10+ and enable "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/7] Python version:
python --version

echo.
echo [2/7] Installing Python requirements...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Could not install requirements.
    pause
    exit /b 1
)

echo.
echo [3/7] Generating server-bound config...
python make_build_config.py
if errorlevel 1 (
    echo ERROR: Could not generate build config.
    pause
    exit /b 1
)

echo.
echo [4/7] Building Windows EXE with PyInstaller...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name HozoorSyncCustomer hozoor_customer_app.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [5/7] Finding Inno Setup compiler...
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    where ISCC.exe >nul 2>nul
    if not errorlevel 1 set "ISCC=ISCC.exe"
)

if "%ISCC%"=="" (
    echo ERROR: Inno Setup was not found.
    echo Download and install Inno Setup 6, then run this file again.
    echo https://jrsoftware.org/isinfo.php
    pause
    exit /b 1
)

echo Inno Setup compiler:
echo %ISCC%

echo.
echo [6/7] Building Setup.exe...
if not exist "Output" mkdir "Output"
"%ISCC%" "installer\HozoorSyncCustomer.iss"
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    pause
    exit /b 1
)

echo.
echo [7/7] Done.
echo.
echo Final installer:
echo %cd%\Output\HozoorSyncCustomer_Setup_v0_2_5.exe
echo.
explorer "%cd%\Output"
pause
