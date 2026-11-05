@echo off
setlocal
cd /d "%~dp0"
if not exist LOGS mkdir LOGS
echo ================================================================
echo  BMS BATTERY SAFE V1
echo  POWERSTAGE SOFTWARE-LOCKED - BMS UART TEST ONLY
echo ================================================================
echo.
py -3 BMS_BATTERY_SAFE_V1_TEST.py --port COM9
echo.
pause
