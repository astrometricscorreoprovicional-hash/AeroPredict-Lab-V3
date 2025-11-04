$ErrorActionPreference="Stop"
$here=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if (!(Test-Path ".\.venv\Scripts\Activate.ps1")) { py -3.13 -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python flight_sim_stub.py
