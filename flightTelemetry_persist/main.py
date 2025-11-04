# main.py
from typing import List, Optional, Union, Iterable
from fastapi import FastAPI, Response, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dateutil import parser as dateparser
from io import BytesIO
import time, os, io, csv, sqlite3, math

# --- NUEVO: para exportar a Excel ---
import pandas as pd  # requiere: pip install pandas openpyxl

APP_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_DIR, 'data', 'telemetry.db')

app = FastAPI(title='flightTelemetry', version='2.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], allow_credentials=True,
    allow_methods=['*'], allow_headers=['*'],
)

class Telemetry(BaseModel):
    ts: float = Field(default_factory=lambda: time.time())
    t: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    vx: Optional[float] = None
    vy: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    engine_out: Optional[Union[int, bool]] = None

def db_conn():
    os.makedirs(os.path.join(APP_DIR, 'data'), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS telemetry(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        t REAL,
        x REAL, y REAL, vx REAL, vy REAL, pitch REAL, roll REAL,
        engine_out INTEGER
    )
    ''')
    conn.commit()
    return conn

CONN = db_conn()

def insert_many(items: Iterable[Telemetry]):
    CONN.executemany('''
        INSERT INTO telemetry(ts,t,x,y,vx,vy,pitch,roll,engine_out)
        VALUES(?,?,?,?,?,?,?,?,?)
    ''', [(float(i.ts), i.t, i.x, i.y, i.vx, i.vy, i.pitch, i.roll,
           int(i.engine_out) if isinstance(i.engine_out, (int, bool)) else None) for i in items])
    CONN.commit()

def fetch_last(n: int):
    cur = CONN.execute('''
        SELECT ts,t,x,y,vx,vy,pitch,roll,engine_out
        FROM telemetry
        ORDER BY id DESC
        LIMIT ?
    ''', (max(0, n),))
    rows = cur.fetchall()
    rows.reverse()
    return [dict(zip(['ts','t','x','y','vx','vy','pitch','roll','engine_out'], r)) for r in rows]

def fetch_range(ts_from: Optional[float], ts_to: Optional[float], n: Optional[int] = None):
    q = 'SELECT ts,t,x,y,vx,vy,pitch,roll,engine_out FROM telemetry WHERE 1=1'
    params = []
    if ts_from is not None:
        q += ' AND ts >= ?'; params.append(ts_from)
    if ts_to is not None:
        q += ' AND ts <= ?'; params.append(ts_to)
    q += ' ORDER BY id ASC'
    if n is not None and n > 0:
        q += ' LIMIT ?'; params.append(n)
    cur = CONN.execute(q, tuple(params))
    rows = cur.fetchall()
    return [dict(zip(['ts','t','x','y','vx','vy','pitch','roll','engine_out'], r)) for r in rows]

def parse_time_param(val: Optional[str]) -> Optional[float]:
    if val is None or val == '':
        return None
    try:
        return float(val)
    except Exception:
        dt = dateparser.parse(val)
        return dt.timestamp()

@app.get('/health')
def health():
    cur = CONN.execute('SELECT COUNT(*) FROM telemetry')
    (count,) = cur.fetchone()
    return {'status':'ok','count':int(count),'version':'2.0.0'}

@app.post('/reset')
def reset():
    CONN.execute('DELETE FROM telemetry')
    CONN.commit()
    return {'reset':True,'total':0}

@app.post('/ingest')
def ingest(items: List[Telemetry]):
    insert_many(items)
    cur = CONN.execute('SELECT COUNT(*) FROM telemetry')
    (count,) = cur.fetchone()
    return {'stored':len(items),'total':int(count)}

@app.get('/last')
def last(n: int = 600) -> List[Telemetry]:
    return fetch_last(n)

@app.get('/alerts')
def alerts():
    cur = CONN.execute('''
        SELECT ts,t,x,y,vx,vy,pitch,roll,engine_out
        FROM telemetry ORDER BY id DESC LIMIT 1
    ''')
    row = cur.fetchone()
    out = []
    if not row:
        return out
    d = dict(zip(['ts','t','x','y','vx','vy','pitch','roll','engine_out'], row))
    def _num(v):
        try: return float(v) if v is not None else None
        except: return None
    pitch = _num(d.get('pitch'))
    roll  = _num(d.get('roll'))
    y     = _num(d.get('y'))
    vx    = _num(d.get('vx'))
    vy    = _num(d.get('vy'))
    eng   = d.get('engine_out')
    eng_on = (int(eng) == 1) if eng is not None else False
    speed = None
    if vx is not None and vy is not None:
        speed = math.sqrt(vx*vx + vy*vy)
    if pitch is not None and abs(pitch) > 0.5:
        out.append({'type':'high_pitch_attitude','value':pitch,'threshold':0.5})
    if roll is not None and abs(roll) > 0.6:
        out.append({'type':'high_bank_angle','value':roll,'threshold':0.6})
    if y is not None and vy is not None and y < 20.0 and vy < -1.2:
        out.append({'type':'hard_landing_risk','altitude_m':y,'vy_ms':vy})
    if speed is not None and speed < 15.0:
        out.append({'type':'stall_risk','speed_ms':speed,'threshold':15.0})
    if speed is not None and y is not None and (speed > 80.0 and y < 50.0):
        out.append({'type':'overspeed_low_altitude','speed_ms':speed,'altitude_m':y,'limits':{'speed':80.0,'altitude':50.0}})
    if (eng_on) and (y is not None and y < 100.0):
        out.append({'type':'engine_out_low_altitude','altitude_m':y})
    return out

@app.get('/export.csv')
def export_csv(
    n: Optional[int] = Query(None, description='Número de últimos puntos'),
    from_ts: Optional[str] = Query(None, description='Inicio (epoch o ISO-8601)'),
    to_ts: Optional[str] = Query(None, description='Fin (epoch o ISO-8601)')
):
    ts_from = parse_time_param(from_ts)
    ts_to   = parse_time_param(to_ts)
    if ts_from is None and ts_to is None:
        data = fetch_last(n if (n and n>0) else 900)
    else:
        data = fetch_range(ts_from, ts_to, n)
    fieldnames = ['ts','t','x','y','vx','vy','pitch','roll','engine_out']
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in data:
        writer.writerow({k: r.get(k, None) for k in fieldnames})
    csv_bytes = buf.getvalue().encode('utf-8')
    headers = {'Content-Disposition': 'attachment; filename="telemetry_export.csv"'}
    return Response(content=csv_bytes, media_type='text/csv; charset=utf-8', headers=headers)

# --- NUEVO: exportación a Excel (.xlsx) con mismos parámetros que /export.csv ---
@app.get('/export/xlsx')
def export_xlsx(
    n: Optional[int] = Query(None, description='Número de últimos puntos'),
    from_ts: Optional[str] = Query(None, description='Inicio (epoch o ISO-8601)'),
    to_ts: Optional[str] = Query(None, description='Fin (epoch o ISO-8601)')
):
    ts_from = parse_time_param(from_ts)
    ts_to   = parse_time_param(to_ts)
    if ts_from is None and ts_to is None:
        data = fetch_last(n if (n and n > 0) else 900)
    else:
        data = fetch_range(ts_from, ts_to, n)

    if not data:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")

    df = pd.DataFrame(data, columns=['ts','t','x','y','vx','vy','pitch','roll','engine_out'])
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="telemetry")
    bio.seek(0)

    headers = {'Content-Disposition': 'attachment; filename="telemetry_export.xlsx"'}
    return StreamingResponse(
        bio,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers=headers
    )

@app.get('/', response_class=HTMLResponse)
def index():
    with open(os.path.join(os.path.dirname(__file__),'static','index.html'),'r',encoding='utf-8') as f:
        return HTMLResponse(f.read())

app.mount('/static', StaticFiles(directory=os.path.join(os.path.dirname(__file__),'static')), name='static')
