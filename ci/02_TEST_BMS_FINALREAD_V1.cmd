@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>nul
set "PORT=%~1"
if "%PORT%"=="" set "PORT=COM9"
if not exist LOGS mkdir LOGS
echo ================================================================
echo  BMS FINALREAD V1 - POWERSTAGE LOCKED
echo  Stock G30 10S battery only. No motor commands.
echo ================================================================
py -3 ".\tools\BMS_FINALREAD_V1_TEST.py" --port "%PORT%" --seconds 16
if errorlevel 1 goto :fail
echo.
echo [PASS] BMS FINALREAD V1.
pause
exit /b 0
:fail
echo.
echo [FAIL/ABORT] LOGS sichern. Powerstage bleibt gesperrt.
pause
exit /b 1
