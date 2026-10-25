@echo off
setlocal
cd /d "%~dp0"
start "KomariDesktop settings" "%~dp0KomariDesktop.exe" --settings
endlocal

