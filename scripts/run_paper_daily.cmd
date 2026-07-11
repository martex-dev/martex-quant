@echo off
rem Daily paper-trading run. Scheduled via Windows Task Scheduler at 03:10
rem local (Bulgaria) — shortly after the 00:00 UTC daily bar close.
rem Runs EVERY paper strategy; add a line per new survivor.
cd /d "C:\Users\PC Games\Desktop\Trading Bot"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -m trading_bot.live.paper --strategy vol-target >> data\paper\runs.log 2>&1
.venv\Scripts\python.exe -m trading_bot.live.paper --strategy rotation >> data\paper\runs.log 2>&1
