@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_EXE=HiMateSync.exe"
set "LEGACY_SETUP=HozoorSyncCustomer_Setup.exe"
set "FINAL_SETUP=HiMateSync_Setup.exe"

echo ================================================
echo HiMate Windows Setup Builder 0.4.5
echo ================================================

if not exist "hozoor_customer_app.py" (
    echo ERROR: hozoor_customer_app.py is missing.
    pause
    exit /b 1
)

if not exist "installer\HozoorSyncCustomer.iss" (
    echo ERROR: installer\HozoorSyncCustomer.iss is missing.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not available in PATH.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 goto :failed
python -m pip install -r requirements.txt
if errorlevel 1 goto :failed

if exist prepare_fonts.py python prepare_fonts.py

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Output rmdir /s /q Output
mkdir Output

python -m PyInstaller --noconfirm --clean --onefile --windowed --name HiMateSync --distpath "%cd%\dist" --workpath "%cd%\build" --specpath "%cd%" "%cd%\hozoor_customer_app.py"
if errorlevel 1 goto :failed

if not exist "dist\%APP_EXE%" (
    echo ERROR: dist\%APP_EXE% was not created.
    goto :failed
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo ERROR: Inno Setup 6 is not installed.
    echo Download: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

set "HIMATE_APP_VERSION=0.4.5"
set "HOZOOR_APP_VERSION=0.4.5"
"%ISCC%" "installer\HozoorSyncCustomer.iss"
if errorlevel 1 goto :failed

if not exist "Output\%LEGACY_SETUP%" (
    echo ERROR: Output\%LEGACY_SETUP% was not created.
    goto :failed
)

copy /y "Output\%LEGACY_SETUP%" "Output\%FINAL_SETUP%" >nul
if errorlevel 1 goto :failed

echo.
echo SUCCESS:
echo %cd%\Output\%FINAL_SETUP%
pause
exit /b 0

:failed
echo.
echo BUILD FAILED.
pause
exit /b 1
