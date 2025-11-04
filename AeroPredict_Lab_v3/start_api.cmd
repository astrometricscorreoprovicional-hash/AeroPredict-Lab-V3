@echo off
setlocal
cd /d %~dp0
if not exist .venv ( py -3 -m venv .venv )
call .\.venv\Scripts\python -m pip install -U pip >nul
call .\.venv\Scripts\pip install -r requirements.txt
set LOG_LEVEL=INFO
call .\.venv\Scripts\python -m uvicorn src.api:app --host 127.0.0.1 --port 8020 --reload
