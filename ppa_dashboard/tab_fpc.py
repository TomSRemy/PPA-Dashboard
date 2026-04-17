"""
tab_fpc.py — KAL-EL : FPC Monte Carlo Tab v2
=============================================
Generic forward-looking simulation. Works for Solar and Wind.
Technology-agnostic: renewable_col driven by cfg["prod_col"].

Sections:
  S1  Contract & model parameters
  S2  Model calibration diagnostics (OLS)
  S3  Capacity scenario chart
  S4  Shape Discount fan charts
  S5  Capture Price fan charts
  S6  Annual P&L fan charts
  S7  Cumulative P&L distribution
  S8  Decision tables
  S9  Methodology note
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Optional

from config import C1, C2, C3, C4, C5, C2L, C3L, C5L, WHT, DEFAULT_FWD
from ui     import section, desc

try:
    from fpc_model import (
        fit_price_model,
        build_national_profile,
        build_asset_profile,
        build_capacity_trajectory,
        run_fpc_montecarlo,
        CAPACITY_SCENARIOS,
        PPE3_TARGETS,
        SOLAR_THRESHOLD_MW,
        WIND_THRESHOLD_MW,
    )
    _FPC_OK = True
except ImportError as _fpc_import_err:
    _FPC_OK = False
    _fpc_import_err_msg = str(_fpc_import_err)


# ─────────────────────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _kpi(label, value, color=C1, text=WHT):
    return (
        f'<div style="background:{color};border-left:5px solid {color};'
        f'padding:12px 16px;border-radius:6px;text-align:center;">'
        f'<div style="font-size:20px;font-weight:700;color:{text};'
        f'font-family:Calibri,Arial,sans-serif;">{value}</div>'
        f'<div style="font-size:11px;color:{text};opacity:0.85;'
        f'text-transform:uppercase;font-family:Calibri,Arial,sans-serif;">{label}</div>'
        f'</div>'
    )


def _pnl_color(v):
    if v > 50:  return C2,  WHT
    if v > 0:   return C2L, C1
    if v > -50: return C5L, C1
    return C5, WHT


def _fmt_k(v):
    return f"{v:+.0f}k"


def _fan_chart(years, bands, y_title, title, color,
               ppa_line=None, y_suffix="", plotly_base=None):
    """Fan chart: P10-P90 + P25-P75 + P50. Optional PPA horizontal line."""
    alpha_o = "rgba(42,157,143,0.10)" if color == C2 else "rgba(231,111,81,0.10)"
    alpha_i = "rgba(42,157,143,0.22)" if color == C2 else "rgba(231,111,81,0.22)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=bands[90] + bands[10][::-1],
        fill="toself", fillcolor=alpha_o,
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90", hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=bands[75] + bands[25][::-1],
        fill="toself", fillcolor=alpha_i,
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75", hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=years, y=bands[50],
        mode="lines+markers", name="P50 (median)",
        line=dict(color=color, width=2.5),
        marker=dict(size=7, color=color, line=dict(width=1.5, color=WHT)),
        hovertemplate=f"Year %{{x}}: P50 = %{{y:.1f}}{y_suffix}<extra></extra>"))

    if y_suffix != "%":
        fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)

    if ppa_line is not None:
        fig.add_hline(y=ppa_line, line_width=2, line_dash="dot", line_color=C4,
                      annotation_text=f"  PPA: {ppa_line:.2f} EUR/MWh",
                      annotation_position="right",
                      annotation_font=dict(size=11, color=C4, family="Calibri,Arial"))

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>",
                   font=dict(size=13, color=C1, family="Calibri,Arial"),
                   x=0.5, xanchor="center"),
        height=300, margin=dict(l=50, r=20, t=50, b=80),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title="Contract Year", tickmode="array", tickvals=years,
                   gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=11)),
        yaxis=dict(title=y_title, gridcolor="#eee",
                   tickfont=dict(family="Calibri,Arial", size=11),
                   zeroline=False,
                   ticksuffix=y_suffix if y_suffix == "%" else ""),
        legend=dict(orientation="h", yanchor="top", y=-0.22,
                    xanchor="center", x=0.5, font=dict(family="Calibri,Arial", size=11)),
        hovermode="x unified")
    if plotly_base:
        plotly_base(fig, h=300)
    return fig


def _hist_chart(cumul_arr, tenor, title, plotly_base=None):
    """Cumulative P&L histogram with P10/P50/P90."""
    p10 = float(np.nanpercentile(cumul_arr, 10))
    p50 = float(np.nanpercentile(cumul_arr, 50))
    p90 = float(np.nanpercentile(cumul_arr, 90))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=cumul_arr, nbinsx=80,
        marker_color="rgba(42,157,143,0.50)",
        marker_line_color=C2, marker_line_width=0.3,
        hovertemplate="P&L: %{x:.0f}k EUR<br>Frequency: %{y}<extra></extra>"))

    x_min = float(np.nanmin(cumul_arr))
    if x_min < 0:
        fig.add_vrect(x0=x_min, x1=0,
                      fillcolor="rgba(231,111,81,0.10)", line_width=0,
                      annotation_text="Loss zone", annotation_position="top left",
                      annotation_font=dict(size=10, color=C5, family="Calibri,Arial"))

    for pv, pl, pc in [(p10,"P10",C5),(p50,"P50",C1),(p90,"P90",C2)]:
        fig.add_vline(x=pv, line_width=2, line_color=pc, line_dash="dot",
                      annotation_text=f"  {pl}: {pv:+.0f}k",
                      annotation_position="top right",
                      annotation_font=dict(size=11, color=pc, family="Calibri,Arial"))
    fig.add_vline(x=0, line_width=1.5, line_color=C5)

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>",
                   font=dict(size=13, color=C1, family="Calibri,Arial"),
                   x=0.5, xanchor="center"),
        height=280, margin=dict(l=50, r=20, t=50, b=50),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title=f"Cumulative P&L over {tenor}yr (k EUR)",
                   gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=11)),
        yaxis=dict(title="Frequency", gridcolor="#eee",
                   tickfont=dict(family="Calibri,Arial", size=11)),
        showlegend=False, bargap=0.02)
    if plotly_base:
        plotly_base(fig, h=280, show_legend=False)
    return fig


def _kpi_strip(data: dict, label: str, ppa: float):
    """Display 5 KPI cards for a National or Asset result block."""
    p10c = data["percentiles_cumul"][10]
    p50c = data["percentiles_cumul"][50]
    p90c = data["percentiles_cumul"][90]
    ploss = data["prob_loss"] * 100
    es    = data["expected_shortfall"]

    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:{C1};margin-bottom:6px;">'
        f'{label}</div>', unsafe_allow_html=True)
    ka, kb, kc, kd, ke = st.columns(5)
    with ka:
        _bg, _tx = _pnl_color(p10c)
        st.markdown(_kpi("P10 Cumul P&L", _fmt_k(p10c), _bg, _tx), unsafe_allow_html=True)
    with kb:
        _bg, _tx = _pnl_color(p50c)
        st.markdown(_kpi("P50 Cumul P&L", _fmt_k(p50c), _bg, _tx), unsafe_allow_html=True)
    with kc:
        _bg, _tx = _pnl_color(p90c)
        st.markdown(_kpi("P90 Cumul P&L", _fmt_k(p90c), _bg, _tx), unsafe_allow_html=True)
    with kd:
        _c = C5 if ploss > 20 else C3 if ploss > 10 else C2
        _t = WHT if ploss > 20 or ploss <= 10 else C1
        st.markdown(_kpi("Prob. of Loss", f"{ploss:.1f}%", _c, _t), unsafe_allow_html=True)
    with ke:
        _bg, _tx = _pnl_color(es)
        st.markdown(_kpi("Expected Shortfall", _fmt_k(es), _bg, _tx), unsafe_allow_html=True)


def _decision_table(rows, label):
    """Style and display decision table."""
    df = pd.DataFrame(rows)

    def _style(row):
        try:
            val = float(row["P&L P50 (kEUR)"].replace("k","").replace("+",""))
        except Exception:
            val = 0
        _bg, _tx = _pnl_color(val)
        base = [""] * len(row)
        idx  = df.columns.get_loc("P&L P50 (kEUR)")
        base[idx] = f"background-color:{_bg};color:{_tx};font-weight:700"
        return base

    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:{C1};margin-bottom:4px;">'
        f'{label}</div>', unsafe_allow_html=True)
    st.dataframe(df.style.apply(_style, axis=1),
                 use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render_fpc_tab(
    hourly,
    nat_ref_complete,
    asset_ann,
    asset_raw: Optional[pd.DataFrame],
    has_asset: bool,
    asset_name: str,
    cfg: dict,
    sl_u: float,
    ic_u: float,
    hist_sd_f,
    plotly_base,
):
    if not _FPC_OK:
        st.error(
            f"fpc_model.py could not be imported. "
            f"Add it to ppa_dashboard/ and redeploy. "
            f"Error: {_fpc_import_err_msg if '_fpc_import_err_msg' in dir() else 'ImportError'}"
        )
        return

    # Technology from sidebar cfg
    techno       = cfg["label"]          # "Solar" or "Wind"
    renewable_col = cfg["prod_col"]      # "NatMW" or "WindMW"
    threshold_mw  = WIND_THRESHOLD_MW if techno == "Wind" else SOLAR_THRESHOLD_MW

    st.markdown(
        f'## FPC Monte Carlo — Forward-Looking {techno} Simulation'
        f'<span style="font-size:13px;color:#888;font-weight:400"> — Generic Engine v2</span>',
        unsafe_allow_html=True)
    desc(
        f"Technology: {techno} | Renewable series: {renewable_col} | "
        f"OLS fitted on hours where {renewable_col} > {threshold_mw} MW. "
        "Shape discount derived endogenously from simulated prices — not an input."
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # S1 — INPUTS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Contract & Model Parameters")

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:{C1};">Contract</div>',
                    unsafe_allow_html=True)
        ppa_input    = st.number_input("PPA Price (EUR/MWh)", 10.0, 200.0, 38.0,
                                       step=0.5, key="fpc_ppa")
        fwd_input    = st.number_input("Baseload Forward — flat across tenor (EUR/MWh)",
                                       10.0, 200.0,
                                       float(DEFAULT_FWD.get(2026, 55.0)),
                                       step=0.5, key="fpc_fwd",
                                       help="V1: single forward applied to all tenor years.")
        tenor_yr     = st.slider("Tenor (years)", 1, 15, 5, key="fpc_tenor")
        _prod_def    = max(1.0, min(
            float(asset_ann["prod_gwh"].mean()) if has_asset else 52.0, 50000.0))
        prod_gwh     = st.number_input("P50 Production (GWh/yr)", 1.0, 50000.0,
                                       _prod_def, step=0.5, key="fpc_prod")
        imb_forfait  = st.number_input("Imbalance forfait (EUR/MWh)", 0.0, 10.0, 1.9,
                                       step=0.1, key="fpc_imb")
        imb_rate     = st.number_input("Imbalance rate (% of production)",
                                       0.5, 15.0, 3.0, step=0.5, key="fpc_imb_rate") / 100

    with c_right:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:{C1};">Model</div>',
                    unsafe_allow_html=True)

        # Asset availability check (upfront, before run)
        _asset_profile_arr, _asset_profile_err = build_asset_profile(
            asset_raw if has_asset else None)
        _asset_ok = _asset_profile_arr is not None

        _basis_opts = ["National"]
        if _asset_ok:
            _basis_opts += ["Asset", "Both"]

        basis = st.radio("Analysis basis", _basis_opts, horizontal=True, key="fpc_basis",
                         help=(
                             "National = market benchmark. "
                             "Asset = deal P&L using uploaded load curve. "
                             "Both = identical simulated prices, two capture prices."))

        if not _asset_ok:
            if has_asset:
                st.warning(f"Asset profile: {_asset_profile_err}")
            else:
                st.info("Upload an asset load curve in the sidebar to enable Asset / Both.")

        exclude_2022 = st.toggle("Exclude 2022 from calibration", value=True, key="fpc_ex22")

        ppe3_label = f"PPE3 {techno} targets: " + \
                     " | ".join(f"{yr}: {gw:.0f} GW"
                                for yr, gw in PPE3_TARGETS.get(techno, {}).items())
        scenario_choice = st.selectbox(
            "Capacity scenario", list(CAPACITY_SCENARIOS.keys()), index=0,
            key="fpc_scenario", help=ppe3_label)

        custom_gw, custom_yr = None, None
        if scenario_choice == "Custom":
            custom_gw = st.slider("Custom target (GW)", 10.0, 120.0, 48.0,
                                  step=1.0, key="fpc_custom_gw")
            custom_yr = st.slider("Target year", 2026, 2040, 2030, key="fpc_custom_yr")

        n_sim = st.select_slider(
            "Simulations", options=[500, 1_000, 2_000, 5_000],
            value=1_000, key="fpc_nsim",
            help="500-1000 for exploration. 5000 for final analysis.")

        run_btn = st.button(f"▶ Run FPC Monte Carlo — {techno}", key="fpc_run")

    # Derived parameters
    prod_mwh    = prod_gwh * 1000
    _last_hist  = int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025
    tenor_years = list(range(_last_hist + 1, _last_hist + 1 + tenor_yr))
    fwd_by_year = {yr: fwd_input for yr in tenor_years}

    # Current capacity from nat_reference
    _cap_col = "cap_solar_gw" if techno == "Solar" else "cap_wind_gw"
    _current_cap_gw = 24.0 if techno == "Solar" else 22.0
    if _cap_col in nat_ref_complete.columns:
        _cap_vals = nat_ref_complete[_cap_col].dropna()
        if len(_cap_vals) > 0:
            _current_cap_gw = float(_cap_vals.iloc[-1])

    # ── RUN ──────────────────────────────────────────────────────────────────
    if run_btn:
        errors = []

        # 1. Fit OLS
        with st.spinner(f"Fitting {techno} price model on ENTSO-E data..."):
            _model, _model_err = fit_price_model(
                hourly, renewable_col=renewable_col,
                techno=techno, exclude_2022=exclude_2022)

        if _model_err:
            st.error(f"Model calibration failed:\n{_model_err}")
            st.stop()

        # Show warning immediately if model is suspect
        if _model.get("warning"):
            for w in _model["warning"].split("\n"):
                if w.strip():
                    st.warning(w)

        # 2. Build national profile
        _nat_profile, _nat_err = build_national_profile(
            hourly, renewable_col=renewable_col,
            techno=techno, exclude_2022=exclude_2022)
        if _nat_err:
            st.error(f"National profile error: {_nat_err}")
            st.stop()

        # 3. Capacity trajectory
        _cap_traj, _cap_err = build_capacity_trajectory(
            current_cap_gw=_current_cap_gw,
            current_year=_last_hist,
            tenor_years=tenor_years,
            techno=techno,
            scenario=scenario_choice,
            custom_target_gw=custom_gw or 48.0,
            custom_target_year=custom_yr or 2030,
        )
        if _cap_err:
            st.warning(f"Capacity trajectory warning: {_cap_err}")

        # 4. Asset profile for this run
        _asset_run = _asset_profile_arr if basis in ("Asset", "Both") else None

        # 5. Run simulation
        with st.spinner(f"Simulating {n_sim:,} trajectories × {tenor_yr} years..."):
            _results, _sim_err = run_fpc_montecarlo(
                model=_model,
                tech_profile_288=_nat_profile,
                asset_profile_288=_asset_run,
                capacity_by_year=_cap_traj,
                current_cap_gw=_current_cap_gw,
                tenor_years=tenor_years,
                forward_by_year=fwd_by_year,
                ppa=ppa_input,
                prod_p50_mwh=prod_mwh,
                imb_rate=imb_rate,
                imb_forfait=imb_forfait,
                basis=basis,
                n_sim=n_sim,
            )

        if _sim_err:
            st.error(f"Simulation failed:\n{_sim_err}")
            st.stop()

        st.session_state["fpc_results"] = _results
        st.session_state["fpc_model"]   = _model
        st.session_state["fpc_cap"]     = _cap_traj
        st.session_state["fpc_params"]  = {
            "ppa": ppa_input, "forward": fwd_input, "tenor": tenor_yr,
            "basis": basis, "scenario": scenario_choice,
            "techno": techno, "renewable_col": renewable_col,
            "current_cap_gw": _current_cap_gw,
        }
        st.success(f"Simulation complete — {n_sim:,} trajectories × {tenor_yr} years.")

    # Retrieve stored state
    _results  = st.session_state.get("fpc_results", None)
    _model    = st.session_state.get("fpc_model",   None)
    _cap_traj = st.session_state.get("fpc_cap",     None)
    _params   = st.session_state.get("fpc_params",  {})

    # ═══════════════════════════════════════════════════════════════════════════
    # S2 — MODEL CALIBRATION DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════════
    if _model is not None:
        st.markdown("---")
        with st.expander(f"Model Calibration — {techno} OLS Diagnostics", expanded=True):

            d1, d2, d3, d4, d5 = st.columns(5)
            beta = _model["beta_renewable"]
            beta_color = C2 if beta < -0.0001 else C5

            with d1:
                st.markdown(_kpi("R²", f"{_model['r2']:.3f}",
                                 C2 if _model['r2'] > MIN_R2_WARNING else C5, WHT),
                            unsafe_allow_html=True)
            with d2:
                st.markdown(_kpi("β renewable", f"{beta:.5f}",
                                 beta_color, WHT), unsafe_allow_html=True)
            with d3:
                st.markdown(_kpi("RMSE", f"{_model['rmse']:.1f} EUR/MWh", C1, WHT),
                            unsafe_allow_html=True)
            with d4:
                st.markdown(_kpi("Obs (filtered)", f"{_model['n_obs']:,}", C1, WHT),
                            unsafe_allow_html=True)
            with d5:
                st.markdown(_kpi("Hours kept", f"{_model['pct_hours_kept']:.0f}%", C1, WHT),
                            unsafe_allow_html=True)

            if beta >= -0.0001:
                st.error(
                    f"β renewable = {beta:.5f} — not meaningfully negative. "
                    f"Expected: negative (more {techno.lower()} → lower prices). "
                    f"Simulation outputs are NOT reliable. "
                    f"Check that '{renewable_col}' is populated in hourly_spot.csv "
                    f"and that the correct technology is selected."
                )
            elif _model['r2'] < 0.10:
                st.warning(
                    f"R² = {_model['r2']:.3f} is very low. "
                    "The model explains little price variation. "
                    "Shape discount estimates will have wide uncertainty bands."
                )
            else:
                beta_effect = beta * _model.get("n_obs", 1)
                st.info(
                    f"β = {beta:.5f} EUR/MWh per MW. "
                    f"At P95 production: "
                    f"approx {beta * float(hourly[renewable_col].quantile(0.95) if renewable_col in hourly.columns else 5000):.1f} EUR/MWh effect on prices. "
                    f"Filtered to hours where {renewable_col} > {_model['threshold_mw']:.0f} MW "
                    f"({_model['pct_hours_kept']:.0f}% of all hours)."
                )

            # Fitted vs actual chart
            mc = _model["monthly_check"]
            _x_labels = mc["Year"].astype(str) + "-" + mc["Month"].astype(str).str.zfill(2)
            fig_fit = go.Figure()
            fig_fit.add_trace(go.Scatter(x=_x_labels, y=mc["actual"].tolist(),
                mode="lines", name="Actual", line=dict(color=C1, width=2)))
            fig_fit.add_trace(go.Scatter(x=_x_labels, y=mc["fitted"].tolist(),
                mode="lines", name="Fitted", line=dict(color=C2, width=2, dash="dot")))
            fig_fit.update_layout(
                title=dict(text=f"<b>Fitted vs Actual — Monthly Average Spot — {techno} production hours</b>",
                           font=dict(size=12, color=C1, family="Calibri,Arial"),
                           x=0.5, xanchor="center"),
                height=240, margin=dict(l=50, r=20, t=40, b=60),
                plot_bgcolor=WHT, paper_bgcolor=WHT,
                yaxis=dict(title="EUR/MWh", gridcolor="#eee",
                           tickfont=dict(family="Calibri,Arial", size=11)),
                xaxis=dict(tickangle=-45, tickfont=dict(family="Calibri,Arial", size=9)),
                legend=dict(orientation="h", yanchor="top", y=-0.3,
                            xanchor="center", x=0.5, font=dict(size=11)))
            plotly_base(fig_fit, h=240)
            st.plotly_chart(fig_fit, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S3 — CAPACITY SCENARIO
    # ═══════════════════════════════════════════════════════════════════════════
    if _cap_traj is not None and _results is not None:
        st.markdown("---")
        section(f"{techno} Capacity Trajectory — Simulation Scenario")

        hist_cap = nat_ref_complete[[
            "year", "cap_solar_gw" if techno == "Solar" else "cap_wind_gw"
        ]].rename(columns={
            "cap_solar_gw": "cap_gw", "cap_wind_gw": "cap_gw"
        }).dropna()

        fig_cap = go.Figure()
        if len(hist_cap) > 0:
            fig_cap.add_trace(go.Scatter(
                x=hist_cap["year"].tolist(), y=hist_cap["cap_gw"].tolist(),
                mode="markers+lines", name="Historical (ENTSO-E)",
                line=dict(color=C1, width=2),
                marker=dict(size=8, color=C1, line=dict(width=1.5, color=WHT)),
                hovertemplate="Year %{x}: %{y:.1f} GW<extra></extra>"))

        _cyrs = list(_cap_traj.keys())
        _cvals = [_cap_traj[y] for y in _cyrs]
        fig_cap.add_trace(go.Scatter(
            x=_cyrs, y=_cvals,
            mode="markers+lines",
            name=f"Scenario: {_params.get('scenario','?')}",
            line=dict(color=C2, width=2.5, dash="dot"),
            marker=dict(size=8, color=C2, line=dict(width=1.5, color=WHT)),
            hovertemplate="Year %{x}: %{y:.1f} GW<extra></extra>"))

        for yr, gw in PPE3_TARGETS.get(techno, {}).items():
            fig_cap.add_hline(y=gw, line_dash="dash", line_color=C3, line_width=1.5,
                              annotation_text=f"PPE3 {yr}: {gw:.0f} GW",
                              annotation_position="right",
                              annotation_font=dict(size=10, color=C3, family="Calibri,Arial"))

        fig_cap.update_layout(
            title=dict(
                text=f"<b>FR {techno} Installed Capacity — Historical + Simulation Scenario</b>",
                font=dict(size=13, color=C1, family="Calibri,Arial"),
                x=0.5, xanchor="center"),
            height=280, margin=dict(l=50, r=120, t=50, b=60),
            plot_bgcolor=WHT, paper_bgcolor=WHT,
            xaxis=dict(title="Year", gridcolor="#eee",
                       tickfont=dict(family="Calibri,Arial", size=11)),
            yaxis=dict(title="Installed Capacity (GW)", gridcolor="#eee",
                       tickfont=dict(family="Calibri,Arial", size=11)),
            legend=dict(orientation="h", yanchor="top", y=-0.18,
                        xanchor="center", x=0.5, font=dict(size=11)))
        plotly_base(fig_cap, h=280)
        st.plotly_chart(fig_cap, use_container_width=True)

        # Multiplier summary
        _cap_cur = _params.get("current_cap_gw", _current_cap_gw)
        _mrows = [{"Year": yr,
                   "Capacity (GW)": f"{_cap_traj[yr]:.1f}",
                   f"Multiplier vs {_last_hist}": f"×{_cap_traj[yr]/_cap_cur:.2f}",
                   "Forward (EUR/MWh)": f"{fwd_input:.1f}"}
                  for yr in _cyrs]
        st.dataframe(pd.DataFrame(_mrows), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # No results yet
    # ═══════════════════════════════════════════════════════════════════════════
    if _results is None:
        st.markdown("---")
        st.info(
            f"Configure parameters above and click "
            f"**▶ Run FPC Monte Carlo — {techno}** to run the simulation.")
        _methodology_note(techno, renewable_col, threshold_mw)
        return

    years      = _results["years"]
    basis_used = _results["basis"]
    do_nat     = "nat"   in _results
    do_asset   = "asset" in _results
    do_both    = do_nat and do_asset

    # ── Validate results (catch post-simulation issues) ───────────────────────
    if do_nat:
        _sd_p50_yr1 = _results["nat"]["sd_bands"][50][0] * 100
        if abs(_sd_p50_yr1) < 0.1:
            st.error(
                f"Shape discount P50 for year 1 = {_sd_p50_yr1:.2f}% — effectively zero. "
                "This indicates the model's beta_renewable is not creating price differences "
                "between production and off-production hours. "
                "Check the model diagnostics above: β_renewable must be meaningfully negative."
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # S4 — SHAPE DISCOUNT FAN CHARTS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section(f"Shape Discount — Forward Probability Fan Chart ({techno})")
    desc(
        "Shape discount = 1 − (capture price / baseload). "
        "Derived endogenously from simulated prices. "
        "Baseload = mean of ALL simulated hours. "
        "Capture price = production-weighted average price."
    )

    if do_both:
        _s4a, _s4b = st.columns(2)
        with _s4a:
            fig = _fan_chart(years, _results["nat"]["sd_bands"],
                             "Shape Discount (%)",
                             f"Shape Discount — National {techno}",
                             C5, y_suffix="%", plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
        with _s4b:
            fig = _fan_chart(years, _results["asset"]["sd_bands"],
                             "Shape Discount (%)",
                             f"Shape Discount — {asset_name}",
                             C4, y_suffix="%", plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
    elif do_nat:
        fig = _fan_chart(years, _results["nat"]["sd_bands"],
                         "Shape Discount (%)",
                         f"Shape Discount — National {techno}",
                         C5, y_suffix="%", plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)
    elif do_asset:
        fig = _fan_chart(years, _results["asset"]["sd_bands"],
                         "Shape Discount (%)",
                         f"Shape Discount — {asset_name}",
                         C4, y_suffix="%", plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S5 — CAPTURE PRICE FAN CHARTS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section(f"Capture Price — Forward Probability Fan Chart ({techno})")
    desc(
        "Capture price = production-weighted average of simulated hourly prices. "
        "Orange dotted line = PPA price. When P50 capture price < PPA → majority of scenarios unprofitable."
    )

    if do_both:
        _s5a, _s5b = st.columns(2)
        with _s5a:
            fig = _fan_chart(years, _results["nat"]["cp_bands"],
                             "Capture Price (EUR/MWh)",
                             f"Capture Price — National {techno}",
                             C2, ppa_line=ppa_input, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
        with _s5b:
            fig = _fan_chart(years, _results["asset"]["cp_bands"],
                             "Capture Price (EUR/MWh)",
                             f"Capture Price — {asset_name}",
                             C2, ppa_line=ppa_input, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
    elif do_nat:
        fig = _fan_chart(years, _results["nat"]["cp_bands"],
                         "Capture Price (EUR/MWh)",
                         f"Capture Price — National {techno}",
                         C2, ppa_line=ppa_input, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)
    elif do_asset:
        fig = _fan_chart(years, _results["asset"]["cp_bands"],
                         "Capture Price (EUR/MWh)",
                         f"Capture Price — {asset_name}",
                         C2, ppa_line=ppa_input, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S6 — ANNUAL P&L FAN CHARTS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section(f"Annual P&L — Forward Probability Fan Chart ({techno})")
    desc(
        "Annual P&L = (Capture Price − PPA) × Volume − Imbalance. "
        "Dashed line = break-even. When P50 crosses below zero → median scenario is loss-making."
    )

    if do_both:
        _s6a, _s6b = st.columns(2)
        with _s6a:
            fig = _fan_chart(years, _results["nat"]["pnl_bands"],
                             "Annual P&L (k EUR)",
                             f"Annual P&L — National {techno}",
                             C2, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
        with _s6b:
            fig = _fan_chart(years, _results["asset"]["pnl_bands"],
                             "Annual P&L (k EUR)",
                             f"Annual P&L — {asset_name}",
                             C2, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
    elif do_nat:
        fig = _fan_chart(years, _results["nat"]["pnl_bands"],
                         "Annual P&L (k EUR)",
                         f"Annual P&L — National {techno}",
                         C2, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)
    elif do_asset:
        fig = _fan_chart(years, _results["asset"]["pnl_bands"],
                         "Annual P&L (k EUR)",
                         f"Annual P&L — {asset_name}",
                         C2, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S7 — CUMULATIVE P&L DISTRIBUTION
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Cumulative P&L Distribution")

    if do_nat:
        _kpi_strip(_results["nat"], f"National {techno} — benchmark", ppa_input)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        fig = _hist_chart(_results["nat"]["cumul_pnl"], tenor_yr,
                          f"Cumulative P&L — National {techno} — {tenor_yr}yr",
                          plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    if do_asset:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _kpi_strip(_results["asset"], f"{asset_name} — deal P&L", ppa_input)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        fig = _hist_chart(_results["asset"]["cumul_pnl"], tenor_yr,
                          f"Cumulative P&L — {asset_name} — {tenor_yr}yr",
                          plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S8 — DECISION TABLES
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Decision Table — Annual P&L, Shape Discount & Risk")
    desc(
        "All values from Monte Carlo simulation. "
        "SD P50 = median simulated shape discount. "
        "Downside = P10 − P50. Upside = P90 − P50."
    )

    if do_both:
        _t1, _t2 = st.columns(2)
        with _t1:
            _decision_table(
                _results["nat"]["scenario_table"],
                f"National {techno} — market benchmark")
        with _t2:
            _decision_table(
                _results["asset"]["scenario_table"],
                f"{asset_name} — deal P&L")
    elif do_nat:
        _decision_table(_results["nat"]["scenario_table"],
                        f"National {techno}")
    elif do_asset:
        _decision_table(_results["asset"]["scenario_table"], asset_name)

    # Summary box
    _ref = _results.get("nat") or _results.get("asset")
    if _ref:
        _cs   = _ref["percentiles_cumul"]
        _label = f"National {techno}" if do_nat else asset_name
        st.markdown(
            f'<div style="background:{C1};color:{WHT};padding:12px 20px;'
            f'margin-top:8px;border-radius:6px;font-family:Calibri,Arial;font-size:13px;">'
            f'<b>{_label} — {tenor_yr}yr cumulative ({_results["n_sim"]:,} simulations):</b>'
            f' &nbsp; P50 = {_fmt_k(_cs[50])}'
            f' &nbsp;|&nbsp; P10 = {_fmt_k(_cs[10])}'
            f' &nbsp;|&nbsp; P90 = {_fmt_k(_cs[90])}'
            f' &nbsp;|&nbsp; Prob. loss = {_ref["prob_loss"]*100:.1f}%'
            f' &nbsp;|&nbsp; Downside = {_fmt_k(_ref["downside"])}'
            f' &nbsp;|&nbsp; Upside = {_fmt_k(_ref["upside"])}'
            f'</div>', unsafe_allow_html=True)

    # ── Methodology note ──────────────────────────────────────────────────────
    st.markdown("---")
    _methodology_note(techno, renewable_col, threshold_mw)


def _methodology_note(techno, renewable_col, threshold_mw):
    with st.expander("Methodology — Model Specification & Assumptions", expanded=False):
        st.markdown(f"""
**Generic engine — works for Solar and Wind**

Technology selected: **{techno}** | Renewable series: **{renewable_col}** | Threshold: **{threshold_mw:.0f} MW**

**Causal flow**
```
Capacity (GW) → multiplier → RenewableMW_simulated
→ Hourly price simulation (OLS + block bootstrap residuals)
→ Forward anchoring: annual avg = forward input (no-arbitrage)
→ Capture price (production-weighted)
→ Shape discount (endogenous output)
→ P&L
```

**OLS price model**
```
Spot_h = α + β_renewable × {renewable_col}_h + Σ γ_k × Hour_k + Σ δ_m × Month_m + ε_h
```
Fitted only on hours where **{renewable_col} > {threshold_mw:.0f} MW** to avoid dilution of β by zero-production hours.

**Key definitions**
- `capture_price` = Σ(Prod_h × Price_h) / Σ(Prod_h) — production-weighted
- `baseload` = mean(Price_h) over **ALL** 8,760 simulated hours
- `shape_discount` = 1 − capture_price / baseload

**For "Both":** identical simulated price paths. Two capture prices computed from different production profiles. Difference reflects asset-specific timing vs national benchmark.

**Assumptions & limitations**
- β_renewable assumed constant over tenor (may evolve with penetration)
- Flat forward across tenor years (V1 — extendable to term structure)
- No gas / CO2 / nuclear covariates
- Historical residuals resampled — future volatility may differ
- Production profile assumed stable over tenor
        """, unsafe_allow_html=False)


# Expose threshold constant for use in tab header
try:
    from fpc_model import MIN_R2_WARNING
except ImportError:
    MIN_R2_WARNING = 0.10
