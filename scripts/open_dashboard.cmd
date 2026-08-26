@echo off
rem Desktop launcher: make sure the dashboard server is running (the
rem service script exits quietly if it already is), then open the page.
rem
rem Resolves the workspace the same way dashboard.cmd does, so this file
rem works on any machine rather than only the one it was written on.

setlocal

if defined MARTEX_QUANT_HOME (
    set "WORKSPACE=%MARTEX_QUANT_HOME%"
) else (
    set "WORKSPACE=%~dp0.."
)
cd /d "%WORKSPACE%" || exit /b 1

set "PYW=%WORKSPACE%\.venv\Scripts\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"

start "" "%PYW%" "%WORKSPACE%\scripts\dashboard_service.pyw"
start "" http://127.0.0.1:8765

endlocal
