@echo off
setlocal
set PORT=8015
python -m uvicorn api.main:app --host 127.0.0.1 --port %PORT% --reload
endlocal
