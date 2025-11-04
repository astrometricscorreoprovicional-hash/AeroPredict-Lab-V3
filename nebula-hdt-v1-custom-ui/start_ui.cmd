@echo off
setlocal
set PORT=8515
streamlit run ui/app.py --server.port %PORT% --server.address 127.0.0.1
endlocal
