@echo off
:: Navigate to script directory
cd /d "%~dp0"

:: Start application silently using pythonw and the wrapper script
:: This suppresses the console window.
:: To stop the server, you must end the "pythonw.exe" process in Task Manager.
start "" pythonw gui_main.py
exit
