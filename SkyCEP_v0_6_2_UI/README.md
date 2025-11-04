
Run like this:

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r skycep/requirements.txt

.\start_api.cmd   # terminal 1
.\start_ui.cmd    # terminal 2

In the UI, use the "Inyector de demo" to generate synthetic telemetry and alerts.
