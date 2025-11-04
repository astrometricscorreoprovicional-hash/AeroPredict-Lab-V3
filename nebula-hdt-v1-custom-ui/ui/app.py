import os, requests, numpy as np, io
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv
import pandas as pd  # para Excel

# --------------------------------------------------------------------
# Intentamos traer reportlab y ImageReader para PDF
# --------------------------------------------------------------------
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader  # 👈 para envolver BytesIO
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

# --------------------------------------------------------------------
# Intentamos detectar kaleido (plotly → imagen)
# --------------------------------------------------------------------
try:
    import kaleido  # noqa: F401
    HAVE_KALEIDO = True
except Exception:
    HAVE_KALEIDO = False

load_dotenv()
API_URL = os.getenv("NEBULA_API_URL", "http://127.0.0.1:8015")

st.set_page_config(page_title="NEBULA-HDT", page_icon="assets/favicon.png", layout="wide")

# --------------------------------------------------------------------
# Estado de sesión
# --------------------------------------------------------------------
if "nebula_last" not in st.session_state:
    st.session_state["nebula_last"] = None
if "nebula_figs" not in st.session_state:
    st.session_state["nebula_figs"] = []  # lista de (titulo, fig)

# --------------------------------------------------------------------
# Header
# --------------------------------------------------------------------
col_logo, col_title, col_right = st.columns([0.1, 0.7, 0.2])
with col_logo:
    st.image("assets/favicon.png", width=32)
with col_title:
    st.markdown(
        "<div style='padding:4px 0'><h1 style='margin:0'>NEBULA-HDT v1</h1>"
        "<p style='margin:0;color:#6b7280'>Hybrid Digital Twin · Aviation & Space</p></div>",
        unsafe_allow_html=True,
    )
with col_right:
    st.markdown(
        f"""
        <div style="text-align:right">
            <span style="font-size:12px;color:#6b7280">API:</span><br/>
            <a href="{API_URL}/docs" target="_blank">/docs</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# --------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------
tab_leo, tab_atm = st.tabs(["🛰️ LEO Satellite", "✈️ Earth / Mars Atmosphere"])

# =========================================================
# LEO TAB
# =========================================================
with tab_leo:
    left, right = st.columns([0.5, 0.5])

    with left:
        st.subheader("Orbit Parameters")
        preset = st.selectbox("Preset", ["circular", "elliptic", "hohmann"], index=0)
        r0_km = st.number_input("Initial radius (km)", 6771.0, step=1.0)
        v0_kms = st.number_input("Initial speed (km/s)", 7.67, step=0.01)
        dur = st.slider("Duration (s)", 60, 7200, 5400)
        dt = st.slider("dt (s)", 1, 30, 10)
        show_3d = st.checkbox("Show 3D orbit", True)

        st.subheader("UKF Settings")
        preset_qr = st.selectbox("Noise preset", ["Aggressive", "Nominal", "Conservative", "Custom"], index=1)
        if preset_qr == "Aggressive":
            Q_alt, Q_spd, R_alt, R_spd = 1e-3, 5e-5, 1e-4, 5e-6
        elif preset_qr == "Conservative":
            Q_alt, Q_spd, R_alt, R_spd = 1e-5, 1e-6, 5e-4, 2e-5
        elif preset_qr == "Custom":
            Q_alt = st.number_input("Q_alt (km^2)", 1e-4, format="%e")
            Q_spd = st.number_input("Q_speed ((km/s)^2)", 1e-5, format="%e")
            R_alt = st.number_input("R_alt (km^2)", 1e-4, format="%e")
            R_spd = st.number_input("R_speed ((km/s)^2)", 1e-6, format="%e")
        else:
            Q_alt, Q_spd, R_alt, R_spd = 1e-4, 1e-5, 1e-4, 1e-6
        nees_target = st.number_input("NEES target (warn above)", 5.0, step=0.5)

        run = st.button("Run LEO demo", type="primary", use_container_width=True)

    with right:
        if run:
            # limpiamos figs anteriores
            st.session_state["nebula_figs"] = []

            # 1) Simulación LEO
            payload = {
                "scenario": "leo_sat",
                "preset": preset,
                "duration_s": float(dur),
                "dt_s": float(dt),
                "initial_state": {"r0_km": float(r0_km), "v0_kms": float(v0_kms)},
            }
            r = requests.post(f"{API_URL}/simulate", json=payload, timeout=60)
            sim = r.json()

            t = np.array(sim["time"])
            alt_km = np.array(sim["states"]["alt_km"])
            speed = np.array(sim["states"]["speed_kms"])
            xs = np.array(sim["states"]["x_m"])
            ys = np.array(sim["states"]["y_m"])
            zs = np.array(sim["states"]["z_m"])

            st.markdown("#### Altitude & Speed (with UKF)")
            c1, c2 = st.columns(2)
            with c1:
                fig1 = go.Figure()
                fig1.add_scatter(x=t, y=alt_km, mode="lines", name="true alt [km]")
                z_alt = (alt_km + np.random.normal(0, 0.01, size=alt_km.shape)).tolist()
                fig1.add_scatter(x=t, y=z_alt, mode="lines", name="meas alt [km]", opacity=0.4)
                fig1.update_layout(xaxis_title="t [s]", yaxis_title="alt [km]")
                st.plotly_chart(fig1, use_container_width=True)
            with c2:
                fig2 = go.Figure()
                fig2.add_scatter(x=t, y=speed, mode="lines", name="true speed [km/s]")
                z_spd = (speed + np.random.normal(0, 0.001, size=speed.shape)).tolist()
                fig2.add_scatter(x=t, y=z_spd, mode="lines", name="meas speed [km/s]", opacity=0.4)
                fig2.update_layout(xaxis_title="t [s]", yaxis_title="speed [km/s]")
                st.plotly_chart(fig2, use_container_width=True)

            # 2) UKF LEO
            ukf_payload = {
                "time": t.tolist(),
                "z_alt_km": z_alt,
                "z_speed_kms": z_spd,
                "Q_alt": float(Q_alt),
                "Q_speed": float(Q_spd),
                "R_alt": float(R_alt),
                "R_speed": float(R_spd),
                "x0_alt": float(alt_km[0]),
                "x0_speed": float(speed[0]),
                "P0_alt": 1.0,
                "P0_speed": 0.1,
            }
            ukf = requests.post(f"{API_URL}/assimilate_ukf", json=ukf_payload, timeout=60).json()

            st.markdown("#### UKF & NEES")
            c3, c4 = st.columns(2)
            with c3:
                fig_alt = go.Figure()
                fig_alt.add_scatter(x=t, y=alt_km, mode="lines", name="true alt [km]")
                fig_alt.add_scatter(x=t, y=z_alt, mode="lines", name="meas alt [km]", opacity=0.4)
                fig_alt.add_scatter(x=t, y=ukf["x_alt_km"], mode="lines", name="UKF alt [km]")
                fig_alt.update_layout(xaxis_title="t [s]", yaxis_title="alt [km]")
                st.plotly_chart(fig_alt, use_container_width=True)
            with c4:
                fig_spd = go.Figure()
                fig_spd.add_scatter(x=t, y=speed, mode="lines", name="true speed [km/s]")
                fig_spd.add_scatter(x=t, y=z_spd, mode="lines", name="meas speed [km/s]", opacity=0.4)
                fig_spd.add_scatter(x=t, y=ukf["x_speed_kms"], mode="lines", name="UKF speed [km/s]")
                fig_spd.update_layout(xaxis_title="t [s]", yaxis_title="speed [km/s]")
                st.plotly_chart(fig_spd, use_container_width=True)

            fig_nees = go.Figure()
            fig_nees.add_scatter(x=t, y=ukf["nees"], mode="lines", name="NEES")
            fig_nees.update_layout(xaxis_title="t [s]", yaxis_title="NEES")
            st.plotly_chart(fig_nees, use_container_width=True)

            nees_avg = float(np.mean(ukf["nees"])) if len(ukf["nees"]) > 0 else 0.0
            nees_max = float(np.max(ukf["nees"])) if len(ukf["nees"]) > 0 else 0.0
            cOK, cMX = st.columns(2)
            cOK.metric("NEES avg", f"{nees_avg:.2f}")
            cMX.metric("NEES max", f"{nees_max:.2f}")
            if nees_max > nees_target:
                st.warning(f"NEES above target (max {nees_max:.2f} > {nees_target:.2f}).")
            else:
                st.success("NEES within target range.")

            st.markdown("#### Export")
            lons = (np.degrees(np.unwrap(np.arctan2(ys, xs))) % 360).tolist()
            if st.button("Export LEO ground-track as GeoJSON", use_container_width=True):
                export = requests.post(
                    f"{API_URL}/export_geojson",
                    json={"kind": "trajectory", "scenario": "leo_sat", "leo_longitudes": lons},
                    timeout=30,
                ).json()
                st.success(f"Saved: {export['saved']}")

            if show_3d:
                st.markdown("#### Orbit 3D (ECI, demo)")
                fig3 = go.Figure(data=[go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name="orbit")])
                fig3.update_layout(
                    scene=dict(xaxis_title="x [m]", yaxis_title="y [m]", zaxis_title="z [m]"),
                    height=500,
                )
                st.plotly_chart(fig3, use_container_width=True)
                # guardamos 3D también
                st.session_state["nebula_figs"].append(("LEO - Orbit 3D", fig3))

            # guardamos último resultado LEO
            st.session_state["nebula_last"] = {
                "mode": "leo",
                "sim": sim,
                "ukf": ukf,
            }
            # registramos figs para PDF
            st.session_state["nebula_figs"].append(("LEO - Altitude", fig1))
            st.session_state["nebula_figs"].append(("LEO - Speed", fig2))
            st.session_state["nebula_figs"].append(("LEO - UKF Alt", fig_alt))
            st.session_state["nebula_figs"].append(("LEO - UKF Speed", fig_spd))
            st.session_state["nebula_figs"].append(("LEO - NEES", fig_nees))

        else:
            st.info("Configura parámetros y pulsa **Run LEO demo**.")

# =========================================================
# ATM TAB
# =========================================================
with tab_atm:
    left, right = st.columns([0.5, 0.5])
    with left:
        st.subheader("Scenario")
        atm_scenario = st.selectbox("Choose", ["earth_engineout", "mars_uav"], index=0)
        alt0 = st.number_input("Initial Altitude (m)", 800.0)
        dur = st.slider("Duration (s)", 10, 240, 60, key="dur_atm")
        dt = st.slider("dt (s)", 1, 100, 20, key="dt_atm") / 100.0

        st.subheader("UKF ATM Settings")
        preset_atm = st.selectbox("Noise preset (ATM)", ["Aggressive", "Nominal", "Conservative", "Custom"], index=1)
        if preset_atm == "Aggressive":
            Q_alt, Q_vd, R_alt, R_vd = 50.0, 1.0, 9.0, 0.04
        elif preset_atm == "Conservative":
            Q_alt, Q_vd, R_alt, R_vd = 10.0, 0.2, 25.0, 0.25
        elif preset_atm == "Custom":
            Q_alt = st.number_input("Q_alt (m^2)", 25.0)
            Q_vd = st.number_input("Q_vd ((m/s)^2)", 0.5)
            R_alt = st.number_input("R_alt (m^2)", 9.0)
            R_vd = st.number_input("R_vd ((m/s)^2)", 0.04)
        else:
            Q_alt, Q_vd, R_alt, R_vd = 25.0, 0.5, 9.0, 0.04
        nees_target_atm = st.number_input("NEES target (ATM)", 5.0, step=0.5)

        run_atm = st.button("Run ATM demo", type="primary", use_container_width=True)

    with right:
        if run_atm:
            # limpiamos figs anteriores
            st.session_state["nebula_figs"] = []

            payload = {
                "scenario": atm_scenario,
                "duration_s": float(dur),
                "dt_s": float(dt),
                "initial_state": {"lat": 37.62, "lon": -122.38, "alt": float(alt0)},
            }
            r = requests.post(f"{API_URL}/simulate", json=payload, timeout=60)
            sim = r.json()
            t = np.array(sim["time"])
            alt = np.array(sim["states"]["alt"])
            sig = np.array(sim["uncertainty"]["alt_sigma"])
            vd = np.array(sim["states"]["vd"])

            st.markdown("#### Altitude (±1σ)")
            fig = go.Figure()
            fig.add_scatter(x=t, y=alt, mode="lines", name="alt")
            fig.add_scatter(
                x=np.concatenate([t, t[::-1]]),
                y=np.concatenate([alt + sig, (alt - sig)[::-1]]),
                fill="toself",
                mode="lines",
                name="±1σ",
                opacity=0.2,
            )
            fig.update_layout(xaxis_title="t [s]", yaxis_title="alt [m]")
            st.plotly_chart(fig, use_container_width=True)

            # UKF ATM
            z_alt = (alt + np.random.normal(0, 3.0, size=alt.shape)).tolist()
            z_vd = (vd + np.random.normal(0, 0.2, size=vd.shape)).tolist()

            ukf_atm_payload = {
                "time": t.tolist(),
                "z_alt_m": z_alt,
                "z_vd_mps": z_vd,
                "Q_alt": float(Q_alt),
                "Q_vd": float(Q_vd),
                "R_alt": float(R_alt),
                "R_vd": float(R_vd),
                "x0_alt": float(alt[0]),
                "x0_vd": float(vd[0]),
                "P0_alt": 4.0,
                "P0_vd": 0.25,
                "scenario": atm_scenario,
                "preset": preset_atm,
            }
            ukf_atm = requests.post(f"{API_URL}/assimilate_ukf_atm", json=ukf_atm_payload, timeout=60).json()

            cA, cB = st.columns(2)
            with cA:
                fig_alt = go.Figure()
                fig_alt.add_scatter(x=t, y=alt, mode="lines", name="true alt [m]")
                fig_alt.add_scatter(x=t, y=z_alt, mode="lines", name="meas alt [m]", opacity=0.4)
                fig_alt.add_scatter(x=t, y=ukf_atm["x_alt_m"], mode="lines", name="UKF alt [m]")
                fig_alt.update_layout(xaxis_title="t [s]", yaxis_title="alt [m]")
                st.plotly_chart(fig_alt, use_container_width=True)
            with cB:
                fig_vd = go.Figure()
                fig_vd.add_scatter(x=t, y=vd, mode="lines", name="true vd [m/s]")
                fig_vd.add_scatter(x=t, y=z_vd, mode="lines", name="meas vd [m/s]", opacity=0.4)
                fig_vd.add_scatter(x=t, y=ukf_atm["x_vd_mps"], mode="lines", name="UKF vd [m/s]")
                fig_vd.update_layout(xaxis_title="t [s]", yaxis_title="vd [m/s]")
                st.plotly_chart(fig_vd, use_container_width=True)

            st.markdown("#### NEES (ATM)")
            figN = go.Figure()
            figN.add_scatter(x=t, y=ukf_atm["nees"], mode="lines", name="NEES")
            st.plotly_chart(figN, use_container_width=True)
            if float(ukf_atm["nees_max"]) > nees_target_atm:
                st.warning(f"NEES above target (max {ukf_atm['nees_max']:.2f} > {nees_target_atm:.2f}).")
            else:
                st.success("NEES within target range (ATM).")

            st.markdown("#### Export")
            if st.button("Export footprint polygon", use_container_width=True):
                export = requests.post(
                    f"{API_URL}/export_geojson",
                    json={
                        "kind": "footprint",
                        "scenario": atm_scenario,
                        "origin": {"lat": 37.62, "lon": -122.38},
                    },
                    timeout=30,
                ).json()
                st.success(f"Saved: {export['saved']}")

            if st.button("Export trajectory (demo)", use_container_width=True):
                coords = [{"lat": 37.62, "lon": -122.38} for _ in t]
                export = requests.post(
                    f"{API_URL}/export_geojson",
                    json={"kind": "trajectory", "scenario": atm_scenario, "coords": coords},
                    timeout=30,
                ).json()
                st.success(f"Saved: {export['saved']}")

            # guardar último resultado ATM
            st.session_state["nebula_last"] = {
                "mode": "atm",
                "sim": sim,
                "ukf": ukf_atm,
            }
            # registrar figs
            st.session_state["nebula_figs"].append(("ATM - Altitude ±1σ", fig))
            st.session_state["nebula_figs"].append(("ATM - UKF Alt", fig_alt))
            st.session_state["nebula_figs"].append(("ATM - UKF Vd", fig_vd))
            st.session_state["nebula_figs"].append(("ATM - NEES", figN))

        else:
            st.info("Configura parámetros y pulsa **Run ATM demo**.")

# =========================================================
# EXPORTAR A EXCEL
# =========================================================
st.divider()
st.subheader("⬇️ Exportar resultados a Excel")

last = st.session_state.get("nebula_last")
if not last:
    st.caption("Aún no hay resultados para exportar. Ejecuta primero una demo (LEO o ATM).")
else:
    mode = last.get("mode")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if mode == "leo":
            sim = last.get("sim", {})
            ukf = last.get("ukf", {})
            # hoja de simulación LEO
            try:
                t = sim.get("time", [])
                states = sim.get("states", {})
                df_leo = pd.DataFrame(
                    {
                        "t_s": t,
                        "alt_km": states.get("alt_km", []),
                        "speed_kms": states.get("speed_kms", []),
                        "x_m": states.get("x_m", []),
                        "y_m": states.get("y_m", []),
                        "z_m": states.get("z_m", []),
                    }
                )
                df_leo.to_excel(writer, index=False, sheet_name="leo_sim")
            except Exception:
                pass
            # hoja de UKF LEO
            try:
                df_ukf = pd.DataFrame(
                    {
                        "x_alt_km": ukf.get("x_alt_km", []),
                        "x_speed_kms": ukf.get("x_speed_kms", []),
                        "nees": ukf.get("nees", []),
                    }
                )
                df_ukf.to_excel(writer, index=False, sheet_name="leo_ukf")
            except Exception:
                pass
        elif mode == "atm":
            sim = last.get("sim", {})
            ukf_atm = last.get("ukf", {})
            # hoja de simulación ATM
            try:
                t = sim.get("time", [])
                states = sim.get("states", {})
                unc = sim.get("uncertainty", {})
                df_atm = pd.DataFrame(
                    {
                        "t_s": t,
                        "alt_m": states.get("alt", []),
                        "vd_mps": states.get("vd", []),
                        "alt_sigma": unc.get("alt_sigma", []),
                    }
                )
                df_atm.to_excel(writer, index=False, sheet_name="atm_sim")
            except Exception:
                pass
            # hoja de UKF ATM
            try:
                df_atm_ukf = pd.DataFrame(
                    {
                        "x_alt_m": ukf_atm.get("x_alt_m", []),
                        "x_vd_mps": ukf_atm.get("x_vd_mps", []),
                        "nees": ukf_atm.get("nees", []),
                    }
                )
                df_atm_ukf.to_excel(writer, index=False, sheet_name="atm_ukf")
            except Exception:
                pass

    buf.seek(0)
    st.download_button(
        label="Descargar Excel",
        data=buf,
        file_name="nebula_hdt_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# =========================================================
# EXPORTAR / IMPRIMIR PDF (con ImageReader)
# =========================================================
st.divider()
st.subheader("🖨️ Exportar / Imprimir gráficos a PDF")

figs = st.session_state.get("nebula_figs", [])
# diagnóstico visible
deps = []
deps.append("reportlab: OK" if REPORTLAB_OK else "reportlab: FALTA")
deps.append("kaleido: OK" if HAVE_KALEIDO else "kaleido: FALTA")
st.caption(f"Diagnóstico · {' · '.join(deps)} · Figuras: {len(figs)}")

col_pdf1, col_pdf2 = st.columns([0.55, 0.45])
with col_pdf1:
    pdf_btn = st.button("Generar PDF de gráficos", use_container_width=True)
with col_pdf2:
    if not REPORTLAB_OK:
        st.warning("Falta 'reportlab'. Instala:  pip install reportlab")
    if not HAVE_KALEIDO:
        st.warning("Falta 'kaleido'. Instala:  pip install -U kaleido")

if pdf_btn:
    if not figs:
        st.error("No hay gráficos para imprimir aún. Ejecuta una demo primero.")
    elif not REPORTLAB_OK or not HAVE_KALEIDO:
        st.error("No se pudo generar el PDF: faltan dependencias (reportlab/kaleido). Instálalas y recarga la página.")
    else:
        st.info("Generando PDF…")
        import traceback

        buf_pdf = io.BytesIO()
        try:
            c = canvas.Canvas(buf_pdf, pagesize=A4)
            width, height = A4
            y = height - 40
            first_error = None

            for title, fig in figs:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(40, y, title)
                y -= 20

                try:
                    # plotly → png (con kaleido)
                    img_bytes = fig.to_image(format="png")
                    img_buf = io.BytesIO(img_bytes)
                    img_rd = ImageReader(img_buf)  # 👈 aquí la corrección
                    c.drawImage(
                        img_rd,
                        40,
                        y - 260,
                        width=520,
                        height=240,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                    y -= 280
                except Exception as e:
                    if first_error is None:
                        first_error = traceback.format_exc()
                    c.setFont("Helvetica", 9)
                    c.drawString(40, y, f"(No se pudo renderizar esta figura: {e})")
                    y -= 40

                if y < 80:
                    c.showPage()
                    y = height - 40

            c.save()
            buf_pdf.seek(0)

            st.download_button(
                label="⬇️ Descargar PDF",
                data=buf_pdf,
                file_name="nebula_hdt_plots.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

            if first_error:
                st.warning("El PDF se generó, pero una o más figuras no pudieron renderizarse. Detalle del primer error:")
                st.code(first_error, language="text")
            else:
                st.success("PDF generado ✅. Descárgalo con el botón de arriba.")
        except Exception as e:
            st.error(f"Fallo generando el PDF: {e}")
