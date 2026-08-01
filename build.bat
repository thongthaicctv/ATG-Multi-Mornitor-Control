@echo off
setlocal
chcp 65001 >nul

rem Luon chuyen ve dung thu muc chua build.bat, ke ca khi mo tu shortcut/CMD khac.
cd /d "%~dp0"

echo ============================================
echo   BUILD ATG SIGNAGE - ONE FILE EXE
echo ============================================
echo Thu muc build: %CD%
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Hay cai Python va chon "Add Python to PATH".
    pause
    exit /b 1
)

if not exist "%~dp0requirements.txt" (
    echo [LOI] Khong tim thay requirements.txt tai:
    echo %~dp0requirements.txt
    pause
    exit /b 1
)

python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [LOI] Cai thu vien that bai. Kiem tra ket noi mang va Python/pip.
    pause
    exit /b 1
)

python "%~dp0build.py"
if errorlevel 1 (
    echo [LOI] Build that bai. Xem thong bao ben tren.
    pause
    exit /b 1
)

echo.
echo [OK] File da tao:
echo %~dp0dist_release\ATG Multi Mornitor Control V1.2.4.exe
pause
endlocal
