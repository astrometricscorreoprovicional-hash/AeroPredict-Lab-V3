# SkyCPA Radar v9.4 — UI con persistencia en disco

Incluye:
- Tema Streamlit (claro-azulado)
- Pydeck (puntos, heatmap, arcos si hay columnas)
- Auto-Demo (seed + steps)
- Auto-refresh opcional
- **Persistencia de vista del mapa en disco** (`dashboard/.skycpa_map_view.json`)

## Arranque
1. Exporta la URL del backend (ajusta puerto si es distinto):
```powershell
$env:API_URL = "http://127.0.0.1:8010"
```
2. Lanza el panel:
```powershell
python -m streamlit run dashboard/app.py
```
