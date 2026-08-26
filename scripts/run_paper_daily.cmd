@echo off
rem Daily paper-trading run (Windows).
rem
rem Schedule this in Task Scheduler for ~03:10 local, shortly after the
rem 00:00 UTC daily bar close. Set the task's "Start in" directory to your
rem workspace, or leave it unset: this script defaults to the directory
rem above itself, which is the repository root in a source install.
rem
rem Runs EVERY paper strategy; add a line per new survivor.

setlocal
set PYTHONIOENCODING=utf-8

rem Workspace: %MARTEX_QUANT_HOME% if set, otherwise the repo root above this
rem script. Never a hardcoded path - this file ships to other machines.
if defined MARTEX_QUANT_HOME (
    set "WORKSPACE=%MARTEX_QUANT_HOME%"
) else (
    set "WORKSPACE=%~dp0.."
)
cd /d "%WORKSPACE%" || exit /b 1

rem Prefer the project's virtualenv; fall back to whatever is on PATH.
set "TB=%WORKSPACE%\.venv\Scripts\martex-quant.exe"
if not exist "%TB%" set "TB=martex-quant"

if not exist "data\paper" mkdir "data\paper"

for %%S in (vol-target rotation crash-bounce rotation-stop) do (
    "%TB%" paper --strategy %%S >> "data\paper\runs.log" 2>&1
)

endlocal
