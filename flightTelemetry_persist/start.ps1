param([int]$Port=8000)
$ErrorActionPreference="Stop"
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if (!(Test-Path ".\.venv\Scripts\Activate.ps1")) { py -3.13 -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port $Port
