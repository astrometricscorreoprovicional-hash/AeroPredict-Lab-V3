param([string]$ApiUrl = "http://127.0.0.1:8000")
$ErrorActionPreference="Stop"
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if (!(Test-Path ".\.venv\Scripts\Activate.ps1")) { py -3.13 -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:API_URL = $ApiUrl
python telemetry_streamer.py
