@echo off
REM Build the portable executable, the portable zip and the installer (Windows).
REM Requires: pyinstaller (pip install pyinstaller) and Inno Setup 6.

setlocal

pyinstaller --noconfirm --onefile --windowed --icon img\icon.ico --name "OPAutoClicker" main.py || exit /b 1

REM Portable zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\OPAutoClicker.exe' -DestinationPath 'dist\OPAutoClicker-Portable.zip' -Force"

REM Installer
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
    "%ISCC%" installer.iss
) else (
    echo [WARNING] Inno Setup not found - skipping installer build.
)

echo.
echo Built:
echo   dist\OPAutoClicker.exe        (portable executable)
echo   dist\OPAutoClicker-Portable.zip
echo   dist\OPAutoClicker-Setup.exe  (installer)
