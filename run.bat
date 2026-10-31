@echo off
cd /d "%~dp0"
echo Starting MCA Attendance Hub on Streamlit...
py -3.12 -m streamlit run app.py
pause
