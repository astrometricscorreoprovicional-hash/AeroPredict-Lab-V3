
import os, requests, streamlit as st, pandas as pd, numpy as np, matplotlib.pyplot as plt

API = os.environ.get("API_URL","http://127.0.0.1:8020")
st.set_page_config(page_title="AeroPredict Lab — v3", page_icon="assets/favicon.png" if os.path.exists("assets/favicon.png") else "✈️", layout="wide")
st.title("🧪 AeroPredict Lab — v3 (K-fold + Calibración)")

st.sidebar.caption(f"API: `{API}`")

tab1, tab2, tab3, tab4 = st.tabs(["Inferencia", "Entrenar", "CV & Calibración", "Métricas/Logs"])

with tab1:
    st.subheader("Inferencia puntual")
    cols = st.columns(7)
    vals = [
        cols[0].number_input("airspeed",  value=70.0),
        cols[1].number_input("altitude",  value=300.0),
        cols[2].number_input("vspeed",    value=-1.5),
        cols[3].number_input("pitch",     value=0.03, format="%.4f"),
        cols[4].number_input("roll",      value=0.02, format="%.4f"),
        cols[5].number_input("wind_x",    value=0.0),
        cols[6].number_input("wind_y",    value=0.0),
    ]
    if st.button("Predecir", type="primary"):
        payload = dict(airspeed=vals[0], altitude=vals[1], vspeed=vals[2], pitch=vals[3], roll=vals[4], wind_x=vals[5], wind_y=vals[6])
        r = requests.post(f"{API}/predict", json=payload, timeout=15).json()
        st.metric("Prob. inestable", f"{r['prob_unstable']:.2%}")
        st.caption("Usa calibración Platt si fue entrenada.")

with tab2:
    st.subheader("Entrenamiento simple")
    n_samples = st.number_input("n_samples", 2000, 300000, 8000, step=1000)
    lr        = st.number_input("lr", 0.0001, 1.0, 0.05)
    epochs    = st.number_input("epochs", 50, 3000, 400, step=50)
    l2        = st.number_input("l2", 1e-6, 1e-1, 1e-3, format="%.6f")
    notes     = st.text_input("notes", "")
    if st.button("Entrenar (simple)", type="primary"):
        payload = dict(n_samples=int(n_samples), lr=float(lr), epochs=int(epochs), l2=float(l2), notes=notes)
        res = requests.post(f"{API}/train", json=payload, timeout=120).json()
        st.success(res)

with tab3:
    st.subheader("K-fold CV")
    k = st.slider("k_folds", 2, 10, 5)
    n_samples = st.number_input("n_samples (CV)", 4000, 300000, 10000, step=2000)
    lr        = st.number_input("lr (CV)", 0.0001, 1.0, 0.05, key="lrcv")
    epochs    = st.number_input("epochs (CV)", 50, 3000, 400, step=50, key="epcv")
    l2        = st.number_input("l2 (CV)", 1e-6, 1e-1, 1e-3, format="%.6f", key="l2cv")
    if st.button("Entrenar CV", type="primary"):
        payload = dict(n_samples=int(n_samples), k_folds=int(k), lr=float(lr), epochs=int(epochs), l2=float(l2))
        js = requests.post(f"{API}/train_cv", json=payload, timeout=300).json()
        st.dataframe(pd.DataFrame(js["per_fold"]), use_container_width=True)
        st.success(js["summary"])

    st.divider()
    st.subheader("Calibración Platt")
    if st.button("Calibrar (auto val set)"):
        js = requests.post(f"{API}/calibrate", timeout=120).json()
        st.info(js)

    st.caption("La calibración ajusta las probabilidades para que reflejen mejor la frecuencia observada.")

with tab4:
    st.subheader("Experiment log (CSV)")
    path = "data/experiments.csv"
    try:
        df = pd.read_csv(path)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.info("Aún no hay registros. Entrena o CV para generar filas.")
