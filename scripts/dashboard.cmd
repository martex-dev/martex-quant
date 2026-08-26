@echo off
rem Launch the operations dashboard (Windows).
rem
rem Serves http://127.0.0.1:8765 and opens it in the default browser.
rem Resolves the workspace the same way run_paper_daily.cmd does, so this
rem file works on any machine, not just the one it was written on.

setlocal
set PYTHONIOENCODING=utf-8

if defined TRADING_BOT_HOME (
    set "WORKSPACE=%TRADING_BOT_HOME%"
) else (
    set "WORKSPACE=%~dp0.."
)
cd /d "%WORKSPACE%" || exit /b 1

set "TB=%WORKSPACE%\.venv\Scripts\tradingbot.exe"
if not exist "%TB%" set "TB=tradingbot"

"%TB%" dashboard

endlocal
