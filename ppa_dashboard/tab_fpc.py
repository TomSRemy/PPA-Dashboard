"""
tab_fpc.py — KAL-EL : FPC Monte Carlo Tab
==========================================
Forward-looking FPC-style Monte Carlo.
Causal flow: Solar Capacity → SolarMW → Hourly Prices → Capture Price → Shape Discount → P&L

Sections:
  S1  Inputs (contract + model parameters)
  S2  Model calibration (OLS diagnostics)
  S3  Solar capacity scenario
  S4  Shape Discount fan charts (National / Asset / Both)
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
        fit_price_model, build_national_profile, build_asset_profile,
        build_capacity_trajectory, run_fpc_montecarlo,
        CAPACITY_SCENARIOS, PPE3_TRAJECTORY,
    )
    _FPC_OK = True
except ImportError:
    _FPC_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
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


def _fan_chart(years, bands, y_title, title, color, suffix="",
               ppa_line=None, plotly_base=None):
    """Generic fan chart with P10-P90 + P25-P75 + P50 + optional PPA reference."""
    alpha_outer = "rgba(42,157,143,0.10)" if color == C2 else "rgba(231,111,81,0.10)"
    alpha_inner = "rgba(42,157,143,0.22)" if color == C2 else "rgba(231,111,81,0.22)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=bands[90] + bands[10][::-1],
        fill="toself", fillcolor=alpha_outer,
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90",
        hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=bands[75] + bands[25][::-1],
        fill="toself", fillcolor=alpha_inner,
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75",
        hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=years, y=bands[50],
        mode="lines+markers", name="P50 (median)",
        line=dict(color=color, width=2.5),
        marker=dict(size=7, color=color, line=dict(width=1.5, color=WHT)),
        hovertemplate=f"Year %{{x}}: P50 = %{{y:.1f}}{suffix}<extra></extra>"))

    if suffix != "%" and suffix != " EUR":
        fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)

    if ppa_line is not None:
        fig.add_hline(
            y=ppa_line, line_width=2, line_dash="dot", line_color=C4,
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
                   ticksuffix=suffix if suffix in ("%",) else ""),
        legend=dict(orientation="h", yanchor="top", y=-0.22,
                    xanchor="center", x=0.5,
                    font=dict(family="Calibri,Arial", size=11)),
        hovermode="x unified")
    if plotly_base:
        plotly_base(fig, h=300)
    return fig


def _hist_chart(cumul_arr, tenor, title, plotly_base=None):
    """Cumulative P&L histogram with P10/P50/P90 markers."""
    p10 = float(np.nanpercentile(cumul_arr, 10))
    p50 = float(np.nanpercentile(cumul_arr, 50))
    p90 = float(np.nanpercentile(cumul_arr, 90))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=cumul_arr, nbinsx=80,
        marker_color="rgba(42,157,143,0.50)",
        marker_line_color=C2, marker_line_width=0.3,
        hovertemplate="P&L: %{x:.0f}k EUR<br>Freq: %{y}<extra></extra>"))

    x_min = float(np.nanmin(cumul_arr))
    if x_min < 0:
        fig.add_vrect(x0=x_min, x1=0,
                      fillcolor="rgba(231,111,81,0.10)", line_width=0,
                      annotation_text="Loss zone",
                      annotation_position="top left",
                      annotation_font=dict(size=10, color=C5, family="Calibri,Arial"))

    for pv, pl, pc in [(p10, "P10", C5), (p50, "P50", C1), (p90, "P90", C2)]:
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


def _decision_table_display(rows, df_ref, label, ppa):
    """Style and display decision table."""
    df = pd.DataFrame(rows)

    def _style(row):
        try:
            val = float(row["P&L P50 (kEUR)"].replace("k", "").replace("+", ""))
        except Exception:
            val = 0
        bg, tx = _pnl_color(val)
        base = [""] * len(row)
        idx  = df.columns.get_loc("P&L P50 (kEUR)")
        base[idx] = f"background-color:{bg};color:{tx};font-weight:700"
        return base

    st.markdown(
        f'<div style="font-size:12px;font-weight:700;color:{C1};'
        f'margin-bottom:6px;">{label}</div>',
        unsafe_allow_html=True)
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
        st.error("fpc_model.py not found in ppa_dashboard/. Add it to the repository.")
        return

    st.markdown(
        '## FPC Monte Carlo — Forward-Looking Simulation'
        f'<span style="font-size:13px;color:#888;font-weight:400"> '
        f'— Hourly Price Model</span>',
        unsafe_allow_html=True)
    desc(
        "Forward-looking simulation: solar capacity growth → hourly price simulation → "
        "capture price and shape discount derived endogenously. "
        "Shape discount is an OUTPUT of this model, not an input. "
        "Simulated annual prices anchored to forward input (no-arbitrage)."
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # S1 — INPUTS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Contract & Model Parameters")

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:{C1};">Contract Parameters</div>',
                    unsafe_allow_html=True)
        ppa_input    = st.number_input("PPA Price (EUR/MWh)", 10.0, 200.0, 38.0, step=0.5,
                                       key="fpc_ppa")
        fwd_input    = st.number_input("Baseload Forward — flat across tenor (EUR/MWh)",
                                       10.0, 200.0, float(DEFAULT_FWD.get(2026, 55.0)),
                                       step=0.5, key="fpc_fwd",
                                       help="V1: flat forward applied to all tenor years.")
        tenor_yr     = st.slider("Tenor (years)", 1, 15, 5, key="fpc_tenor")
        _prod_def    = max(1.0, min(float(asset_ann["prod_gwh"].mean()) if has_asset else 52.0, 50000.0))
        prod_p50_gwh = st.number_input("P50 Production (GWh/yr)", 1.0, 50000.0,
                                        _prod_def, step=0.5, key="fpc_prod")
        imb_forfait  = st.number_input("Imbalance forfait (EUR/MWh)", 0.0, 10.0, 1.9,
                                        step=0.1, key="fpc_imb_forfait")
        imb_rate     = st.number_input("Imbalance rate (% of production)", 0.5, 15.0, 3.0,
                                        step=0.5, key="fpc_imb_rate") / 100

    with c_right:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:{C1};">Model Parameters</div>',
                    unsafe_allow_html=True)

        # Asset availability check
        _asset_profile_arr, _asset_profile_err = build_asset_profile(asset_raw if has_asset else None)
        _asset_ok = _asset_profile_arr is not None

        _basis_opts = ["National"]
        if _asset_ok:
            _basis_opts += ["Asset", "Both"]

        basis = st.radio("Analysis basis", _basis_opts, horizontal=True, key="fpc_basis",
                         help="National = market proxy. Asset = deal P&L. "
                              "Both = same simulated price paths, two capture prices.")
        if not _asset_ok and has_asset:
            st.warning(f"Asset profile insufficient: {_asset_profile_err}")
        elif not has_asset:
            st.info("Upload an asset load curve in the sidebar to enable Asset / Both.")

        exclude_2022 = st.toggle("Exclude 2022 from calibration", value=True, key="fpc_ex22")

        scenario_choice = st.selectbox(
            "Solar capacity scenario",
            list(CAPACITY_SCENARIOS.keys()), index=0,
            key="fpc_scenario",
            help="PPE3 targets: 48 GW by 2030, 67.5 GW by 2035.")

        custom_target_gw   = None
        custom_target_year = None
        if scenario_choice == "Custom":
            custom_target_gw   = st.slider("Custom target (GW)", 20.0, 100.0, 48.0,
                                            step=1.0, key="fpc_custom_gw")
            custom_target_year = st.slider("Target year", 2026, 2040, 2030,
                                            key="fpc_custom_yr")

        n_sim = st.select_slider("Simulations", options=[500, 1_000, 2_000, 5_000],
                                  value=1_000, key="fpc_nsim",
                                  help="500-1000 recommended for speed. 5000 for final analysis.")

        run_btn = st.button("▶ Run FPC Monte Carlo", key="fpc_run")

    prod_p50_mwh = prod_p50_gwh * 1000
    tenor_years  = list(range(
        (int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025) + 1,
        (int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025) + 1 + tenor_yr
    ))
    forward_by_year = {yr: fwd_input for yr in tenor_years}

    # Current capacity
    _current_cap_gw = 24.0
    if "cap_solar_gw" in nat_ref_complete.columns:
        _cap_vals = nat_ref_complete["cap_solar_gw"].dropna()
        if len(_cap_vals) > 0:
            _current_cap_gw = float(_cap_vals.iloc[-1])

    # ── RUN ──────────────────────────────────────────────────────────────────
    if run_btn:
        # 1. Fit OLS model
        with st.spinner("Fitting price model on ENTSO-E data..."):
            _model, _model_err = fit_price_model(
                hourly, exclude_2022=exclude_2022, prod_col=cfg["prod_col"])

        if _model_err:
            st.error(f"Model calibration failed: {_model_err}")
            st.stop()

        if _model.get("warning"):
            st.warning(_model["warning"])

        # 2. Build profiles
        _nat_profile, _nat_err = build_national_profile(
            hourly, prod_col=cfg["prod_col"], exclude_2022=exclude_2022)
        if _nat_err:
            st.error(f"National profile error: {_nat_err}")
            st.stop()

        _asset_profile_run = _asset_profile_arr if basis in ("Asset", "Both") else None

        # 3. Capacity trajectory
        _cap_traj, _cap_err = build_capacity_trajectory(
            current_cap_gw=_current_cap_gw,
            current_year=int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025,
            tenor_years=tenor_years,
            scenario=scenario_choice,
            custom_target_gw=custom_target_gw or 48.0,
            custom_target_year=custom_target_year or 2030,
        )
        if _cap_err:
            st.warning(f"Capacity trajectory warning: {_cap_err}")

        # 4. Run simulation
        with st.spinner(f"Simulating {n_sim:,} trajectories × {tenor_yr} years..."):
            _results, _sim_err = run_fpc_montecarlo(
                hourly=hourly,
                model=_model,
                nat_profile_288=_nat_profile,
                asset_profile_288=_asset_profile_run,
                capacity_by_year=_cap_traj,
                current_cap_gw=_current_cap_gw,
                tenor_years=tenor_years,
                forward_by_year=forward_by_year,
                ppa=ppa_input,
                prod_p50_mwh=prod_p50_mwh,
                imb_rate=imb_rate,
                imb_forfait=imb_forfait,
                basis=basis,
                n_sim=n_sim,
            )

        if _sim_err:
            st.error(f"Simulation failed: {_sim_err}")
            st.stop()

        # Store in session state
        st.session_state["fpc_results"] = _results
        st.session_state["fpc_model"]   = _model
        st.session_state["fpc_cap"]     = _cap_traj
        st.session_state["fpc_params"]  = {
            "ppa": ppa_input, "forward": fwd_input, "tenor": tenor_yr,
            "basis": basis, "scenario": scenario_choice,
            "current_cap_gw": _current_cap_gw,
        }

    # ── Retrieve results ──────────────────────────────────────────────────────
    _results = st.session_state.get("fpc_results", None)
    _model   = st.session_state.get("fpc_model",   None)
    _cap_traj = st.session_state.get("fpc_cap",    None)
    _params  = st.session_state.get("fpc_params",  {})

    # ═══════════════════════════════════════════════════════════════════════════
    # S2 — MODEL CALIBRATION
    # ═══════════════════════════════════════════════════════════════════════════
    if _model is not None:
        st.markdown("---")
        with st.expander("Model Calibration — OLS Diagnostics", expanded=False):
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.markdown(_kpi("R²", f"{_model['r2']:.2f}",
                                 C2 if _model['r2'] > 0.4 else C5, WHT),
                            unsafe_allow_html=True)
            with d2:
                st.markdown(_kpi("RMSE", f"{_model['rmse']:.1f} EUR/MWh", C1, WHT),
                            unsafe_allow_html=True)
            with d3:
                beta_display = f"{_model['beta_solar']:.3f} EUR/MWh per GW"
                c_beta = C2 if _model['beta_solar'] < 0 else C5
                st.markdown(_kpi("β solar", beta_display, c_beta, WHT),
                            unsafe_allow_html=True)
            with d4:
                st.markdown(_kpi("N obs", f"{_model['n_obs']:,}", C1, WHT),
                            unsafe_allow_html=True)

            if _model['beta_solar'] >= 0:
                st.warning(
                    f"β solar = {_model['beta_solar']:.3f} is non-negative. "
                    "Expected: negative (more solar → lower prices). "
                    "This may indicate insufficient solar hours in the data or data quality issues.")

            # Fitted vs actual chart
            mc = _model["monthly_check"]
            fig_fit = go.Figure()
            fig_fit.add_trace(go.Scatter(
                x=mc["Year"].astype(str) + "-" + mc["Month"].astype(str).str.zfill(2),
                y=mc["actual"], mode="lines", name="Actual",
                line=dict(color=C1, width=2)))
            fig_fit.add_trace(go.Scatter(
                x=mc["Year"].astype(str) + "-" + mc["Month"].astype(str).str.zfill(2),
                y=mc["fitted"], mode="lines", name="Fitted",
                line=dict(color=C2, width=2, dash="dot")))
            fig_fit.update_layout(
                title=dict(text="<b>Fitted vs Actual — Monthly Average Spot Price</b>",
                           font=dict(size=12, color=C1, family="Calibri,Arial"),
                           x=0.5, xanchor="center"),
                height=250, margin=dict(l=50, r=20, t=40, b=60),
                plot_bgcolor=WHT, paper_bgcolor=WHT,
                yaxis=dict(title="EUR/MWh", gridcolor="#eee",
                           tickfont=dict(family="Calibri,Arial", size=11)),
                xaxis=dict(tickangle=-45, tickfont=dict(family="Calibri,Arial", size=9)),
                legend=dict(orientation="h", yanchor="top", y=-0.25,
                            xanchor="center", x=0.5, font=dict(size=11)))
            plotly_base(fig_fit, h=250)
            st.plotly_chart(fig_fit, use_container_width=True)

            desc(
                f"OLS model: Spot = α + β×SolarMW + hour dummies + month dummies + ε. "
                f"β = {_model['beta_solar']:.3f} EUR/MWh per GW of solar output. "
                f"RMSE = {_model['rmse']:.1f} EUR/MWh. "
                f"Residuals are block-bootstrapped (168h blocks) for simulation."
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # S3 — CAPACITY SCENARIO
    # ═══════════════════════════════════════════════════════════════════════════
    if _cap_traj is not None and _results is not None:
        st.markdown("---")
        section("Solar Capacity Trajectory — Simulation Scenario")

        # Historical from nat_ref
        hist_cap = nat_ref_complete[["year","cap_solar_gw"]].dropna()

        fig_cap = go.Figure()

        # Historical
        if len(hist_cap) > 0:
            fig_cap.add_trace(go.Scatter(
                x=hist_cap["year"].tolist(),
                y=hist_cap["cap_solar_gw"].tolist(),
                mode="markers+lines", name="Historical (ENTSO-E)",
                line=dict(color=C1, width=2),
                marker=dict(size=8, color=C1, line=dict(width=1.5, color=WHT)),
                hovertemplate="Year %{x}: %{y:.1f} GW<extra></extra>"))

        # Simulated scenario
        _cap_years = list(_cap_traj.keys())
        _cap_vals  = [_cap_traj[y] for y in _cap_years]
        fig_cap.add_trace(go.Scatter(
            x=_cap_years, y=_cap_vals,
            mode="markers+lines", name=f"Scenario: {_params.get('scenario','Custom')}",
            line=dict(color=C2, width=2.5, dash="dot"),
            marker=dict(size=8, color=C2, line=dict(width=1.5, color=WHT)),
            hovertemplate="Year %{x}: %{y:.1f} GW<extra></extra>"))

        # PPE3 reference lines
        fig_cap.add_hline(y=48.0, line_dash="dash", line_color=C3, line_width=1.5,
                          annotation_text="PPE3 2030: 48 GW",
                          annotation_position="right",
                          annotation_font=dict(size=10, color=C3, family="Calibri,Arial"))
        fig_cap.add_hline(y=67.5, line_dash="dash", line_color=C4, line_width=1.5,
                          annotation_text="PPE3 2035: 67.5 GW",
                          annotation_position="right",
                          annotation_font=dict(size=10, color=C4, family="Calibri,Arial"))

        fig_cap.update_layout(
            title=dict(text="<b>FR Solar Installed Capacity — Historical + Simulation Scenario</b>",
                       font=dict(size=13, color=C1, family="Calibri,Arial"),
                       x=0.5, xanchor="center"),
            height=300, margin=dict(l=50, r=100, t=50, b=60),
            plot_bgcolor=WHT, paper_bgcolor=WHT,
            xaxis=dict(title="Year", gridcolor="#eee",
                       tickfont=dict(family="Calibri,Arial", size=11)),
            yaxis=dict(title="Installed Capacity (GW)", gridcolor="#eee",
                       tickfont=dict(family="Calibri,Arial", size=11)),
            legend=dict(orientation="h", yanchor="top", y=-0.18,
                        xanchor="center", x=0.5, font=dict(size=11)))
        plotly_base(fig_cap, h=300)
        st.plotly_chart(fig_cap, use_container_width=True)

        # Multiplier table
        _mult_rows = [{"Year": yr,
                       "Capacity (GW)": f"{_cap_traj[yr]:.1f}",
                       "vs Current": f"×{_cap_traj[yr]/_params.get('current_cap_gw',24):.2f}",
                       "Forward (EUR)": f"{_params.get('forward', 55):.1f}"}
                      for yr in _cap_years]
        st.dataframe(pd.DataFrame(_mult_rows), use_container_width=True,
                     hide_index=True)
        desc(
            f"Solar multiplier applied to NatMW in hourly price simulation. "
            f"At ×{_cap_traj[max(_cap_years)]/_params.get('current_cap_gw',24):.2f} "
            f"capacity, cannibalization effect is proportionally amplified via β_solar."
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # S4-S8 — SIMULATION OUTPUTS
    # ═══════════════════════════════════════════════════════════════════════════
    if _results is None:
        st.markdown("---")
        st.info("Configure parameters above and click **▶ Run FPC Monte Carlo** to run the simulation.")
        # Methodology note
        _show_methodology()
        return

    years      = _results["years"]
    basis_used = _results["basis"]
    do_nat     = "nat"   in _results
    do_asset   = "asset" in _results
    do_both    = do_nat and do_asset

    # ── S4 : Shape Discount Fan Charts ───────────────────────────────────────
    st.markdown("---")
    section("Shape Discount — Forward Probability Fan Chart")
    desc(
        "Shape discount derived endogenously from simulated hourly prices. "
        "SD = 1 − (capture price / baseload). "
        "Baseload = mean of ALL simulated hours. Capture price = production-weighted average price. "
        "Bands show P10-P90 (outer) and P25-P75 (inner) of the simulation distribution."
    )

    if do_both:
        _s4a, _s4b = st.columns(2)
        with _s4a:
            fig = _fan_chart(years, _results["nat"]["sd_bands"],
                             "Shape Discount (%)", "Shape Discount — National",
                             C5, suffix="%", plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
        with _s4b:
            fig = _fan_chart(years, _results["asset"]["sd_bands"],
                             "Shape Discount (%)", f"Shape Discount — {asset_name}",
                             C4, suffix="%", plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
    elif do_nat:
        fig = _fan_chart(years, _results["nat"]["sd_bands"],
                         "Shape Discount (%)", "Shape Discount — National",
                         C5, suffix="%", plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)
    elif do_asset:
        fig = _fan_chart(years, _results["asset"]["sd_bands"],
                         "Shape Discount (%)", f"Shape Discount — {asset_name}",
                         C4, suffix="%", plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ── S5 : Capture Price Fan Charts ────────────────────────────────────────
    st.markdown("---")
    section("Capture Price — Forward Probability Fan Chart")
    desc(
        "Capture price = production-weighted average of simulated hourly prices. "
        "Orange dotted line = PPA price. When capture price < PPA → loss on that year."
    )

    if do_both:
        _s5a, _s5b = st.columns(2)
        with _s5a:
            fig = _fan_chart(years, _results["nat"]["cp_bands"],
                             "Capture Price (EUR/MWh)", "Capture Price — National",
                             C2, suffix=" EUR", ppa_line=ppa_input, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
        with _s5b:
            fig = _fan_chart(years, _results["asset"]["cp_bands"],
                             "Capture Price (EUR/MWh)", f"Capture Price — {asset_name}",
                             C2, suffix=" EUR", ppa_line=ppa_input, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
    elif do_nat:
        fig = _fan_chart(years, _results["nat"]["cp_bands"],
                         "Capture Price (EUR/MWh)", "Capture Price — National",
                         C2, suffix=" EUR", ppa_line=ppa_input, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)
    elif do_asset:
        fig = _fan_chart(years, _results["asset"]["cp_bands"],
                         "Capture Price (EUR/MWh)", f"Capture Price — {asset_name}",
                         C2, suffix=" EUR", ppa_line=ppa_input, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ── S6 : Annual P&L Fan Charts ───────────────────────────────────────────
    st.markdown("---")
    section("Annual P&L — Forward Probability Fan Chart")
    desc(
        "Annual P&L = (Capture Price − PPA) × Volume − Imbalance. "
        "Horizontal dashed line = break-even (P&L = 0). "
        "When P50 crosses zero → more than 50% of scenarios are loss-making for that year."
    )

    if do_both:
        _s6a, _s6b = st.columns(2)
        with _s6a:
            fig = _fan_chart(years, _results["nat"]["pnl_bands"],
                             "Annual P&L (k EUR)", "Annual P&L — National",
                             C2, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
        with _s6b:
            fig = _fan_chart(years, _results["asset"]["pnl_bands"],
                             "Annual P&L (k EUR)", f"Annual P&L — {asset_name}",
                             C2, plotly_base=plotly_base)
            st.plotly_chart(fig, use_container_width=True)
    elif do_nat:
        fig = _fan_chart(years, _results["nat"]["pnl_bands"],
                         "Annual P&L (k EUR)", "Annual P&L — National",
                         C2, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)
    elif do_asset:
        fig = _fan_chart(years, _results["asset"]["pnl_bands"],
                         "Annual P&L (k EUR)", f"Annual P&L — {asset_name}",
                         C2, plotly_base=plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ── S7 : Cumulative P&L Distribution ────────────────────────────────────
    st.markdown("---")
    section("Cumulative P&L Distribution")

    # KPI strips — separate for nat and asset
    if do_nat:
        _n = _results["nat"]
        st.markdown(
            f'<div style="font-size:12px;font-weight:700;color:{C1};margin-bottom:6px;">'
            f'National — {_results["n_sim"]:,} simulations</div>',
            unsafe_allow_html=True)
        ka, kb, kc, kd, ke = st.columns(5)
        with ka:
            _bg, _tx = _pnl_color(_n["percentiles_cumul"][10])
            st.markdown(_kpi("P10 Cumul P&L", _fmt_k(_n["percentiles_cumul"][10]), _bg, _tx),
                        unsafe_allow_html=True)
        with kb:
            _bg, _tx = _pnl_color(_n["percentiles_cumul"][50])
            st.markdown(_kpi("P50 Cumul P&L", _fmt_k(_n["percentiles_cumul"][50]), _bg, _tx),
                        unsafe_allow_html=True)
        with kc:
            _bg, _tx = _pnl_color(_n["percentiles_cumul"][90])
            st.markdown(_kpi("P90 Cumul P&L", _fmt_k(_n["percentiles_cumul"][90]), _bg, _tx),
                        unsafe_allow_html=True)
        with kd:
            _pl = _n["prob_loss"] * 100
            _c  = C5 if _pl > 20 else C3 if _pl > 10 else C2
            _t  = WHT if _pl > 20 or _pl <= 10 else C1
            st.markdown(_kpi("Prob. of Loss", f"{_pl:.1f}%", _c, _t), unsafe_allow_html=True)
        with ke:
            _bg, _tx = _pnl_color(_n["expected_shortfall"])
            st.markdown(_kpi("Expected Shortfall", _fmt_k(_n["expected_shortfall"]), _bg, _tx),
                        unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        fig = _hist_chart(_n["cumul_pnl"], tenor_yr,
                          f"Cumulative P&L Distribution — National — {tenor_yr}yr",
                          plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    if do_asset:
        _a = _results["asset"]
        st.markdown(
            f'<div style="font-size:12px;font-weight:700;color:{C1};margin:16px 0 6px;">'
            f'{asset_name} — {_results["n_sim"]:,} simulations</div>',
            unsafe_allow_html=True)
        ka2, kb2, kc2, kd2, ke2 = st.columns(5)
        with ka2:
            _bg, _tx = _pnl_color(_a["percentiles_cumul"][10])
            st.markdown(_kpi("P10 Cumul P&L", _fmt_k(_a["percentiles_cumul"][10]), _bg, _tx),
                        unsafe_allow_html=True)
        with kb2:
            _bg, _tx = _pnl_color(_a["percentiles_cumul"][50])
            st.markdown(_kpi("P50 Cumul P&L", _fmt_k(_a["percentiles_cumul"][50]), _bg, _tx),
                        unsafe_allow_html=True)
        with kc2:
            _bg, _tx = _pnl_color(_a["percentiles_cumul"][90])
            st.markdown(_kpi("P90 Cumul P&L", _fmt_k(_a["percentiles_cumul"][90]), _bg, _tx),
                        unsafe_allow_html=True)
        with kd2:
            _pl2 = _a["prob_loss"] * 100
            _c2  = C5 if _pl2 > 20 else C3 if _pl2 > 10 else C2
            _t2  = WHT if _pl2 > 20 or _pl2 <= 10 else C1
            st.markdown(_kpi("Prob. of Loss", f"{_pl2:.1f}%", _c2, _t2), unsafe_allow_html=True)
        with ke2:
            _bg, _tx = _pnl_color(_a["expected_shortfall"])
            st.markdown(_kpi("Expected Shortfall", _fmt_k(_a["expected_shortfall"]), _bg, _tx),
                        unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        fig = _hist_chart(_a["cumul_pnl"], tenor_yr,
                          f"Cumulative P&L Distribution — {asset_name} — {tenor_yr}yr",
                          plotly_base)
        st.plotly_chart(fig, use_container_width=True)

    # ── S8 : Decision Tables ─────────────────────────────────────────────────
    st.markdown("---")
    section("Decision Table — Annual P&L, Shape Discount & Risk")
    desc(
        "Each row = one contract year. All values from Monte Carlo simulation. "
        "SD P50 = median simulated shape discount. P&L P50/P10/P90 = percentile outcomes. "
        "Downside = P10 − P50. Upside = P90 − P50. Volatility = std of annual P&L across simulations."
    )

    if do_both:
        _t1, _t2 = st.columns(2)
        with _t1:
            _decision_table_display(
                _results["nat"]["scenario_table"],
                pd.DataFrame(_results["nat"]["scenario_table"]),
                "National — benchmark", ppa_input)
        with _t2:
            _decision_table_display(
                _results["asset"]["scenario_table"],
                pd.DataFrame(_results["asset"]["scenario_table"]),
                f"{asset_name} — deal P&L", ppa_input)
    elif do_nat:
        _decision_table_display(
            _results["nat"]["scenario_table"],
            pd.DataFrame(_results["nat"]["scenario_table"]),
            "National", ppa_input)
    elif do_asset:
        _decision_table_display(
            _results["asset"]["scenario_table"],
            pd.DataFrame(_results["asset"]["scenario_table"]),
            asset_name, ppa_input)

    # Summary box
    _ref = _results.get("nat") or _results.get("asset")
    if _ref:
        _cs = _ref["percentiles_cumul"]
        st.markdown(
            f'<div style="background:{C1};color:{WHT};padding:12px 20px;'
            f'margin-top:8px;border-radius:6px;font-family:Calibri,Arial;font-size:13px;">'
            f'<b>{tenor_yr}yr cumulative ({basis_used}):</b> &nbsp;'
            f'P50 = {_fmt_k(_cs[50])} &nbsp;|&nbsp; '
            f'P10 = {_fmt_k(_cs[10])} &nbsp;|&nbsp; '
            f'P90 = {_fmt_k(_cs[90])} &nbsp;|&nbsp; '
            f'Prob. loss = {_ref["prob_loss"]*100:.1f}% &nbsp;|&nbsp; '
            f'Downside = {_fmt_k(_ref["downside"])} &nbsp;|&nbsp; '
            f'Upside = {_fmt_k(_ref["upside"])}'
            f'</div>', unsafe_allow_html=True)

    # ── S9 : Methodology ─────────────────────────────────────────────────────
    st.markdown("---")
    _show_methodology()


def _show_methodology():
    with st.expander("Methodology — Model Specification & Limitations", expanded=False):
        st.markdown(f"""
**Causal flow**
```
Solar capacity (GW) → Solar output multiplier
→ Simulated hourly prices (OLS + block bootstrap residuals)
→ Anchoring to forward input (no-arbitrage)
→ Capture price (production-weighted)
→ Shape discount (endogenous output)
→ P&L
```

**Price model (OLS)**
```
Spot_h = α + β × SolarMW_h + Σ γ_k × Hour_k + Σ δ_m × Month_m + ε_h
```
Fitted on historical ENTSO-E data. β (solar coefficient) captures the cannibalization mechanism.

**Forward anchoring**
Simulated prices are rescaled so their annual average equals the forward input.
This enforces the absence-of-arbitrage principle: the forward is the market's unbiased estimate of future average spot.

**Shape discount definition**
- `capture_price` = Σ(Prod_h × Price_h) / Σ(Prod_h)
- `baseload` = mean of ALL simulated hours
- `shape_discount` = 1 − capture_price / baseload

**Block bootstrap**
Residuals are resampled in 168h (1-week) blocks to preserve autocorrelation.
52 blocks × 168h = 8,736h + 24h top-up = 8,760h per synthetic year.

**Assumptions & limitations**
- β assumed constant over tenor (may evolve with growing penetration)
- Flat forward across tenor years (V1 — extend to term structure later)
- No gas/CO2/nuclear covariates in price model
- No peak/base shaping at quarter granularity
- Historical residuals resampled — future volatility regime may differ
- National profile assumed stable over tenor
        """, unsafe_allow_html=False)
