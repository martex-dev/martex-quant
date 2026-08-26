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

rem ORDER MATTERS. The run is a sequential loop, so if it is interrupted
rem partway - machine sleep, logoff, shutdown - the accounts at the END of
rem the list are the ones that lose their mark. Two such truncations are on
rem record: 2026-08-20 (1 of 4 completed) and 2026-08-26 (3 of 4, task exit
rem 0xC000013A = STATUS_CONTROL_C_EXIT), and both times the account that
rem lost its mark was the last one in this list.
rem
rem So the list is ordered by how much the record matters, not
rem alphabetically or by age: the DEPLOYED spec runs first and the
rem never-triggered overlay runs last.
for %%S in (rotation-stop rotation vol-target crash-bounce) do (
    "%TB%" paper --strategy %%S >> "data\paper\runs.log" 2>&1
)

endlocal
