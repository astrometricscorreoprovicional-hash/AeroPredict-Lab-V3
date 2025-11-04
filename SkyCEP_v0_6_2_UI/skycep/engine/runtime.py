from __future__ import annotations
import time
class Engine:
    def __init__(self, window_seconds: float = 5.0, on_alert=None):
        self.window_seconds = window_seconds
        self.on_alert = on_alert
        self.programs = []
        self.alerts = []
        self.states = {}
    def load_programs(self, progs):
        self.programs = list(progs)
    def ingest(self, events):
        now = time.time()
        for e in events:
            d = e.get("data", {})
            if d.get("y") is not None and d.get("vy") is not None and float(d["y"]) < 20 and float(d["vy"]) < -1.2:
                alert = {"ts": e.get("ts", now), "id": e.get("id","UNK"), "type": "hard_landing_risk",
                         "rule": "demo", "alt": d.get("y"), "vy": d.get("vy")}
                self.alerts.append(alert)
                if self.on_alert: self.on_alert(alert)
