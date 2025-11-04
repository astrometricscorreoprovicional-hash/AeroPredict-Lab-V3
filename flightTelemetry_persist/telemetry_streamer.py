# telemetry_streamer.py
import os, glob, time, requests

API = os.environ.get("API_URL", "http://127.0.0.1:8000")

def latest_csv():
    os.makedirs("logs", exist_ok=True)
    files = sorted(glob.glob(os.path.join("logs","telemetry_*.csv")))
    if not files:
        raise SystemExit("No hay CSVs en ./logs. Genera alguno o ejecuta flight_sim_stub.py")
    return files[-1]

def tail_and_publish(path, batch_size=15, interval=0.6):
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        buf = []

        def to_float(rec, k):
            try:
                return float(rec.get(k, ""))
            except Exception:
                return None

        def push(rec):
            return {
                "ts": time.time(),
                "t": to_float(rec, "t"),
                "x": to_float(rec, "x"),
                "y": to_float(rec, "y"),
                "vx": to_float(rec, "vx"),
                "vy": to_float(rec, "vy"),
                "pitch": to_float(rec, "pitch"),
                "roll": to_float(rec, "roll"),
                "engine_out": int(rec.get("engine_out", "0")) if str(rec.get("engine_out", "0")).isdigit() else 0
            }

        def send_buf():
            nonlocal buf
            if not buf:
                return
            try:
                r = requests.post(f"{API}/ingest", json=buf, timeout=5)
                if r.ok:
                    total = None
                    try:
                        total = r.json().get("total")
                    except Exception:
                        pass
                    print(f"[OK] Enviados {len(buf)} — total remoto: {total}")
                else:
                    print(f"[ERR] {r.status_code}: {r.text[:160]}")
            except Exception as e:
                print("[ERR] publicando:", e)
            buf = []

        print(f"Publicando backlog a {API}/ingest — CSV: {os.path.basename(path)}")
        for line in f:
            if not line.strip():
                continue
            values = [v.strip() for v in line.strip().split(",")]
            rec = dict(zip(header, values))
            buf.append(push(rec))
            if len(buf) >= 200:
                send_buf()
        send_buf()

        print(f"Publicando tail en {API}/ingest — CSV: {os.path.basename(path)}")
        while True:
            line = f.readline()
            if not line:
                time.sleep(interval)
                continue
            values = [v.strip() for v in line.strip().split(",")]
            rec = dict(zip(header, values))
            buf.append(push(rec))
            if len(buf) >= batch_size:
                send_buf()

if __name__ == '__main__':
    path = latest_csv()
    tail_and_publish(path)
