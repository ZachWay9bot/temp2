@echo off
setlocal
cd /d "%~dp0"
if not exist LOGS mkdir LOGS
py -3 BMSPHY_V1_TEST.py --port COM9
echo.
pause
