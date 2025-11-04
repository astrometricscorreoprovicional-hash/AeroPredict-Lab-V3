from __future__ import annotations
from fastapi import FastAPI, Body, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sqlite3, json, time, os, io, csv, asyncio, contextlib
import pandas as pd, pyarrow as pa, pyarrow.parquet as pq
from datetime import datetime, timezone

from skycep.engine.runtime import Engine
from skycep.engine.ruleset import compile_rules

DB_PATH = os.environ.get("SKYCEP_DB", "skycep.db")
RAW_DIR = os.environ.get("SKYCEP_RAW_DIR", "skycep/data/raw")
ALERT_DIR = os.environ.get("SKYCEP_ALERT_DIR", "skycep/data/alerts")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(ALERT_DIR, exist_ok=True)

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS rules (version INTEGER PRIMARY KEY, ts REAL, text TEXT, active INTEGER, sha256 TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS alerts (ts REAL, id TEXT, type TEXT, rule TEXT, payload TEXT, day TEXT)")
    con.commit(); con.close()
init_db()

def store_alert(alert: dict):
    day = time.strftime("%Y-%m-%d", time.gmtime(alert.get("ts", time.time())))
    payload = json.dumps({k:v for k,v in alert.items() if k not in ("ts","id","type","rule")})
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT INTO alerts(ts,id,type,rule,payload,day) VALUES(?,?,?,?,?,?)",
                (alert.get("ts"), alert.get("id"), alert.get("type"), alert.get("rule"), payload, day))
    con.commit(); con.close()
    df = pd.DataFrame([alert])
    day_dir = os.path.join(ALERT_DIR, f"day={day}")
    os.makedirs(day_dir, exist_ok=True)
    file_path = os.path.join(day_dir, "alerts.parquet")
    table = pa.Table.from_pandas(df)
    if os.path.exists(file_path):
        with pq.ParquetWriter(file_path, table.schema, use_dictionary=True) as writer:
            writer.write_table(table)
    else:
        pq.write_table(table, file_path)

def _sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def store_rules(text: str, active: int=1):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT COALESCE(MAX(version),0) FROM rules")
    ver = (cur.fetchone()[0] or 0) + 1
    sha = _sha256(text)
    cur.execute("INSERT INTO rules(version,ts,text,active,sha256) VALUES(?,?,?,?,?)",
                (ver, time.time(), text, active, sha))
    if active:
        cur.execute("UPDATE rules SET active=0 WHERE version<>?", (ver,))
    con.commit(); con.close()
    return ver, sha

def get_active_rules():
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT version, text, sha256 FROM rules WHERE active=1 ORDER BY version DESC LIMIT 1").fetchone()
    con.close()
    return row

app = FastAPI(title="SkyCEP", version="0.6.2")
alert_subs: list[asyncio.Queue] = []

def on_alert_cb(alert):
    try: store_alert(alert)
    except Exception: pass
    for q in list(alert_subs):
        with contextlib.suppress(Exception):
            q.put_nowait(alert)

ENG = Engine(window_seconds=5.0, on_alert=on_alert_cb)

class Event(BaseModel):
    ts: float
    id: str
    data: Dict[str, Any]

@app.get("/health")
def health():
    con = sqlite3.connect(DB_PATH)
    c = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    row = get_active_rules()
    con.close()
    return {"status":"ok","rules": len(ENG.programs), "alerts_mem": len(ENG.alerts), "alerts_db": c,
            "active_rules_version": (row[0] if row else None), "active_rules_hash": (row[2] if row else None),
            "version": "0.6.2"}

@app.post("/rules/validate")
def validate_rules(text: str = Body(..., media_type="text/plain")):
    try:
        sha = _sha256(text)
        return {"ok": True, "sha256": sha}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/rules")
def post_rules(text: str = Body(..., media_type="text/plain"), activate: int = 1):
    try:
        progs = compile_rules(text)
        if activate: ENG.load_programs(progs)
        ver, sha = store_rules(text, active=1 if activate else 0)
        return {"loaded": len(progs), "version": ver, "active": bool(activate), "sha256": sha}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/rules/versions")
def rule_versions():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT version, ts, active, sha256 FROM rules ORDER BY version DESC").fetchall()
    con.close()
    return [{"version":v,"ts":ts,"active":bool(a),"sha256":h} for (v,ts,a,h) in rows]

@app.post("/ingest")
def ingest(items: List[Event]):
    ts0 = items[0].ts if items else time.time()
    day = datetime.fromtimestamp(ts0, tz=timezone.utc).strftime("%Y-%m-%d")
    day_dir = os.path.join(RAW_DIR, f"day={day}")
    os.makedirs(day_dir, exist_ok=True)
    rows = []
    for e in items:
        row = {"ts": e.ts, "id": e.id}
        for k,v in e.data.items(): row[k] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    file_path = os.path.join(day_dir, "events.parquet")
    table = pa.Table.from_pandas(df)
    if os.path.exists(file_path):
        with pq.ParquetWriter(file_path, table.schema, use_dictionary=True) as writer:
            writer.write_table(table)
    else:
        pq.write_table(table, file_path)
    ENG.ingest([e.model_dump() for e in items])
    return {"stored": len(items), "raw_partition": f"day={day}"}

@app.get("/alerts")
def alerts(n: int = 50, day: Optional[str]=None, start_ts: Optional[float]=None, end_ts: Optional[float]=None):
    con = sqlite3.connect(DB_PATH)
    q = "SELECT ts,id,type,rule,payload FROM alerts WHERE 1=1"
    args = []
    if day: q += " AND day=?"; args.append(day)
    if start_ts is not None: q += " AND ts>=?"; args.append(start_ts)
    if end_ts is not None: q += " AND ts<=?"; args.append(end_ts)
    q += " ORDER BY ts DESC LIMIT ?"; args.append(n)
    rows = con.execute(q, tuple(args)).fetchall()
    con.close()
    out = []
    for ts,id_,type_,rule_,payload in rows:
        d = {"ts": ts, "id": id_, "type": type_, "rule": rule_}
        try: d.update(json.loads(payload or "{}"))
        except Exception: pass
        out.append(d)
    return out

@app.get("/export/alerts.csv")
def export_csv(day: Optional[str]=None, start_ts: Optional[float]=None, end_ts: Optional[float]=None):
    con = sqlite3.connect(DB_PATH)
    q = "SELECT ts,id,type,rule,payload FROM alerts WHERE 1=1"
    args = []
    if day: q += " AND day=?"; args.append(day)
    if start_ts is not None: q += " AND ts>=?"; args.append(start_ts)
    if end_ts is not None: q += " AND ts<=?"; args.append(end_ts)
    q += " ORDER BY ts"
    rows = con.execute(q, tuple(args)).fetchall()
    con.close()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["ts","id","type","rule","payload_json"])
    for r in rows: w.writerow(r)
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition":"attachment; filename=alerts.csv"})

@app.get("/alerts/stream")
async def alerts_stream(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    alert_subs.append(q)
    async def gen():
        try:
            while True:
                if await request.is_disconnected(): break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield "event: keepalive\ndata: {}\n\n"; continue
                yield "event: alert\ndata: " + json.dumps(msg) + "\n\n"
        finally:
            with contextlib.suppress(ValueError): alert_subs.remove(q)
    return StreamingResponse(gen(), media_type="text/event-stream")

LIVE_HTML = """
<!doctype html><html><head><meta charset='utf-8'><title>SkyCEP Live v0.6.2</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:0;background:#0b1021;color:#e6edf3}
h1{margin:0;padding:16px 20px;background:#00E0FF;color:#0b1021;font-weight:800}
#log{padding:12px 16px;max-height:80vh;overflow:auto}
.item{background:#0f1631;border:1px solid #1f2a4d;margin:8px 0;padding:8px 10px;border-radius:14px;box-shadow:0 2px 10px rgba(0,0,0,.3)}
.badge{display:inline-block;border-radius:999px;padding:2px 10px;margin-right:8px;font-weight:700}
.t-hard{background:#2C0B0E;color:#FF6B6B;border:1px solid #FF6B6B}
.small{opacity:.8;font-size:12px}
</style></head><body><h1>SkyCEP Live v0.6.2 — Alerts</h1><div id='log'></div>
<script>
const log = document.getElementById('log');
function push(item){
  const d=document.createElement('div');
  d.className='item';
  const badge = '<span class="badge t-hard">'+(item.type||'alert')+'</span>';
  d.innerHTML= badge + '<span>'+ (item.id||'UNK') +'</span>'+
              '<div class="small">'+new Date(item.ts*1000).toLocaleString()+' — '+(item.rule||'')+'</div>'+
              '<pre>'+JSON.stringify(item,null,2)+'</pre>';
  log.prepend(d);
}
const es = new EventSource('/alerts/stream');
es.addEventListener('alert', e => push(JSON.parse(e.data)));
es.addEventListener('keepalive', e => {});
</script></body></html>
"""

@app.get("/live", response_class=HTMLResponse)
def live_page():
    return HTMLResponse(LIVE_HTML)
