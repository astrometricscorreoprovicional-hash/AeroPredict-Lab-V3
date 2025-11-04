# dashboard/app.py — SkyCPA Radar v9.4 (persistencia en disco + auto-refresh + pydeck + Auto-Demo)
import os, io, time, json, pathlib
import requests
import pandas as pd
import numpy as np
import streamlit as st
import pydeck as pdk

API = os.environ.get("API_URL", "http://127.0.0.1:8010")
st.set_page_config(
    page_title="SkyCPA Radar — v9.4",
    page_icon="assets/favicon.png" if os.path.exists("assets/favicon.png") else "🛰️",
    layout="wide",
)

# -------------------- Estilos --------------------
st.markdown("""
<style>
.pill{padding:.35rem .6rem;border-radius:999px;border:1px solid #e5efff;
      background:linear-gradient(180deg,#f2f7ff 0%,#e9f1ff 100%);display:inline-flex;gap:.4rem}
.ok{color:#1f7a44;border-color:#cfeadb;background:linear-gradient(#ebfff3,#e2ffef)}
.warn{color:#a36b00;border-color:#ffe3b3;background:linear-gradient(#fff7e6,#fff0cf)}
.muted{color:#64748b}
.kpi{padding:14px 16px;border-radius:14px;border:1px solid #e6eefc;background:white;
     box-shadow:0 .5px 2px rgba(16,24,40,.05)}
.kpi .v{font-size:1.35rem;font-weight:700}
.kpi .l{font-size:.85rem;color:#6b7280}
</style>
""", unsafe_allow_html=True)

# -------------------- Persistencia en disco (map view) --------------------
PERSIST_PATH = pathlib.Path(__file__).resolve().parent / ".skycpa_map_view.json"

def persist_view_to_disk(view: dict):
    try:
        PERSIST_PATH.write_text(json.dumps(view, ensure_ascii=False))
    except Exception:
        pass

def load_view_from_disk() -> dict | None:
    try:
        if PERSIST_PATH.exists():
            return json.loads(PERSIST_PATH.read_text())
    except Exception:
        pass
    return None

# --- Estado de la vista del mapa ---
if "map_view_locked" not in st.session_state:
    st.session_state.map_view_locked = False
if "map_view" not in st.session_state:
    st.session_state.map_view = dict(lat=None, lon=None, zoom=9, bearing=0, pitch=35)

# si no hay vista, intenta restaurar de disco
if st.session_state.map_view["lat"] is None:
    disk_view = load_view_from_disk()
    if isinstance(disk_view, dict):
        for k in ["lat","lon","zoom","bearing","pitch"]:
            if disk_view.get(k) is not None:
                st.session_state.map_view[k] = disk_view.get(k)

# -------------------- Auto-refresh helper --------------------
def do_autorefresh(enabled: bool, seconds: int):
    fn = getattr(st, "autorefresh", None)
    if enabled and seconds > 0:
        if callable(fn):
            fn(interval=seconds * 1000, key="auto_refresh_key")
        else:
            st.markdown(
                f"""
                <script>
                  setTimeout(function() {{
                    window.location.reload();
                  }}, {int(seconds*1000)});
                </script>
                """,
                unsafe_allow_html=True,
            )

# -------------------- helpers HTTP/UI --------------------
def toast_ok(msg):   st.toast(msg, icon="✅")
def toast_warn(msg): st.toast(msg, icon="⚠️")
def toast_err(msg):  st.toast(msg, icon="❌")

def safe_get(path, params=None, timeout=20):
    try:
        t0 = time.time(); r = requests.get(f"{API}{path}", params=params, timeout=timeout); r.raise_for_status()
        return True, r, (time.time() - t0) * 1000
    except Exception as e:
        return False, e, 0.0

def safe_post(path, payload=None, timeout=40):
    try:
        t0 = time.time(); r = requests.post(f"{API}{path}", json=payload, timeout=timeout); r.raise_for_status()
        return True, r, (time.time() - t0) * 1000
    except Exception as e:
        return False, e, 0.0

def df_pick(df: pd.DataFrame, prefer: list[str], max_cols=6):
    cols = [c for c in prefer if c in df.columns]
    for c in df.columns:
        if c not in cols and len(cols) < max_cols: cols.append(c)
    return df[cols] if cols else df

def number_from_any(d: dict) -> int | float | None:
    for v in d.values():
        if isinstance(v, (int, float)): return v
        if isinstance(v, dict):
            n = number_from_any(v)
            if n is not None: return n
    return None

# -------------------- Header --------------------
lc, rc = st.columns([3,2])
with lc:
    st.markdown("### 🛰️ **SkyCPA Radar — v9.4**  <span class='muted'>(SQLite + Time Range)</span>", unsafe_allow_html=True)
with rc:
    API = st.text_input("API URL", value=API)

# Auto-refresh (cabecera)
ar1, ar2 = st.columns([1,1])
auto_refresh_on  = ar1.toggle("Auto-refresh", value=False, help="Actualiza automáticamente el panel")
auto_refresh_sec = ar2.slider("Intervalo (s)", 3, 60, 10)
do_autorefresh(auto_refresh_on, auto_refresh_sec)

# Controles de vista (candado)
mv1, mv2, mv3, mv4, mv5 = st.columns([1,1,1,1,1])
st.session_state.map_view_locked = mv1.toggle("🔒 Bloquear vista", value=st.session_state.map_view_locked,
                                              help="Conservar centro/zoom al refrescar")
if st.session_state.map_view_locked:
    st.session_state.map_view["zoom"]    = mv2.slider("Zoom",   5, 15, st.session_state.map_view["zoom"])
    st.session_state.map_view["bearing"] = mv3.slider("Rumbo",  0, 360, st.session_state.map_view["bearing"])
    st.session_state.map_view["pitch"]   = mv4.slider("Pitch",  0, 60,  st.session_state.map_view["pitch"])
    if mv5.button("Re-centrar"):
        st.session_state.map_view["lat"] = None
        st.session_state.map_view["lon"] = None
    persist_view_to_disk(st.session_state.map_view)

# Health
ok, resp, dt = safe_get("/health")
row = st.columns(4)
if ok:
    h = resp.json()
    row[0].markdown("<span class='pill ok'>API OK</span>", unsafe_allow_html=True)
    row[1].markdown(f"<span class='pill'>v{h.get('version','')}</span>", unsafe_allow_html=True)
    row[2].markdown(f"<span class='pill'>rows: {h.get('db_rows','—')}</span>", unsafe_allow_html=True)
    row[3].markdown(f"<span class='pill muted'>{dt:.0f} ms</span>", unsafe_allow_html=True)
else:
    row[0].markdown("<span class='pill warn'>API no responde</span>", unsafe_allow_html=True)

st.divider()

# -------------------- Filtros + Acciones --------------------
c1, c2, c3, c4, c5, c6 = st.columns(6)
minutes  = c1.slider("Ventana histórico (min)", 5, 180, 30, step=5)
lat_min  = c2.text_input("lat_min", "")
lat_max  = c3.text_input("lat_max", "")
lon_min  = c4.text_input("lon_min", "")
lon_max  = c5.text_input("lon_max", "")
since_min= c6.number_input("since_min (tráfico)", 1, 240, minutes)

a1, a2, a3, a4 = st.columns([1,1,2,4])
seed_n   = a1.number_input("Seed N", 5, 500, 25, step=5)
step_rep = a2.number_input("Step reps", 1, 200, 25, step=5)
auto_rep = a3.number_input("Auto-Demo steps", 1, 300, 60, step=10)

# Seed
if a1.button("Seed (N)"):
    ok, r, _ = safe_post("/seed", {"n_aircraft": int(seed_n)})
    if not ok: ok, r, _ = safe_get("/seed", {"n": int(seed_n)})
    if ok:
        js = r.json() if hasattr(r, "json") else {}
        n = number_from_any(js) or seed_n
        a1.markdown(f"<div class='kpi'><div class='l'>Semillas</div><div class='v'>{int(n)}</div></div>", unsafe_allow_html=True)
        st.toast("Semillas creadas", icon="✅")
    else:
        st.toast(f"Seed falló: {r}", icon="❌")

# Step
if a2.button("Step ▶"):
    ok, r, _ = safe_post("/seed/step", {"reps": int(step_rep)})
    if not ok: ok, r, _ = safe_get("/seed/step", {"reps": int(step_rep)})
    if ok:
        js = r.json() if hasattr(r, "json") else {}
        moved = number_from_any(js) or step_rep
        a2.markdown(f"<div class='kpi'><div class='l'>Actualizaciones</div><div class='v'>{int(moved)}</div></div>", unsafe_allow_html=True)
        st.toast("Step ejecutado", icon="✅")
    else:
        st.toast(f"Step falló: {r}", icon="❌")

# Auto-Demo: seed + múltiples steps + refresco UI
def do_auto_demo(n_seed: int, reps: int):
    ok1, r1, _ = safe_post("/seed", {"n_aircraft": int(n_seed)})
    if not ok1: ok1, r1, _ = safe_get("/seed", {"n": int(n_seed)})
    if not ok1: return False, "seed_error"
    done = 0
    chunk = max(1, reps // 6)
    for _ in range(0, reps, chunk):
        ok2, _, _ = safe_post("/seed/step", {"reps": int(chunk)})
        if not ok2: ok2, _, _ = safe_get("/seed/step", {"reps": int(chunk)})
        if not ok2: break
        done += chunk
        time.sleep(0.15)
    # ping rápido
    safe_get("/traffic", {"since_min": 5}); safe_get("/history/window", {"minutes": 5})
    return True, done

if a3.button("Auto-Demo 🚀"):
    okd, done = do_auto_demo(int(seed_n), int(auto_rep))
    if okd:
        a3.markdown(f"<div class='kpi'><div class='l'>Auto-Demo</div><div class='v'>{int(done)} steps</div></div>", unsafe_allow_html=True)
        st.toast("Demo inyectada y panel refrescado", icon="✅")
        st.rerun()
    else:
        st.toast("Auto-Demo falló (¿/seed o /seed/step ausentes?)", icon="❌")

with a4:
    st.caption("👆 **Auto-Demo** si arrancas vacío: siembra N aeronaves y avanza varias veces; luego refresca paneles.")

# -------------------- Tabs --------------------
tab_map, tab_conf, tab_hist, tab_exp = st.tabs(["🗺️ Mapa (pydeck)", "⚠️ Conflictos", "🕓 Histórico", "🧰 Exportar"])

# === TAB MAPA ===
with tab_map:
    st.subheader("Mapa — puntos + heatmap + arcos (si hay columnas)")
    params = {"since_min": int(since_min)}
    for k, v in {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max}.items():
        if v.strip(): params[k] = v.strip()
    ok, r, _ = safe_get("/traffic", params)
    if not ok:
        st.warning("No se pudo consultar /traffic.")
    else:
        raw = r.json()
        df = pd.DataFrame(raw) if isinstance(raw, list) else pd.DataFrame(raw.get("value", []))
        if df.empty:
            st.info("Sin tráfico en el rango.")
        else:
            lat = next((c for c in ["lat","latitude","y","lat_deg"] if c in df.columns), None)
            lon = next((c for c in ["lon","longitude","x","lon_deg"] if c in df.columns), None)
            ident  = next((c for c in ["id","icao","callsign"] if c in df.columns), None)
            alt = next((c for c in ["alt","altitude","h"] if c in df.columns), None)
            spd = next((c for c in ["spd","speed","gs"] if c in df.columns), None)
            if not (lat and lon):
                st.error("No hay columnas lat/lon.")
            else:
                # centro (usa estado si está bloqueado, si no calcula y guarda)
                if st.session_state.map_view_locked and st.session_state.map_view["lat"] is not None:
                    center_lat = st.session_state.map_view["lat"]
                    center_lon = st.session_state.map_view["lon"]
                else:
                    center_lat = float(df[lat].astype(float).median())
                    center_lon = float(df[lon].astype(float).median())
                    if st.session_state.map_view_locked:
                        st.session_state.map_view["lat"] = center_lat
                        st.session_state.map_view["lon"] = center_lon
                        persist_view_to_disk(st.session_state.map_view)

                zoom    = st.session_state.map_view["zoom"]
                bearing = st.session_state.map_view["bearing"]
                pitch   = st.session_state.map_view["pitch"]

                layers = [
                    pdk.Layer("ScatterplotLayer", data=df, get_position=f"[{lon},{lat}]", get_radius=60,
                              pickable=True, radius_min_pixels=2, radius_max_pixels=100)
                ]
                if len(df) >= 10:
                    layers.append(pdk.Layer("HeatmapLayer", data=df, get_position=f"[{lon},{lat}]",
                                            aggregation="MEAN", opacity=0.35))

                # arcos si existen columnas a_lat/a_lon/b_lat/b_lon (o variantes)
                arc_cols = ["a_lat","a_lon","b_lat","b_lon"]
                ok_arcs = all(c in df.columns for c in arc_cols)
                if not ok_arcs:
                    altc = ["a_latitude","a_longitude","b_latitude","b_longitude"]
                    ok_arcs = all(c in df.columns for c in altc)
                    if ok_arcs: arc_cols = altc
                if ok_arcs:
                    arcs = df[[*arc_cols]].dropna().rename(columns={
                        arc_cols[0]:"a_lat", arc_cols[1]:"a_lon",
                        arc_cols[2]:"b_lat", arc_cols[3]:"b_lon",
                    })
                    layers.append(pdk.Layer("ArcLayer", data=arcs,
                                            get_source_position='[a_lon,a_lat]',
                                            get_target_position='[b_lon,b_lat]',
                                            get_source_color=[0,128,255],
                                            get_target_color=[255,64,0],
                                            get_width=2, great_circle=True, pickable=True))

                view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon,
                                           zoom=zoom, bearing=bearing, pitch=pitch)
                st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state, map_style="light"))
            st.dataframe(df_pick(df, [ident, lat, lon, alt, spd, "hdg","ts"]), use_container_width=True, hide_index=True)

# === TAB CONFLICTOS ===
with tab_conf:
    st.subheader("Conflictos")
    q = {"since_min": int(minutes)}
    ok, r, _ = safe_get("/conflicts", q)
    if ok:
        js = r.json()
        df = pd.DataFrame(js) if isinstance(js, list) else pd.DataFrame(js.get("value", []))
        if df.empty:
            st.success("✅ Sin conflictos en la ventana.")
        else:
            st.dataframe(df_pick(df, ["a","b","risk","sep_nm","vert_ft","ts"]), use_container_width=True, hide_index=True)
            c = st.columns(3)
            c[0].markdown(f"<div class='kpi'><div class='l'>Total</div><div class='v'>{len(df)}</div></div>", unsafe_allow_html=True)
            c[1].markdown(f"<div class='kpi'><div class='l'>Máx riesgo</div><div class='v'>{df.get('risk',pd.Series([0])).max():.2f}</div></div>", unsafe_allow_html=True)
            c[2].markdown(f"<div class='kpi'><div class='l'>Min sep (NM)</div><div class='v'>{df.get('sep_nm',pd.Series([np.nan])).min()}</div></div>", unsafe_allow_html=True)
    else:
        st.warning("No se pudo consultar /conflicts.")

# === TAB HISTÓRICO ===
with tab_hist:
    st.subheader("Histórico (N minutos)")
    params = {"minutes": int(minutes)}
    for k, v in {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max}.items():
        if v.strip(): params[k] = v.strip()
    ok, r, _ = safe_get("/history/window", params)
    if ok:
        js = r.json()
        df = pd.DataFrame(js) if isinstance(js, list) else pd.DataFrame(js.get("value", []))
        if df.empty:
            st.info("Sin registros para la ventana.")
        else:
            if "ts" in df.columns:
                try:
                    df["_t"] = pd.to_datetime(df["ts"], unit="s")
                    st.line_chart(df.set_index("_t")[[c for c in ["alt","spd","vs","risk"] if c in df.columns]])
                except Exception:
                    pass
            st.dataframe(df_pick(df, ["id","ts","lat","lon","alt","spd","hdg"]), use_container_width=True, hide_index=True)
    else:
        st.warning("No se pudo consultar /history/window.")

# === TAB EXPORTAR ===
with tab_exp:
    st.subheader("Exportaciones")
    c1, c2, c3 = st.columns(3)
    def download_endpoint(label, path, params):
        ok, r, dt = safe_get(path, params)
        if not ok: st.error(f"{label}: error"); return
        st.download_button(label, data=r.content, file_name=path.replace("/","_") + ".bin")
        st.caption(f"{dt:.0f} ms")
    with c1:
        st.write("CSV")
        download_endpoint("Traffic CSV", "/export/csv/traffic", {"since_min": int(since_min)})
        download_endpoint("Conflicts CSV", "/export/csv/conflicts", {"minutes": int(minutes)})
        download_endpoint("History CSV", "/export/csv/history", {"minutes": int(minutes)})
    with c2:
        st.write("XLSX / Parquet")
        download_endpoint("Export XLSX", "/export/xlsx", {"minutes": int(minutes)})
        download_endpoint("Export Parquet", "/export/parquet", {"minutes": int(minutes)})
    with c3:
        st.write("PDF")
        download_endpoint("Export PDF", "/export/pdf", {"minutes": int(minutes)})

st.caption("Tema propio + pydeck; Auto-Demo; persistencia de vista en disco; autorefresco opcional.")
