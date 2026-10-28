@echo off
setlocal
pushd "%~dp0"
py g30_r3i5_pushstart_test.py --port COM9 --target-erpm 1500 --hold 3
set "RC=%ERRORLEVEL%"
popd
pause
exit /b %RC%
