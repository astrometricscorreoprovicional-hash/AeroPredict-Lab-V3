import os, time, requests, streamlit as st, pandas as pd, altair as alt, humanize, random, io

API = os.environ.get("API_URL","http://127.0.0.1:8050")
st.set_page_config(page_title="SkyCEP Monitor — v0.6.2", page_icon="skycep/ui_modern/assets/favicon.png", layout="wide")

st.markdown('''
<style>
:root{ --glass:#0f1631; --ink:#e6edf3; --muted:#a1acc9; --accent:#00E0FF; --danger:#FF6B6B; }
.block{background:var(--glass); border:1px solid #1f2a4d; border-radius:16px; padding:14px; box-shadow:0 2px 10px rgba(0,0,0,.25);}
.kpi{display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:12px;}
.kpi .card{background:#0b1228; border:1px solid #1c2444; border-radius:14px; padding:12px;}
.kpi .h{font-size:13px; color:var(--muted); margin-bottom:6px}
.kpi .v{font-size:22px; font-weight:800; color:var(--ink)}
.badge{display:inline-block; padding:2px 10px; border-radius:999px; font-weight:700; margin-right:6px}
.badge.ok{background:#06261f; color:#04d49c; border:1px solid #04d49c}
.badge.err{background:#2C0B0E; color:var(--danger); border:1px solid var(--danger)}
.feed .item{background:#0b1228; border:1px solid #1c2444; border-radius:14px; padding:10px 12px; margin-bottom:10px}
.feed .top{display:flex; align-items:center; justify-content:space-between}
.feed .type{font-weight:800}
.small{color:var(--muted); font-size:12px}
hr{border-color:#1f2a4d}
.btnrow{display:flex; gap:8px; align-items:center}
</style>
''', unsafe_allow_html=True)

st.title("SkyCEP Monitor — v0.6.2")

# ===== SIDEBAR =====
with st.sidebar:
    st.subheader("Conexión")
    API = st.text_input("API URL", API)
    auto = st.toggle("Auto-refresh", value=True)
    interval = st.slider("Intervalo (s)", 2, 30, 6)
    if auto:
        fn = getattr(st, "autorefresh", None)
        if callable(fn):
            fn(interval=interval*1000, key="auto_modern")
    # 👇 cambiamos esto:
    st.markdown("[⬇️ Descargar Excel de alertas](#exportar--datos)")

# --- Demo Injector ---
st.markdown("<div class='block'>", unsafe_allow_html=True)
st.subheader("Inyector de demo (sin simulador)")
colx1, colx2, colx3 = st.columns([1,1,1])
with colx1:
    flight_id = st.text_input("Vuelo", "DEMO123")
with colx2:
    n_points = st.number_input("Puntos", 50, 2000, 300, step=50)
with colx3:
    pct_hard = st.slider("% eventos de riesgo", 0, 100, 25, step=5)

if st.button("Inyectar demo ahora", type="primary"):
    ts0 = time.time()
    events = []
    for i in range(int(n_points)):
        ts = ts0 + i*0.2
        y = 50 + 10*random.random()
        vy = -0.5 + 0.2*random.random()
        if random.random() < (pct_hard/100.0):
            y = 10 + 5*random.random()
            vy = -1.5 - 0.5*random.random()
        e = {
            "ts": ts,
            "id": flight_id,
            "data": {
                "y": y,
                "vy": vy,
                "spd": 60 + 10*random.random()
            }
        }
        events.append(e)
    try:
        r = requests.post(f"{API}/ingest", json=events, timeout=10)
        if r.ok:
            try:
                payload = r.json()
                part = payload.get("raw_partition", "-")
            except Exception:
                part = "-"
            st.success(f"Inyectados {len(events)} puntos. Partición: {part}")
        else:
            st.error(f"Error {r.status_code}: {r.text[:160]}")
    except Exception as e:
        st.error(f"Error inyectando demo: {e}")
st.markdown("</div>", unsafe_allow_html=True)

# ===== Health / KPIs =====
try:
    H = requests.get(f"{API}/health", timeout=5).json()
    status_badge = '<span class="badge ok">API OK</span>' if H.get("status") == "ok" else '<span class="badge err">API DOWN</span>'
except Exception:
    H = {}
    status_badge = '<span class="badge err">API DOWN</span>'

st.markdown(
    "<div class='block'><div class='kpi'>"
    f"<div class='card'><div class='h'>Estado</div><div class='v'>{status_badge}</div></div>"
    f"<div class='card'><div class='h'>Version</div><div class='v'>{H.get('version','-')}</div></div>"
    f"<div class='card'><div class='h'>Alertas en DB</div><div class='v'>{H.get('alerts_db','-')}</div></div>"
    f"<div class='card'><div class='h'>Reglas cargadas</div><div class='v'>{H.get('rules','-')}</div></div>"
    "</div></div>",
    unsafe_allow_html=True
)

st.markdown("<br/>", unsafe_allow_html=True)

# ===== Filtros =====
colf1, colf2, colf3, colf4 = st.columns([1,1,1,1])
with colf1:
    day = st.text_input("Día (YYYY-MM-DD)", value="")
with colf2:
    start_ts = st.number_input("start_ts (unix)", value=0.0, step=1.0)
with colf3:
    end_ts = st.number_input("end_ts (unix)", value=0.0, step=1.0)
with colf4:
    n = st.number_input("n registros", 10, 5000, 400)

params = {"n": int(n)}
if day.strip():
    params["day"] = day.strip()
if start_ts > 0:
    params["start_ts"] = float(start_ts)
if end_ts > 0:
    params["end_ts"] = float(end_ts)

# ===== Data =====
try:
    alerts = requests.get(f"{API}/alerts", params=params, timeout=10).json()
    df = pd.DataFrame(alerts)
except Exception:
    df = pd.DataFrame()

# ===== Exportar a Excel =====
st.markdown("<div class='block' id='exportar--datos'>", unsafe_allow_html=True)
st.subheader("Exportar / Datos")
if not df.empty:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="alerts")
    excel_bytes = buf.getvalue()
    st.download_button(
        label="⬇️ Exportar a Excel (.xlsx)",
        data=excel_bytes,
        file_name="skycep_alerts.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.caption(f"{len(df)} filas cargadas.")
else:
    st.info("No hay datos para exportar todavía. Trae alertas o usa el inyector.")
st.markdown("</div>", unsafe_allow_html=True)

# ===== Charts & feed =====
c1, c2 = st.columns([2,1])
with c1:
    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.subheader("Tendencias de alertas")
    if not df.empty and "ts" in df.columns:
        df["ts_dt"] = pd.to_datetime(df["ts"], unit="s")
        agg = (
            df.groupby(pd.Grouper(key="ts_dt", freq="1min"))[["type"]]
              .count()
              .rename(columns={"type": "count"})
              .reset_index()
        )
        line = (
            alt.Chart(agg)
            .mark_area(opacity=0.5)
            .encode(
                x="ts_dt:T",
                y="count:Q",
                tooltip=["ts_dt:T", "count:Q"]
            )
            .properties(height=240)
        )
        st.altair_chart(line, use_container_width=True)
    else:
        st.info("Sin datos para graficar aún.")
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.subheader("Por tipo")
    if not df.empty and "type" in df.columns:
        bytype = df.groupby("type").size().reset_index(name="count")
        bar = (
            alt.Chart(bytype)
            .mark_bar()
            .encode(
                x="count:Q",
                y=alt.Y("type:N", sort='-x'),
                tooltip=["type", "count"]
            )
            .properties(height=240)
        )
        st.altair_chart(bar, use_container_width=True)
    else:
        st.info("Sin datos por tipo.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)

st.markdown("<div class='block'>", unsafe_allow_html=True)
st.subheader("Feed de alertas (recientes)")
if not df.empty:
    df = df.sort_values("ts", ascending=False).head(int(n))
    for _, row in df.iterrows():
        when = ""
        try:
            when = humanize.naturaltime(time.time() - float(row["ts"]))
        except Exception:
            pass
        html = (
            "<div class='feed'>"
            "<div class='item'>"
            "<div class='top'>"
            "<div class='type'>ALERTA: " + str(row.get('type','alert')) + "</div>"
            "<div class='small'>" + when + "</div>"
            "</div>"
            "<div class='small'>Regla: <b>" + str(row.get('rule','')) + "</b> — Vuelo: <b>" + str(row.get('id','')) + "</b></div>"
        )
        st.markdown(html, unsafe_allow_html=True)
        keys = [k for k in ["alt","vy","spd","y"] if k in row and row[k] is not None]
        if keys:
            cols = st.columns(len(keys))
            for i,k in enumerate(keys):
                with cols[i]:
                    try:
                        val = f"{float(row[k]):.2f}"
                    except Exception:
                        val = str(row[k])
                    st.metric(k.upper(), val)
        st.markdown("</div></div>", unsafe_allow_html=True)
else:
    st.info("Aún no hay alertas. Usa el inyector o tu simulador.")
st.markdown("</div>", unsafe_allow_html=True)
