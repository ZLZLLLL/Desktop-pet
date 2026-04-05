@echo off
setlocal
cd /d "%~dp0"

set "PY_EXE=.venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

echo [INFO] Using Python: %PY_EXE%
%PY_EXE% -m PyInstaller --noconfirm --clean DesktopPet.spec
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo [OK] Build completed.
echo [INFO] Output: dist\DesktopPet.exe
