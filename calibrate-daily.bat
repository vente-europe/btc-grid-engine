@echo off
REM Dzienna kalibracja BTC Grid Engine + push na GitHub Pages
REM Task Scheduler: "BTC Grid Calibrate", codziennie 06:30
cd /d "c:\AI Workspaces\Claude Code Workspace - Tom\02-Projects\BTC Grid Engine"
"C:\Users\tommi\AppData\Local\Programs\Python\Python311\python.exe" src\calibrate.py >> calibrate.log 2>&1
"C:\Users\tommi\AppData\Local\Programs\Python\Python311\python.exe" src\push_pages.py >> calibrate.log 2>&1
