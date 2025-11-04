# NEBULA‑HDT v1 — Hybrid Digital Twin for Aviation & Space

Gemelo digital **híbrido** (física + ML) con asimilación (EKF/UKF/EnKF), FDIR, alcance/planificación y cuantificación de incertidumbre. Incluye API + UI para demos E2E y escenarios Tierra/Marte/LEO.

## Quickstart
```ps1
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
.\start_api.cmd     # http://127.0.0.1:8015
.\start_ui.cmd      # http://127.0.0.1:8515
```

## Endpoints
- `POST /simulate` → estados + incertidumbre (demo)
- `POST /assimilate` → NEES/NMRSE (demo)
- `POST /faults` → alarmas CUSUM (demo)
- `POST /reachability` → footprint GeoJSON (demo)

## Demo
1. UI → **Earth/Engine-out** → *Run demo*
2. Revisa fan plot, alarmas y footprint de alcance.

## Roadmap
- Surrogates aerodinámicos (MLP/XGBoost) y PINNs
- Planificación con terreno real (DEM) y riesgo viento
- Propagación orbital con J2 completa y conjunction checks

### LEO demo
- Escenario `leo_sat` con dinámica de dos-cuerpos (ECI). Ajusta `r0_km` y `v0_kms` en la UI.

- **UKF LEO**: La UI genera mediciones ruidosas de altitud/velocidad, llama a `/assimilate_ukf` y muestra **NEES**.

## Tests
- Ejecuta `python -m pytest -q` para validar UKF y estabilidad de NEES.

- **Presets UKF (LEO)**: Sidebar con *Aggressive / Nominal / Conservative / Custom* para Q/R.

## Integraciones nuevas
- **GeoJSON export**: `POST /export_geojson` y `GET /geojson/latest`. La UI exporta **ground-track LEO** y **footprint/trajectory** Earth/Mars.
- **LEO presets**: `circular`, `elliptic`, `hohmann` (vis-viva simplificado).
- **Run log**: CSV en `logs/nebula_runs.csv` con parámetros y métricas (NEES).
- **UKF ATM**: endpoint `/assimilate_ukf_atm` (alt [m], vd [m/s]) + UI con presets Q/R y NEES target.
