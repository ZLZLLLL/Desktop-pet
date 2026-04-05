@echo off
setlocal
cd /d "%~dp0"

where ISCC >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Inno Setup compiler ^(ISCC^) not found.
    echo [INFO] Please install Inno Setup and add ISCC to PATH.
    echo [INFO] Download: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

if not exist "dist\DesktopPet.exe" (
    echo [INFO] dist\DesktopPet.exe not found, running build_release.bat first...
    call .\build_release.bat
    if errorlevel 1 exit /b 1
)

echo [INFO] Building installer with DesktopPet.iss ...
ISCC DesktopPet.iss
if errorlevel 1 (
    echo [ERROR] Installer build failed.
    pause
    exit /b 1
)

echo [OK] Installer generated under installer\DesktopPet-Setup.exe
