
import os, csv, time
from typing import Dict, Any

class CSVLogger:
    def __init__(self, path:str = "data/experiments.csv"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["ts","event","params","metrics"])
                w.writeheader()

    def log(self, event:str, params:Dict[str,Any], metrics:Dict[str,Any]):
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["ts","event","params","metrics"]).writerow({
                "ts": time.time(),
                "event": event,
                "params": str(params),
                "metrics": str(metrics)
            })
