@echo off
setlocal
cd /d %~dp0
if not exist .venv ( py -3 -m venv .venv )
call .\.venv\Scripts\python -m pip install -U pip >nul
call .\.venv\Scripts\pip install -r requirements.txt
set API_URL=http://127.0.0.1:8020
call .\.venv\Scripts\python -m streamlit run dashboard\app.py
