@echo off
REM CT Cannabis Political Check - Windows launcher
cd /d "%~dp0"
python -m pip install -r requirements.txt
python CTCannabisPoliticalCheck.py %*
