@echo off
chcp 65001 >nul
cd /d "%~dp0"

 echo.
 echo ==========================================================
 echo HiMate Sync - Customer Installer Builder 0.4.3
 echo ==========================================================
 echo.
 echo Final output:
 echo Output\HiMateSync_Setup.exe
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
if errorlevel 1 (
    echo ERROR: Could not prepare fonts.
    pause
    exit /b 1
)

python make_build_config.py
if errorlevel 1 (
    echo ERROR: Could not generate build config.
    pause
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller --noconfirm --clean --onefile --windowed --name HiMateSync hozoor_customer_app.py
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)
if not exist "dist\HiMateSync.exe" (
    echo ERROR: dist\HiMateSync.exe was not created.
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
for /f "usebackq delims=" %%v in ("VERSION.txt") do set "HIMATE_APP_VERSION=%%v"
set "HOZOOR_APP_VERSION=%HIMATE_APP_VERSION%"
"%ISCC%" "installer\HozoorSyncCustomer.iss"
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    pause
    exit /b 1
)
if not exist "Output\HiMateSync_Setup.exe" (
    echo ERROR: Output\HiMateSync_Setup.exe was not created.
    pause
    exit /b 1
)

 echo.
 echo Done:
 echo %cd%\Output\HiMateSync_Setup.exe
explorer "%cd%\Output"
pause
