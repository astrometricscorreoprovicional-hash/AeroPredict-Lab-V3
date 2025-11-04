
# AeroPredict Lab — v3 (NumPy + FastAPI + Streamlit)

**Novedades v3**
- **K-fold CV** (`/train_cv`) con reporte por fold y promedio (AUC-ROC/PR).
- **Calibración Platt** (`/calibrate`) y uso automático en `/predict*` si existe `models/calib.json`.
- **Experiment log CSV** (`data/experiments.csv`) con hiperparámetros y métricas.
- **Tests** (`pytest`) y configuración **pre-commit** (black/mypy/isort).
- Dashboard con pestaña **CV & Calibración** (reporte y gráfico de fiabilidad).

## Arranque (Windows)
1) API: `start_api.cmd`  → http://127.0.0.1:8020
2) Dashboard: `start_dashboard.cmd` → http://localhost:8501

## Endpoints clave
- `POST /train_cv` → entrena con K folds, devuelve por-fold + medias.
- `POST /calibrate` → ajusta Platt (logístico) sobre un conjunto de validación.
- `POST /train` — entrenamiento simple.
- `POST /predict` y `POST /predict/batch` — usan calibración si existe.
- `GET /metrics/summary` — últimas métricas y runs (desde CSV).
- `GET /model/card` y `/model/download` — documentación + binario.

## Logs
- CSV: `data/experiments.csv`
- Model: `models/model.npz`, stats: `models/stats.json`, calibración: `models/calib.json`
