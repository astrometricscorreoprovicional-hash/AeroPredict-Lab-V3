import csv, os, time
from typing import Dict, Any

LOG_PATH = os.path.join("logs", "nebula_runs.csv")

def append_run(entry: Dict[str, Any]):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "timestamp","scenario","preset","duration_s","dt_s",
            "Q_alt","Q_speed","R_alt","R_speed","nees_avg","nees_max","n_points"
        ])
        if not exists:
            w.writeheader()
        w.writerow(entry)
