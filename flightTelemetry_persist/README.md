# flightTelemetry — Persistente (SQLite) + export por rango + alertas ampliadas

## Servidor (API + Dashboard)
```powershell
cd "C:\ruta\flightTelemetry_persist"
.\start.ps1            # lanza en 127.0.0.1:8000
```
Abre: http://127.0.0.1:8000

## Streamer (publica CSV a /ingest)
```powershell
.\start_streamer.ps1                 # usa 127.0.0.1:8000
# o: .\start_streamer.ps1 -ApiUrl "http://127.0.0.1:18000"
```

## Stub de simulador (opcional)
```powershell
.\start_stub_simulator.ps1           # genera logs\telemetry_*.csv
```

## Exportar CSV con filtros
- `GET /export.csv?n=900` (últimos N)
- `GET /export.csv?from_ts=1730000000&to_ts=1730003600` (epoch seg)
- `GET /export.csv?from_ts=2025-10-21T18:00:00Z&to_ts=2025-10-21T19:00:00Z` (ISO-8601)

## Alertas demo
- high_pitch_attitude (>|0.5| rad)
- high_bank_angle (>|0.6| rad)
- hard_landing_risk (alt<20 m y Vv<-1.2 m/s)
- stall_risk (vel < 15 m/s)
- overspeed_low_altitude (vel>80 m/s y alt<50 m)
- engine_out_low_altitude (motor OFF y alt<100 m)

Ajusta umbrales en `main.py` si lo necesitas.
