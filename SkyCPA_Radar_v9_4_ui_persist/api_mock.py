# api_mock.py
from fastapi import FastAPI, Response
from typing import List, Optional
import time, io, csv, random, math

app = FastAPI(title="SkyCPA Radar – mock API", version="0.4.0")

# almacenamiento en memoria
ALERTS: list[dict] = []


def _make_demo_alert(ts: float, idx: int, label: str = "radar_event") -> dict:
    """Crea una alerta de ejemplo."""
    base_alt = 50
    alt = base_alt + 10 * math.sin(idx / 5.0) + random.uniform(-3, 3)
    vy = -0.5 + random.uniform(-0.3, 0.4)
    spd = 60 + random.uniform(-5, 12)
    return {
        "ts": ts,
        "id": f"DEMO-{idx:04d}",
        "type": label,
        "rule": "mock_rule",
        "y": round(alt, 2),
        "vy": round(vy, 2),
        "spd": round(spd, 2),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.4.0",
        "alerts_db": len(ALERTS),
        "rules": 3,
    }


@app.get("/alerts")
def get_alerts(
    n: int = 400,
    day: Optional[str] = None,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
):
    out = ALERTS[-n:]
    if start_ts is not None:
        out = [a for a in out if a.get("ts") and a["ts"] >= start_ts]
    if end_ts is not None:
        out = [a for a in out if a.get("ts") and a["ts"] <= end_ts]
    return out


@app.get("/last")
def get_last(n: int = 50):
    """Por si la UI pide /last en lugar de /alerts."""
    return ALERTS[-n:]


@app.post("/ingest")
def ingest(items: List[dict]):
    """
    Espera items como:
      { "ts":..., "id":..., "data": { "y":..., "vy":..., "spd":..., "type":..., "rule":... } }
    """
    now = time.time()
    stored = 0
    for it in items:
        data = it.get("data") or {}
        row = {
            "ts": float(it.get("ts", now)),
            "id": it.get("id", "DEMO"),
            "type": data.get("type", "radar_event"),
            "rule": data.get("rule", "mock_rule"),
            "y": data.get("y"),
            "vy": data.get("vy"),
            "spd": data.get("spd"),
        }
        ALERTS.append(row)
        stored += 1
    return {"stored": stored, "raw_partition": "mock-part"}


@app.get("/seed")
def seed(n: int = 25):
    """Semilla rápida."""
    now = time.time()
    for i in range(n):
        ALERTS.append(_make_demo_alert(now + i * 0.2, i))
    return {"seeded": n, "total": len(ALERTS)}


@app.get("/seed/step")
def seed_step(reps: int = 25):
    """La UI te estaba llamando acá: /seed/step?reps=25."""
    now = time.time()
    for i in range(reps):
        ALERTS.append(_make_demo_alert(now + i * 0.2, i, label="radar_step"))
    return {"seeded_step": reps, "total": len(ALERTS)}


@app.post("/reset")
def reset():
    ALERTS.clear()
    return {"reset": True, "total": 0}


@app.get("/export/alerts.csv")
def export_csv():
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["ts", "id", "type", "rule", "y", "vy", "spd"],
    )
    writer.writeheader()
    for a in ALERTS:
        writer.writerow({
            "ts": a.get("ts"),
            "id": a.get("id"),
            "type": a.get("type"),
            "rule": a.get("rule"),
            "y": a.get("y"),
            "vy": a.get("vy"),
            "spd": a.get("spd"),
        })
    data = buf.getvalue().encode("utf-8")
    headers = {"Content-Disposition": 'attachment; filename="alerts.csv"'}
    return Response(content=data, media_type="text/csv; charset=utf-8", headers=headers)


# ========= NUEVO: /traffic =========
@app.get("/traffic")
def traffic():
    """
    Devuelve posiciones para el mapa (pydeck).
    Si hay alertas, las usamos como base y les añadimos lat/lon sintéticos.
    Si no hay alertas, generamos tráfico demo.
    """
    out = []
    # centro de ejemplo (Bogotá)
    base_lat = 4.65
    base_lon = -74.08

    if ALERTS:
        for i, a in enumerate(ALERTS[-80:]):  # no más de 80 para no explotar el mapa
            lat = base_lat + random.uniform(-0.25, 0.25)
            lon = base_lon + random.uniform(-0.25, 0.25)
            out.append({
                "id": a.get("id", f"ACFT-{i:03d}"),
                "lat": lat,
                "lon": lon,
                "alt": (a.get("y") or 50) * 30,   # convertir “y” en algo tipo altitud
                "spd": a.get("spd") or 120,
                "vy": a.get("vy") or 0,
                "ts": a.get("ts", time.time()),
            })
    else:
        # demo puro
        now = time.time()
        for i in range(15):
            out.append({
                "id": f"ACFT-{i:03d}",
                "lat": base_lat + random.uniform(-0.25, 0.25),
                "lon": base_lon + random.uniform(-0.25, 0.25),
                "alt": random.randint(1500, 9500),
                "spd": random.randint(90, 260),
                "vy": random.uniform(-5, 5),
                "ts": now,
            })
    return out
