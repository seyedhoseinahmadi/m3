@echo off
chcp 65001 >nul
cd /d "%~dp0"

setlocal
set "APP_EXE=HiMateSync.exe"
set "SETUP_EXE=HiMateSync_Setup.exe"

echo.
echo ==========================================================
echo HiMate Sync - Complete Customer Installer Builder v0.4.4
echo ==========================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Could not install requirements.
    pause
    exit /b 1
)

if exist prepare_fonts.py python prepare_fonts.py
python make_build_config.py
if errorlevel 1 (
    echo ERROR: Could not generate build config.
    pause
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Output rmdir /s /q Output
mkdir Output

python -m PyInstaller --noconfirm --clean --onefile --windowed --name HiMateSync --distpath "%cd%\dist" --workpath "%cd%\build" --specpath "%cd%" "%cd%\hozoor_customer_app.py"
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

if not exist "dist\%APP_EXE%" (
    echo ERROR: dist\%APP_EXE% was not created.
    dir /s dist
    pause
    exit /b 1
)

copy /y "dist\%APP_EXE%" "Output\%APP_EXE%" >nul
if not exist "Output\%APP_EXE%" (
    echo ERROR: Could not stage Output\%APP_EXE%.
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
    echo ERROR: Inno Setup 6 was not found.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%v in ("VERSION.txt") do set "HIMATE_APP_VERSION=%%v"
set "HOZOOR_APP_VERSION=%HIMATE_APP_VERSION%"

"%ISCC%" "installer\HozoorSyncCustomer.iss"
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    pause
    exit /b 1
)

if not exist "Output\%SETUP_EXE%" (
    echo ERROR: Output\%SETUP_EXE% was not created.
    pause
    exit /b 1
)

echo.
echo Build completed successfully:
echo %cd%\Output\%SETUP_EXE%
explorer "%cd%\Output"
pause
endlocal
