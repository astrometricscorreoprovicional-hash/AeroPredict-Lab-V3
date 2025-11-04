from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
import numpy as np

# import minimal orbital step
from core.orbital import twobody_step, MU_EARTH, R_E

app = FastAPI(title="NEBULA-HDT API", version="1.1.0")
from util.geojson import linestring, polygon, feature_collection, save_geojson
from util.runlog import append_run
from estimation.ukf_atm import ukf_filter_atm
_last_geojson_path = None


ScenarioName = Literal["earth_engineout", "mars_uav", "leo_sat"]

class InitialState(BaseModel):
    # Aircraft-like initial state (for earth/mars)
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    vn: float = 0.0
    ve: float = 0.0
    vd: float = 0.0
    q: List[float] = Field(default_factory=lambda: [1,0,0,0])
    p: float = 0.0
    q_rate: float = 0.0
    r: float = 0.0
    # Orbit-like initial state (for leo_sat), defaults to ~400 km circular
    r0_km: float = 6771.0
    v0_kms: float = 7.67

class SimRequest(BaseModel):
    scenario: ScenarioName
    duration_s: float = 60.0
    dt_s: float = 0.5
    initial_state: InitialState
    preset: Optional[str] = None   # e.g., 'circular', 'elliptic', 'hohmann' for LEO
    controls: Optional[List[Dict[str, float]]] = None
    disturbances: Optional[Dict[str, Any]] = None

class AssimilateRequest(BaseModel):
    model: Literal["ekf", "ukf", "enkf"] = "ukf"
    meas: List[Dict[str, Any]]
    Q: Optional[Dict[str, float]] = None
    initial_belief: Optional[Dict[str, Any]] = None

class FaultsRequest(BaseModel):
    residuals: List[Dict[str, float]]
    spec: Dict[str, Any] = {"methods":["cusum","bayes"]}

class ReachabilityRequest(BaseModel):
    state: Dict[str, float]
    env: Dict[str, Any] = {}
    horizon_s: float = 90.0

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/simulate")
def simulate(req: SimRequest):
    n = int(req.duration_s / req.dt_s) + 1
    t = np.linspace(0.0, req.duration_s, n)

    if req.scenario == "leo_sat":
        # Presets for LEO
        mu = MU_EARTH
        if req.preset == "circular" or req.preset is None:
            r_km = req.initial_state.r0_km
            v_kms = np.sqrt(mu / (r_km*1e3)) / 1e3
            r0 = np.array([r_km*1e3, 0.0, 0.0])
            v0 = np.array([0.0, v_kms*1e3, 0.0])
        elif req.preset == "elliptic":
            rp = 6771.0 * 1e3
            ra = 7371.0 * 1e3
            a = 0.5*(rp+ra)
            v_per = np.sqrt(mu*(2/rp - 1/a))
            r0 = np.array([rp, 0.0, 0.0])
            v0 = np.array([0.0, v_per, 0.0])
        elif req.preset == "hohmann":
            r1 = 6771.0 * 1e3
            r2 = 7071.0 * 1e3
            a = 0.5*(r1+r2)
            v_per = np.sqrt(mu*(2/r1 - 1/a))
            r0 = np.array([r1, 0.0, 0.0])
            v0 = np.array([0.0, v_per, 0.0])
        else:
            r0 = np.array([req.initial_state.r0_km*1e3, 0.0, 0.0])
            v0 = np.array([0.0, req.initial_state.v0_kms*1e3, 0.0])
        r, v = r0.copy(), v0.copy()
        xs, ys, zs, alts_km, speeds_kms = [], [], [], [], []
        for _ in t:
            xs.append(r[0]); ys.append(r[1]); zs.append(r[2])
            alts_km.append(np.linalg.norm(r)/1e3 - R_E/1e3)
            speeds_kms.append(np.linalg.norm(v)/1e3)
            r, v = twobody_step(r, v, req.dt_s)
        # Synthetic 1σ uncertainty grows slowly
        sigma_alt = 1.0 + 0.002*t
        return {
            "time": t.tolist(),
            "states": {
                "x_m": xs, "y_m": ys, "z_m": zs,
                "alt_km": alts_km, "speed_kms": speeds_kms
            },
            "uncertainty": {"alt_sigma_km": sigma_alt.tolist()},
            "meta": {"scenario": req.scenario, "dt_s": req.dt_s}
        }

    # Aircraft-like demo (earth/mars): descent with sine perturbation
    alt = req.initial_state.alt - 0.5 * t + 5*np.sin(0.05*2*np.pi*t)
    vn = np.zeros_like(t)
    ve = np.zeros_like(t)
    vd = -np.gradient(alt, t)
    sigma_alt = 3.0 + 0.02*t
    return {
        "time": t.tolist(),
        "states": {"alt": alt.tolist(), "vn": vn.tolist(), "ve": ve.tolist(), "vd": vd.tolist()},
        "uncertainty": {"alt_sigma": sigma_alt.tolist()},
        "meta": {"scenario": req.scenario, "dt_s": req.dt_s}
    }

@app.post("/assimilate")
def assimilate(req: AssimilateRequest):
    n = max(1, len(req.meas))
    nees = 1.0 + 2.0/np.sqrt(n)
    nrmse = 0.05 + 0.4/np.sqrt(n)
    return {"state_est": {}, "cov": {}, "nees": nees, "nrmse": nrmse}

@app.post("/faults")
def faults(req: FaultsRequest):
    vals = [r.get("value", 0.0) for r in req.residuals]
    mean_res = float(np.mean(vals)) if vals else 0.0
    alarms = []
    if mean_res > 0.8:
        alarms.append({"t": 0.0, "type": "engine_out", "prob": 0.92, "severity": "red"})
    return {"alarms": alarms, "residual_mean": mean_res}

@app.post("/reachability")
def reachability(req: ReachabilityRequest):
    lat0 = req.state.get("lat", 0.0)
    lon0 = req.state.get("lon", 0.0)
    r_km = 3.0 + 0.01*req.horizon_s
    polygon = [[lon0-0.02, lat0-0.02],[lon0+0.02, lat0-0.02],[lon0+0.02, lat0+0.02],[lon0-0.02, lat0+0.02],[lon0-0.02, lat0-0.02]]
    return {"footprint": {"type":"Polygon","coordinates":[polygon]}, "radius_km": r_km}


from estimation.ukf import ukf_filter
from fastapi import HTTPException

class UKFRequest(BaseModel):
    time: List[float]
    z_alt_km: List[float]
    z_speed_kms: List[float]
    Q_alt: float = 1e-3
    Q_speed: float = 1e-4
    R_alt: float = 5e-3
    R_speed: float = 1e-3
    x0_alt: float = 400.0
    x0_speed: float = 7.67
    P0_alt: float = 1.0
    P0_speed: float = 0.1

@app.post("/assimilate_ukf")
def assimilate_ukf(req: UKFRequest):
    try:
        t = np.asarray(req.time, dtype=float)
        z = np.vstack([req.z_alt_km, req.z_speed_kms]).T
        dt = np.diff(t, prepend=t[0])
        xs, Ps, nees = ukf_filter(
            z_series=z,
            dt_series=dt,
            Q=[req.Q_alt, req.Q_speed],
            R=[req.R_alt, req.R_speed],
            x0=[req.x0_alt, req.x0_speed],
            P0=[req.P0_alt, req.P0_speed],
        )
        return {
            "x_alt_km": xs[:,0].tolist(),
            "x_speed_kms": xs[:,1].tolist(),
            "P_alt": Ps[:,0].tolist(),
            "P_speed": Ps[:,1].tolist(),
            "nees": nees.tolist(),
            "n": int(len(t))
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from fastapi.responses import JSONResponse

@app.post("/export_geojson")
def export_geojson(payload: Dict[str, Any]):
    """Create GeoJSON from provided series or simple footprints.
    payload may include:
      - kind: "trajectory" | "footprint"
      - scenario: "earth_engineout" | "mars_uav" | "leo_sat"
      - coords: list of {lat,lon} (for earth/mars trajectories)
      - origin: {lat,lon} (for footprint square)
      - leo_longitudes: list of lon (deg) with lat=0 for demo ground-track
    """
    kind = payload.get("kind", "trajectory")
    scenario = payload.get("scenario", "earth_engineout")
    feats = []
    if scenario in ("earth_engineout","mars_uav"):
        if kind == "trajectory":
            coords = [[c["lon"], c["lat"]] for c in payload.get("coords", [])]
            feats.append(linestring(coords, {"name":"trajectory","scenario":scenario}))
        else:
            o = payload.get("origin", {"lat":0.0,"lon":0.0})
            d = 0.02
            poly = [[o["lon"]-d,o["lat"]-d],[o["lon"]+d,o["lat"]-d],[o["lon"]+d,o["lat"]+d],[o["lon"]-d,o["lat"]+d],[o["lon"]-d,o["lat"]-d]]
            feats.append(polygon(poly, {"name":"footprint","scenario":scenario}))
    else:
        # LEO: simple equatorial ground-track (lat=0, lon from list)
        if kind == "trajectory":
            lons = payload.get("leo_longitudes", [])
            coords = [[float(l), 0.0] for l in lons]
            feats.append(linestring(coords, {"name":"leo_groundtrack","scenario":"leo_sat"}))
        else:
            feats.append(polygon([[-5,-5],[5,-5],[5,5],[-5,5],[-5,-5]], {"name":"leo_footprint_demo"}))
    fc = feature_collection(feats)
    global _last_geojson_path
    _last_geojson_path = save_geojson(fc, outdir="exports", prefix=f"{scenario}_{kind}")
    return {"saved": _last_geojson_path, "feature_count": len(feats), "feature_collection": fc}

@app.get("/geojson/latest")
def geojson_latest():
    global _last_geojson_path
    if not _last_geojson_path or not os.path.exists(_last_geojson_path):
        return JSONResponse(status_code=404, content={"error":"no geojson exported yet"})
    with open(_last_geojson_path, "r", encoding="utf-8") as f:
        return json.load(f)

from estimation.ukf_atm import ukf_filter_atm

class UKFAtmRequest(BaseModel):
    time: List[float]
    z_alt_m: List[float]
    z_vd_mps: List[float]
    Q_alt: float = 25.0
    Q_vd: float = 0.5
    R_alt: float = 9.0
    R_vd: float = 0.04
    x0_alt: float = 800.0
    x0_vd: float = -0.5
    P0_alt: float = 4.0
    P0_vd: float = 0.25
    scenario: Literal["earth_engineout","mars_uav"] = "earth_engineout"
    preset: Optional[str] = None

@app.post("/assimilate_ukf_atm")
def assimilate_ukf_atm(req: UKFAtmRequest):
    t = np.asarray(req.time, dtype=float)
    z = np.vstack([req.z_alt_m, req.z_vd_mps]).T
    dt = np.diff(t, prepend=t[0])
    xs, Ps, nees = ukf_filter_atm(
        z_series=z, dt_series=dt,
        Q=[req.Q_alt, req.Q_vd],
        R=[req.R_alt, req.R_vd],
        x0=[req.x0_alt, req.x0_vd],
        P0=[req.P0_alt, req.P0_vd],
    )
    nees_avg = float(np.mean(nees)) if len(nees)>0 else 0.0
    nees_max = float(np.max(nees)) if len(nees)>0 else 0.0
    append_run({
        "timestamp": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "scenario": req.scenario,
        "preset": req.preset or "custom",
        "duration_s": float(t[-1]-t[0]) if len(t)>1 else 0.0,
        "dt_s": float(np.mean(dt)) if len(dt)>0 else 0.0,
        "Q_alt": req.Q_alt, "Q_speed": req.Q_vd,
        "R_alt": req.R_alt, "R_speed": req.R_vd,
        "nees_avg": nees_avg, "nees_max": nees_max,
        "n_points": int(len(t))
    })
    return {
        "x_alt_m": xs[:,0].tolist(),
        "x_vd_mps": xs[:,1].tolist(),
        "P_alt": Ps[:,0].tolist(),
        "P_vd": Ps[:,1].tolist(),
        "nees": nees.tolist(),
        "n": int(len(t)),
        "nees_avg": nees_avg, "nees_max": nees_max
    }

from fastapi.responses import RedirectResponse, FileResponse

@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico")
def favicon():
    # serve UI favicon if running from the same folder structure
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "favicon.png")
    path = os.path.abspath(path)
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    return {}
