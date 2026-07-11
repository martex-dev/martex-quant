@echo off
rem Launch the operations dashboard and open it in the default browser.
cd /d "C:\Users\PC Games\Desktop\Trading Bot"
start "" http://127.0.0.1:8765
.venv\Scripts\python.exe -m trading_bot.dashboard
