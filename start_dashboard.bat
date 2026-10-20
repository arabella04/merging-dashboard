@echo off
cd /d "%~dp0"
echo Starting QA Audit Trail & Risk Monitoring Dashboard...
start "" "http://localhost:8095"
python server.py
pause
