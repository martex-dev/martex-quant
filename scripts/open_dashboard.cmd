@echo off
rem Desktop launcher: make sure the dashboard server is running (the
rem service script exits quietly if it already is), then open the page.
cd /d "C:\Users\PC Games\Desktop\Trading Bot"
start "" ".venv\Scripts\pythonw.exe" "scripts\dashboard_service.pyw"
start "" http://127.0.0.1:8765
