"""
tab_pricer.py — KAL-EL : Asset Pricer & Risk Analysis
======================================================
Consolidated pricing + full risk decomposition tab.

P&L model (3 components):
  [1] CAL hedged   = P50e × (Forward × CP%_realised − PPA_fixed)
  [2] Volume delta = (Prod_realised − P50e) × DA_deboucle_price
  [3] Imbalance    = Prod × Imb_rate% × Forfait_EUR  (±20% stress)

HOW TO INTEGRATE IN app.py
───────────────────────────
1. Add at top of app.py (after existing imports):
       from tab_pricer import render_pricer_tab

2. In the st.tabs() call (~line 245) add one tab:
       tab1,...,tab9,tab10 = st.tabs([
           "Overview","Forward Curve & Pricing","Market Dynamics",
           "Sensitivity & Scenarios","Price Waterfall","Market Evolution",
           "Export & SPOT Extractor","Market Prices","Market Overview",
           "Asset Pricer",
       ])

3. Add before the footer in app.py:
       with tab10:
           render_pricer_tab(
               hourly=hourly,
               nat_ref_complete=nat_ref_complete,
               asset_ann=asset_ann,
               asset_name=asset_name,
               has_asset=has_asset,
               cfg=cfg,
               sl_u=sl_u, ic_u=ic_u,
               hist_sd_f=hist_sd_f,
               plotly_base=plotly_base,
           )
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from config    import C1, C2, C3, C4, C5, C2L, C3L, C5L, WHT, DEFAULT_FWD
from compute   import compute_ppa, project_cp
from ui        import section, desc
try:
    from bootstrap import run_bootstrap, percentile_from_dist, build_percentile_table
    _BS_OK = True
except ImportError:
    _BS_OK = False

try:
    from montecarlo import run_montecarlo
    _MC_OK = True
except ImportError:
    _MC_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _kpi(label, value, color=C1, text=WHT, border=None):
    bc = border or color
    return (
        f'<div style="background:{color};border-left:5px solid {bc};'
        f'padding:14px 18px;border-radius:6px;text-align:center;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.10);">'
        f'<div style="font-size:22px;font-weight:700;color:{text};'
        f'font-family:Calibri,Arial,sans-serif;">{value}</div>'
        f'<div style="font-size:11px;color:{text};opacity:0.85;'
        f'text-transform:uppercase;letter-spacing:0.06em;'
        f'font-family:Calibri,Arial,sans-serif;">{label}</div>'
        f'</div>'
    )


def _pnl_color(v):
    """Return (bg, text) colours for a P&L value."""
    if v > 50:   return C2,  WHT
    if v > 0:    return C2L, C1
    if v > -50:  return C5L, C1
    return C5, WHT


def _fmt_k(v):
    return f"{v:+.0f}k"


# ─────────────────────────────────────────────────────────────────────────────
# Core P&L computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_pnl_components(
    prod_p50_mwh: float,
    ppa_eur: float,
    forward_eur: float,
    shape_disc: float,
    vol_delta_pct: float,
    da_deboucle_discount: float,
    imb_rate_pct: float,
    imb_forfait_eur: float,
    imb_stress_pct: float,
) -> dict:
    """
    Three-component P&L model.

    [1] CAL hedged: P50e volume × (captured price − PPA)
        Captured price = forward × (1 − shape_disc)

    [2] Volume delta: over/under-production vs P50e sold/bought at DA price
        Surplus (delta > 0) → sold at DA depressed by solar cannib
        Deficit (delta < 0) → bought back at forward (less correlated)

    [3] Imbalance net of forfait:
        Cost = prod × imb_rate × forfait × (1 + stress)
        Stress > 0 → real settlement above forfait → extra cost
        Stress < 0 → real settlement below forfait → saving
    """
    cp_realised = forward_eur * (1 - shape_disc)

    # [1] CAL hedged
    pnl1_mwh  = cp_realised - ppa_eur
    pnl1_keur = prod_p50_mwh * pnl1_mwh / 1000

    # [2] Volume delta
    delta_mwh = prod_p50_mwh * vol_delta_pct
    if vol_delta_pct >= 0:
        # surplus sold at DA — depressed by solar peak
        deboucle_price = forward_eur * (1 - da_deboucle_discount)
    else:
        # deficit — buy back at forward (buy when solar is low = prices not depressed)
        deboucle_price = forward_eur
    pnl2_keur = delta_mwh * (deboucle_price - ppa_eur) / 1000
    pnl2_mwh  = pnl2_keur * 1000 / prod_p50_mwh if prod_p50_mwh > 0 else 0.0

    # [3] Imbalance net of forfait
    imb_vol_mwh   = prod_p50_mwh * imb_rate_pct
    imb_cost_keur = imb_vol_mwh * imb_forfait_eur * (1 + imb_stress_pct) / 1000
    pnl3_keur     = -imb_cost_keur   # always a cost; stress drives magnitude
    pnl3_mwh      = pnl3_keur * 1000 / prod_p50_mwh if prod_p50_mwh > 0 else 0.0

    total_keur = pnl1_keur + pnl2_keur + pnl3_keur
    total_mwh  = pnl1_mwh  + pnl2_mwh  + pnl3_mwh

    return {
        "pnl1_mwh": pnl1_mwh,   "pnl1_keur": pnl1_keur,
        "pnl2_mwh": pnl2_mwh,   "pnl2_keur": pnl2_keur,
        "pnl3_mwh": pnl3_mwh,   "pnl3_keur": pnl3_keur,
        "total_mwh": total_mwh,  "total_keur": total_keur,
        "cp_realised": cp_realised,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────

def _chart_pnl_vs_cannib(
    forward, ppa, prod_mwh, hist_sd_f, chosen_pct,
    vol_delta_pct, da_disc, imb_rate, imb_forfait, imb_stress,
    plotly_base,
):
    pcts    = list(range(1, 101))
    sd_vals = [
        float(np.percentile(hist_sd_f, p)) if len(hist_sd_f) > 0 else 0.15
        for p in pcts
    ]
    pnl_total, pnl1_s, pnl2_s, pnl3_s = [], [], [], []
    for sd in sd_vals:
        r = _compute_pnl_components(
            prod_mwh, ppa, forward, sd,
            vol_delta_pct, da_disc, imb_rate, imb_forfait, imb_stress,
        )
        pnl_total.append(r["total_keur"])
        pnl1_s.append(r["pnl1_keur"])
        pnl2_s.append(r["pnl2_keur"])
        pnl3_s.append(r["pnl3_keur"])

    be         = next((p for p, v in zip(pcts, pnl_total) if v < 0), None)
    chosen_pnl = pnl_total[chosen_pct - 1] if chosen_pct <= len(pnl_total) else 0

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=pcts, y=pnl1_s, name="[1] CAL hedged",
        mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(42,157,143,0.22)",
        hovertemplate="P%{x} — CAL: %{y:+.0f}k EUR<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=pcts, y=pnl2_s, name="[2] Volume delta",
        mode="lines", line=dict(width=2, color=C3, dash="dot"),
        hovertemplate="P%{x} — Vol delta: %{y:+.0f}k EUR<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=pcts, y=pnl3_s, name="[3] Imbalance",
        mode="lines", line=dict(width=2, color=C4, dash="dot"),
        hovertemplate="P%{x} — Imbalance: %{y:+.0f}k EUR<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=pcts, y=pnl_total, name="Total P&L",
        mode="lines", line=dict(width=3, color=C1),
        hovertemplate="P%{x} — Total: %{y:+.0f}k EUR<extra></extra>",
    ))

    fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)

    fig.add_vline(
        x=chosen_pct, line_width=1.5, line_dash="dot", line_color=C1,
        annotation_text=f"  P{chosen_pct}: {chosen_pnl:+.0f}k EUR",
        annotation_position="top right",
        annotation_font=dict(size=12, color=C1, family="Calibri,Arial"),
    )
    if be:
        fig.add_vline(
            x=be, line_width=1.5, line_color=C5,
            annotation_text=f"Break-even P{be}  ",
            annotation_position="top left",
            annotation_font=dict(size=12, color=C5, family="Calibri,Arial"),
        )

    fig.update_layout(
        height=420, margin=dict(l=50, r=30, t=30, b=50),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title="Cannibalization Percentile (historical distribution)",
                   gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
        yaxis=dict(title="P&L (k EUR/yr)", gridcolor="#eee",
                   tickfont=dict(family="Calibri,Arial", size=12), zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="center", x=0.5,
                    font=dict(family="Calibri,Arial", size=12)),
        hovermode="x unified",
    )
    return plotly_base(fig, h=420), be, chosen_pnl


def _chart_heatmap_risk(
    forward_range, cannib_range,
    prod_mwh, ppa, vol_delta_pct, da_disc,
    imb_rate, imb_forfait, imb_stress,
    forward_central, cannib_central,
    plotly_base,
):
    z = []
    for sd in cannib_range:
        row = []
        for fwd in forward_range:
            r = _compute_pnl_components(
                prod_mwh, ppa, fwd, sd,
                vol_delta_pct, da_disc, imb_rate, imb_forfait, imb_stress,
            )
            row.append(r["total_keur"])
        z.append(row)

    z_arr   = np.array(z)
    abs_max = max(abs(float(z_arr.min())), abs(float(z_arr.max())), 1.0)

    fig = go.Figure(go.Heatmap(
        x=[f"{f:.0f}" for f in forward_range],
        y=[f"{s*100:.0f}%" for s in cannib_range],
        z=z_arr,
        colorscale=[
            [0.00, C5],
            [0.45, "#FAEAE6"],
            [0.50, "#F7F4F0"],
            [0.55, C2L],
            [1.00, C2],
        ],
        zmid=0, zmin=-abs_max, zmax=abs_max,
        text=[[f"{v:+.0f}k" for v in row] for row in z_arr],
        texttemplate="%{text}",
        textfont=dict(size=11, family="Calibri,Arial"),
        hovertemplate=(
            "Forward: %{x} EUR/MWh<br>Cannib: %{y}<br>"
            "P&L: %{z:+.0f}k EUR/yr<extra></extra>"
        ),
        colorbar=dict(
            title=dict(
                text="P&L (k EUR/yr)",
                font=dict(family="Calibri,Arial", size=12),
            ),
            tickfont=dict(family="Calibri,Arial", size=11),
        ),
    ))

    # Mark current position
    fwd_labels  = [f"{f:.0f}" for f in forward_range]
    cann_labels = [f"{s*100:.0f}%" for s in cannib_range]
    cx = min(range(len(forward_range)), key=lambda i: abs(forward_range[i] - forward_central))
    cy = min(range(len(cannib_range)),  key=lambda i: abs(cannib_range[i]  - cannib_central))
    fig.add_trace(go.Scatter(
        x=[fwd_labels[cx]], y=[cann_labels[cy]],
        mode="markers",
        marker=dict(symbol="cross", size=18, color=C1,
                    line=dict(width=2.5, color=WHT)),
        name="Current position",
        hovertemplate=(
            f"Current position<br>"
            f"Forward: {forward_central:.0f} EUR/MWh<br>"
            f"Cannib: {cannib_central*100:.0f}%<extra></extra>"
        ),
    ))

    fig.update_layout(
        height=440, margin=dict(l=70, r=20, t=20, b=60),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title="Baseload Forward (EUR/MWh)",
                   tickfont=dict(family="Calibri,Arial", size=11)),
        yaxis=dict(title="Shape Discount (Cannibalization %)",
                   tickfont=dict(family="Calibri,Arial", size=11)),
        font=dict(family="Calibri,Arial", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18,
                    xanchor="center", x=0.5,
                    font=dict(family="Calibri,Arial", size=12)),
    )
    return plotly_base(fig, h=440)


def _chart_scenarios_decomposed(scenarios_data, tenor_yr, plotly_base):
    names   = [s["name"]      for s in scenarios_data]
    p50_tot = [s["p50_total"] for s in scenarios_data]
    p50_1   = [s["p50_1"]     for s in scenarios_data]
    p50_2   = [s["p50_2"]     for s in scenarios_data]
    p50_3   = [s["p50_3"]     for s in scenarios_data]
    p10_tot = [s["p10_total"] for s in scenarios_data]
    p90_tot = [s["p90_total"] for s in scenarios_data]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="[1] CAL hedged", x=names, y=p50_1,
        marker_color="rgba(42,157,143,0.75)",
        hovertemplate="%{x}<br>[1] CAL: %{y:+.0f}k EUR<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="[2] Volume delta", x=names, y=p50_2,
        marker_color="rgba(233,196,106,0.75)",
        hovertemplate="%{x}<br>[2] Vol delta: %{y:+.0f}k EUR<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="[3] Imbalance", x=names, y=p50_3,
        marker_color="rgba(244,162,97,0.75)",
        hovertemplate="%{x}<br>[3] Imbalance: %{y:+.0f}k EUR<extra></extra>",
    ))

    err_minus = [p - p10 for p, p10 in zip(p50_tot, p10_tot)]
    err_plus  = [p90 - p for p, p90 in zip(p50_tot, p90_tot)]
    fig.add_trace(go.Scatter(
        name="P50 total", x=names, y=p50_tot,
        mode="markers",
        marker=dict(symbol="diamond", size=12, color=C1,
                    line=dict(width=1.5, color=WHT)),
        error_y=dict(
            type="data", symmetric=False,
            array=err_plus, arrayminus=err_minus,
            color=C1, thickness=2, width=6,
        ),
        customdata=[[p10, p90] for p10, p90 in zip(p10_tot, p90_tot)],
        hovertemplate=(
            "%{x}<br>P50: %{y:+.0f}k<br>"
            "P10: %{customdata[0]:+.0f}k | P90: %{customdata[1]:+.0f}k<extra></extra>"
        ),
    ))

    fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)
    fig.update_layout(
        height=460, barmode="relative",
        margin=dict(l=50, r=20, t=20, b=100),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(tickfont=dict(family="Calibri,Arial", size=11), tickangle=-25),
        yaxis=dict(
            title=f"Cumulative P&L over {tenor_yr}yr (k EUR)",
            gridcolor="#eee",
            tickfont=dict(family="Calibri,Arial", size=12), zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.38,
                    xanchor="center", x=0.5,
                    font=dict(family="Calibri,Arial", size=12)),
        font=dict(family="Calibri,Arial", size=12),
        hovermode="x unified",
    )
    return plotly_base(fig, h=460)


# ─────────────────────────────────────────────────────────────────────────────
# Main render function
# ─────────────────────────────────────────────────────────────────────────────

def render_pricer_tab(
    hourly,
    nat_ref_complete,
    asset_ann,
    asset_name: str,
    has_asset: bool,
    cfg: dict,
    sl_u: float,
    ic_u: float,
    hist_sd_f,
    plotly_base,
    asset_raw=None,
):
    st.markdown(
        f'## Asset Pricer & Risk Analysis '
        f'<span style="font-size:13px;color:#888;font-weight:400">'
        f'— {asset_name}</span>',
        unsafe_allow_html=True,
    )
    desc(
        "Full P&L decomposition: [1] CAL hedged (cannibalization risk) + "
        "[2] Volume delta deboucle DA/ID + [3] Imbalance net of forfait. "
        "Adjust all inputs below — charts update instantly."
    )

    # ─── SECTION 1 : INPUTS ──────────────────────────────────────────────────
    st.markdown("---")
    section("Asset & Contract Parameters")

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:{C1};'
            f'margin-bottom:8px;">Production & Tenor</div>',
            unsafe_allow_html=True,
        )
        _prod_default = float(asset_ann["prod_gwh"].mean()) if has_asset else 52.0
        _prod_default = max(1.0, min(_prod_default, 50000.0))
        prod_p50 = st.number_input(
            "P50 production (GWh/yr)", 1.0, 50000.0,
            _prod_default,
            step=0.5, key="pr_prod_p50",
            help="Annual P50e — volume hedged in CAL at contract signature.",
        )
        vol_stress_pct = st.slider(
            "Volume stress (+/-% vs P50e)", 0, 30, 15, key="pr_vol_stress",
            help="Interannual production variance. Typical solar FR: ±10-20%.",
        )
        tenor_yr   = st.slider("Tenor (years)", 1, 15, 5, key="pr_tenor")
        forward_eur = st.number_input(
            "Baseload forward (EUR/MWh)", 20.0, 200.0,
            float(DEFAULT_FWD.get(2026, 55.0)), step=0.5, key="pr_fwd",
        )
        chosen_pct = st.slider(
            "Cannibalization percentile", 1, 100, 74, key="pr_pct",
            help=(
                "Percentile of the historical shape discount distribution used for pricing. "
                "P74 = WPD reference. Higher = more cannibalization priced in = more conservative."
            ),
        )

    with c_right:
        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:{C1};'
            f'margin-bottom:8px;">Discounts, Premiums & Risk Parameters</div>',
            unsafe_allow_html=True,
        )
        imb_forfait = st.number_input(
            "Imbalance forfait (EUR/MWh)", 0.0, 10.0, 1.9, step=0.1, key="pr_imb",
            help="Contractual fixed imbalance price. WPD reference: 1.9 EUR/MWh.",
        )
        imb_rate = st.number_input(
            "Imbalance rate (% of production)", 0.5, 15.0, 3.0, step=0.5,
            key="pr_imb_rate",
            help="% of production volume settled as imbalance. Typical solar FR: 2-5%.",
        ) / 100
        imb_stress = st.slider(
            "Imbalance forfait stress (+/-%%)", -30, 30, 20, key="pr_imb_stress",
            help=(
                "+20% = real RTE settlement price 20% above forfait → extra cost. "
                "-20% = real settlement below forfait → saving."
            ),
        ) / 100
        da_deboucle_disc = st.slider(
            "DA deboucle discount vs forward (%)", 0, 40, 20, key="pr_da_disc",
            help=(
                "When surplus (over-production), sold at DA price during solar peak hours. "
                "Structurally depressed vs forward. Typical: 15-25%."
            ),
        ) / 100
        add_disc = st.number_input(
            "Additional discount (%)", 0.0, 10.0, 0.0, step=0.25, key="pr_add_disc",
        ) / 100
        goo_val  = st.number_input(
            "GoO value (EUR/MWh)", 0.0, 10.0, 1.0, step=0.1, key="pr_goo",
        )
        margin   = st.number_input(
            "Margin (EUR/MWh)", 0.0, 10.0, 1.0, step=0.1, key="pr_margin",
        )

    # ─── PPA COMPUTATION — use bootstrap dist if available ─────────────────────
    _bs_dist = st.session_state.get('bs_dist', None)

    if _bs_dist is not None and _BS_OK:
        sd_chosen = percentile_from_dist(_bs_dist, chosen_pct)
        sd_p10    = percentile_from_dist(_bs_dist, 10)
        sd_p50    = percentile_from_dist(_bs_dist, 50)
        sd_p90    = percentile_from_dist(_bs_dist, 90)
        _sd_source = _bs_dist['method']
    else:
        # Fallback: np.percentile on 8-10 historical years
        sd_chosen = float(np.percentile(hist_sd_f, chosen_pct)) if len(hist_sd_f) > 0 else 0.15
        sd_p10    = float(np.percentile(hist_sd_f, 10))         if len(hist_sd_f) > 0 else 0.08
        sd_p50    = float(np.percentile(hist_sd_f, 50))         if len(hist_sd_f) > 0 else 0.15
        sd_p90    = float(np.percentile(hist_sd_f, 90))         if len(hist_sd_f) > 0 else 0.25
        _sd_source = f'Historical sample ({len(hist_sd_f)} years — run bootstrap for robust estimates)'
    pricing    = compute_ppa(forward_eur, sd_chosen, imb_forfait, add_disc,
                             goo_value=goo_val, margin=margin)
    ppa        = pricing["ppa"]
    multiplier = pricing["multiplier"]
    prod_mwh   = prod_p50 * 1000
    formula_str = f"{multiplier:.4f} x CAL - {imb_forfait:.1f}"


    # ─── SECTION 1b : BOOTSTRAP SIMULATION ──────────────────────────────────────
    st.markdown("---")
    section("Shape Discount Distribution — Block Bootstrap Simulation")

    _bs_dist = st.session_state.get("bs_dist", None)
    _bs_col1, _bs_col2 = st.columns([2, 1])

    with _bs_col2:
        ex22_bs = st.checkbox("Exclude 2022", value=False, key="bs_ex22")
        n_sim_bs = st.select_slider(
            "Simulations", options=[1_000, 5_000, 10_000, 20_000], value=10_000, key="bs_nsim",
            help="More simulations = smoother distribution. 10k takes ~3-5s."
        )
        run_bs = st.button("Run Bootstrap", key="bs_run",
                           help="Compute 10k synthetic years from hourly ENTSO-E data.")
        if run_bs and _BS_OK:
            with st.spinner(f"Running {n_sim_bs:,} simulations..."):
                try:
                    _bs_result = run_bootstrap(
                        hourly=hourly,
                        asset_raw=asset_raw,
                        prod_col=cfg["prod_col"],
                        n_sim=n_sim_bs,
                        exclude_2022=ex22_bs,
                    )
                    st.session_state["bs_dist"] = _bs_result
                    _bs_dist = _bs_result
                    st.success(f"Done — {_bs_result['n_sim']:,} scenarios computed.")
                except Exception as _e:
                    st.error(f"Bootstrap failed: {_e}")
        elif run_bs and not _BS_OK:
            st.error("bootstrap.py not found — add it to ppa_dashboard/.")

        if _bs_dist is not None:
            st.markdown(
                f'<div style="font-size:11px;color:{C1};background:{C2L};'
                f'border-left:3px solid {C2};padding:8px 12px;border-radius:4px;">'
                f'<strong>Source:</strong> {_bs_dist["prod_source"]}<br>'
                f'<strong>Pool:</strong> {_bs_dist["n_hours_pool"]:,} hours | '
                f'{_bs_dist["n_blocks"]} blocks × {_bs_dist["block_size_h"]}h<br>'
                f'<strong>Years:</strong> {", ".join(str(y) for y in _bs_dist["years_used"])}<br>'
                + (f'<strong>DA forecast coverage:</strong> {_bs_dist["fc_coverage_pct"]:.0f}%<br>'
                   if _bs_dist.get("fc_coverage_pct", 0) > 0 else "")
                + f'<strong>Asset profile:</strong> {"applied" if _bs_dist.get("asset_profile") else "national (upload asset for specific profile)"}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:12px;color:{C1};background:{C3L};'
                f'border-left:3px solid {C3};padding:8px 12px;border-radius:4px;">'
                f'Click "Run Bootstrap" to compute a robust shape discount distribution '
                f'from {len(hourly):,} hourly ENTSO-E observations.<br>'
                f'Until then, percentiles use np.percentile on {len(hist_sd_f)} historical years.'
                f'</div>',
                unsafe_allow_html=True,
            )

    with _bs_col1:
        if _bs_dist is not None:
            # Histogram of shape discount distribution
            import plotly.graph_objects as go
            _sd_arr  = _bs_dist["shape_disc_dist"] * 100
            _p10_v   = _bs_dist["percentiles"][10]  * 100
            _p50_v   = _bs_dist["percentiles"][50]  * 100
            _p74_v   = _bs_dist["percentiles"][74]  * 100
            _p90_v   = _bs_dist["percentiles"][90]  * 100
            _pch_v   = _bs_dist["percentiles"][chosen_pct] * 100

            _fig_bs = go.Figure()
            _fig_bs.add_trace(go.Histogram(
                x=_sd_arr, nbinsx=80, name="Shape Discount",
                marker_color=f"rgba(42,157,143,0.55)",
                marker_line_color=C2, marker_line_width=0.5,
                hovertemplate="Shape disc: %{x:.1f}%<br>Count: %{y}<extra></extra>",
            ))
            # Vertical lines for key percentiles
            for _pval, _plabel, _pcol in [
                (_p10_v,  "P10",  C2),
                (_p50_v,  "P50",  C1),
                (_p74_v,  "P74",  C3),
                (_p90_v,  "P90",  C5),
                (_pch_v,  f"P{chosen_pct} (chosen)", "#9B59B6"),
            ]:
                _fig_bs.add_vline(
                    x=_pval, line_width=2,
                    line_color=_pcol,
                    line_dash="dot" if _plabel != f"P{chosen_pct} (chosen)" else "solid",
                    annotation_text=f"  {_plabel}: {_pval:.1f}%",
                    annotation_position="top right",
                    annotation_font=dict(size=11, color=_pcol, family="Calibri,Arial"),
                )
            _fig_bs.update_layout(
                height=320, margin=dict(l=50, r=20, t=20, b=50),
                plot_bgcolor=WHT, paper_bgcolor=WHT,
                xaxis=dict(title="Shape Discount (%)", gridcolor="#eee",
                           tickfont=dict(family="Calibri,Arial", size=11)),
                yaxis=dict(title="Frequency", gridcolor="#eee",
                           tickfont=dict(family="Calibri,Arial", size=11)),
                showlegend=False,
                bargap=0.05,
            )
            plotly_base(_fig_bs, h=320, show_legend=False)
            st.plotly_chart(_fig_bs, use_container_width=True)

            # Key percentile table from bootstrap
            desc(
                f"Distribution of shape discount across {_bs_dist['n_sim']:,} synthetic years. "
                f"P74 = {_p74_v:.1f}% (vs {float(np.percentile(hist_sd_f,74))*100:.1f}% from {len(hist_sd_f)} historical years). "
                f"Chosen P{chosen_pct} = {_pch_v:.1f}%."
            )
        else:
            st.info("Run bootstrap to see the shape discount distribution.")

    # ─── SECTION 2 : PPA OUTPUT CARDS ────────────────────────────────────────
    st.markdown("---")
    section("PPA Price — Output")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(_kpi("PPA Price", f"{ppa:.2f} EUR/MWh", C1, WHT), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi("Multiplier", f"{multiplier:.4f}", C2, WHT), unsafe_allow_html=True)
    with k3:
        sd_d  = sd_chosen * 100
        c_sd  = C5 if sd_d > 25 else C3 if sd_d > 15 else C2
        t_sd  = WHT if sd_d > 25 or sd_d <= 15 else C1
        st.markdown(_kpi(f"Shape Disc P{chosen_pct}", f"{sd_d:.1f}%", c_sd, t_sd),
                    unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi("Capture Rate", f"{(1-sd_chosen)*100:.1f}%", C2L, C1, border=C2),
                    unsafe_allow_html=True)
    with k5:
        st.markdown(_kpi("Indexed Formula", formula_str, C3, C1), unsafe_allow_html=True)

    st.markdown(
        f'<div style="background:{C3L};border-left:4px solid {C3};padding:10px 16px;'
        f'border-radius:0 6px 6px 0;margin:12px 0;font-family:Calibri,Arial;'
        f'font-size:13px;color:{C1};">'
        f'<strong>Reading the percentile:</strong> P{chosen_pct} means the shape discount '
        f'retained ({sd_d:.1f}%) is higher than {chosen_pct}% of historical years observed '
        f'— a conservative pricing assumption. '
        f'This is <em>not</em> a probability: it is the {chosen_pct}th centile of a '
        f'small historical sample. Captured price assumed: '
        f'<strong>{forward_eur*(1-sd_chosen):.2f} EUR/MWh</strong>.'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ─── SECTION 3 : P&L CURVE ───────────────────────────────────────────────
    st.markdown("---")
    section("P&L vs Cannibalization Percentile — 3-Component Decomposition")
    desc(
        "Black line = total P&L. Green area = [1] CAL hedged (pure cannibalization risk). "
        "Gold dashed = [2] volume delta deboucle DA/ID. Orange dashed = [3] imbalance net of forfait. "
        "Dotted vertical = chosen percentile. Red vertical = break-even."
    )

    fig_pnl, be_pct, chosen_pnl = _chart_pnl_vs_cannib(
        forward_eur, ppa, prod_mwh, hist_sd_f, chosen_pct,
        vol_delta_pct=0.0, da_disc=da_deboucle_disc,
        imb_rate=imb_rate, imb_forfait=imb_forfait, imb_stress=imb_stress,
        plotly_base=plotly_base,
    )
    st.plotly_chart(fig_pnl, use_container_width=True)

    if be_pct:
        c_be = C5 if be_pct < chosen_pct else C3
        t_be = WHT if be_pct < chosen_pct else C1
        st.markdown(
            f'<div style="background:{c_be};color:{t_be};padding:10px 16px;'
            f'border-radius:6px;font-family:Calibri,Arial;font-size:13px;font-weight:600;">'
            f'Break-even at P{be_pct} — above this cannibalization level the total position '
            f'is loss-making. {"Your chosen P" + str(chosen_pct) + " is above break-even — at risk." if chosen_pct > be_pct else "Your chosen P" + str(chosen_pct) + " is below break-even — within profitable range."}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:{C2};color:{WHT};padding:10px 16px;border-radius:6px;'
            f'font-family:Calibri,Arial;font-size:13px;font-weight:600;">'
            f'No break-even in historical range — profitable across all observed cannibalization levels.'
            f'</div>', unsafe_allow_html=True,
        )

    # ─── SECTION 4 : RISK HEATMAP ────────────────────────────────────────────
    st.markdown("---")
    section("Risk Heatmap — Forward Price x Cannibalization")
    desc(
        "Each cell = total annual P&L (kEUR) for a given (forward, cannibalization) pair. "
        "Green = profit, red = loss. Cross = current position (forward input x chosen percentile). "
        "Read rows: how far can the forward fall before break-even at a given cannibalization level?"
    )

    fwd_step      = 5.0
    forward_range = [
        round(f, 1)
        for f in np.arange(max(20.0, forward_eur - 20), min(150.0, forward_eur + 21), fwd_step)
    ]
    cann_step     = 0.05
    cannib_range  = [
        round(c, 3)
        for c in np.arange(max(0.0, sd_chosen - 0.20), min(0.70, sd_chosen + 0.21), cann_step)
    ]

    fig_hm = _chart_heatmap_risk(
        forward_range, cannib_range, prod_mwh, ppa,
        vol_delta_pct=0.0, da_disc=da_deboucle_disc,
        imb_rate=imb_rate, imb_forfait=imb_forfait, imb_stress=imb_stress,
        forward_central=forward_eur, cannib_central=sd_chosen,
        plotly_base=plotly_base,
    )
    st.plotly_chart(fig_hm, use_container_width=True)


    # ─── SECTION 5b : MONTE CARLO SIMULATION ─────────────────────────────────
    st.markdown("---")
    section(f"Monte Carlo — P&L Distribution over {tenor_yr}-Year Tenor")
    desc(
        "10,000 simulated trajectories combining 3 independent risk sources: "
        "[1] Cannibalization trend (regression) + intra-year variance (bootstrap), "
        "[2] Production variance (±vol std vs P50), "
        "[3] Forward price uncertainty (±fwd std). "
        "Each trajectory = one possible outcome of the full contract. "
        "Run bootstrap first for best cannibalization distribution."
    )

    _mc_dist = st.session_state.get("mc_dist", None)

    _mc_c1, _mc_c2 = st.columns([3, 1])

    with _mc_c2:
        vol_std_mc  = st.slider("Production std (% of P50)", 5, 30, 12, key="mc_vol_std",
                                help="Interannual production variance. Solar FR typical: 10-15%.") / 100
        fwd_std_mc  = st.slider("Forward price std (%)", 2, 25, 10, key="mc_fwd_std",
                                help="Annual forward price uncertainty around central scenario.") / 100
        n_sim_mc    = st.select_slider("Simulations", options=[1_000, 5_000, 10_000, 20_000],
                                       value=10_000, key="mc_nsim")
        run_mc = st.button("Run Monte Carlo", key="mc_run")

        if run_mc:
            if not _MC_OK:
                st.error("montecarlo.py not found — add it to ppa_dashboard/.")
            else:
                _last_yr_mc = (
                    int(asset_ann["Year"].max()) if has_asset
                    else (int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025)
                )
                with st.spinner(f"Simulating {n_sim_mc:,} trajectories..."):
                    try:
                        _mc_result = run_montecarlo(
                            ppa=ppa,
                            forward_eur=forward_eur,
                            prod_p50_mwh=prod_mwh,
                            sl_u=sl_u,
                            ic_u=ic_u,
                            last_yr=_last_yr_mc,
                            tenor=tenor_yr,
                            bs_dist=st.session_state.get("bs_dist", None),
                            hist_sd_f=hist_sd_f,
                            vol_std=vol_std_mc,
                            fwd_std=fwd_std_mc,
                            imb_rate=imb_rate,
                            imb_forfait=imb_forfait,
                            n_sim=n_sim_mc,
                        )
                        st.session_state["mc_dist"] = _mc_result
                        _mc_dist = _mc_result
                        st.success(f"Done — {n_sim_mc:,} trajectories computed.")
                    except Exception as _e:
                        st.error(f"Monte Carlo failed: {_e}")

    with _mc_c1:
        if _mc_dist is not None:
            import plotly.graph_objects as go

            # ── KPI strip ─────────────────────────────────────────────────
            _p10c = _mc_dist["percentiles_cumul"][10]
            _p50c = _mc_dist["percentiles_cumul"][50]
            _p90c = _mc_dist["percentiles_cumul"][90]
            _ploss = _mc_dist["prob_loss"] * 100
            _es    = _mc_dist["expected_shortfall"]

            _kc1, _kc2, _kc3, _kc4, _kc5 = st.columns(5)
            with _kc1:
                _bg, _tx = _pnl_color(_p10c)
                st.markdown(_kpi("P10 cumul (kEUR)", _fmt_k(_p10c), _bg, _tx),
                            unsafe_allow_html=True)
            with _kc2:
                _bg, _tx = _pnl_color(_p50c)
                st.markdown(_kpi("P50 cumul (kEUR)", _fmt_k(_p50c), _bg, _tx),
                            unsafe_allow_html=True)
            with _kc3:
                _bg, _tx = _pnl_color(_p90c)
                st.markdown(_kpi("P90 cumul (kEUR)", _fmt_k(_p90c), _bg, _tx),
                            unsafe_allow_html=True)
            with _kc4:
                _c_loss = C5 if _ploss > 20 else C3 if _ploss > 10 else C2
                _t_loss = WHT if _ploss > 20 or _ploss <= 10 else C1
                st.markdown(_kpi("Prob. of loss", f"{_ploss:.1f}%", _c_loss, _t_loss),
                            unsafe_allow_html=True)
            with _kc5:
                _bg, _tx = _pnl_color(_es)
                st.markdown(_kpi("Expected Shortfall P10", _fmt_k(_es), _bg, _tx),
                            unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Chart 1: Cumulative P&L histogram ─────────────────────────
            _cum_arr = _mc_dist["cumul_pnl"]
            _fig_mc = go.Figure()
            _fig_mc.add_trace(go.Histogram(
                x=_cum_arr, nbinsx=100,
                marker_color="rgba(42,157,143,0.50)",
                marker_line_color=C2, marker_line_width=0.3,
                name="Simulated P&L",
                hovertemplate="P&L: %{x:.0f}k EUR<br>Count: %{y}<extra></extra>",
            ))
            # Shade loss region
            _x_min = float(_cum_arr.min())
            _fig_mc.add_vrect(
                x0=_x_min, x1=0,
                fillcolor="rgba(231,111,81,0.12)", line_width=0,
                annotation_text="Loss zone",
                annotation_position="top left",
                annotation_font=dict(size=10, color=C5, family="Calibri,Arial"),
            )
            for _pv, _pl, _pc in [
                (_p10c, "P10", C5),
                (_p50c, "P50", C1),
                (_p90c, "P90", C2),
            ]:
                _fig_mc.add_vline(
                    x=_pv, line_width=2, line_color=_pc, line_dash="dot",
                    annotation_text=f"  {_pl}: {_pv:+.0f}k",
                    annotation_position="top right",
                    annotation_font=dict(size=11, color=_pc, family="Calibri,Arial"),
                )
            _fig_mc.add_vline(x=0, line_width=2, line_color=C5)
            _fig_mc.update_layout(
                height=300, margin=dict(l=50, r=20, t=20, b=50),
                plot_bgcolor=WHT, paper_bgcolor=WHT,
                xaxis=dict(title=f"Cumulative P&L over {tenor_yr}yr (k EUR)",
                           gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=11)),
                yaxis=dict(title="Frequency", gridcolor="#eee",
                           tickfont=dict(family="Calibri,Arial", size=11)),
                showlegend=False, bargap=0.02,
            )
            plotly_base(_fig_mc, h=300, show_legend=False)
            st.plotly_chart(_fig_mc, use_container_width=True)

            # ── Chart 2: Annual fan chart ──────────────────────────────────
            _years   = _mc_dist["years"]
            _bands   = _mc_dist["percentile_bands"]
            _trend   = _mc_dist["pnl_trend"]

            _fig_fan = go.Figure()

            # P10-P90 band
            _fig_fan.add_trace(go.Scatter(
                x=_years + _years[::-1],
                y=_bands[90].tolist() + _bands[10].tolist()[::-1],
                fill="toself", fillcolor="rgba(42,157,143,0.12)",
                line=dict(color="rgba(0,0,0,0)"), name="P10-P90",
            ))
            # P25-P75 band
            _fig_fan.add_trace(go.Scatter(
                x=_years + _years[::-1],
                y=_bands[75].tolist() + _bands[25].tolist()[::-1],
                fill="toself", fillcolor="rgba(42,157,143,0.25)",
                line=dict(color="rgba(0,0,0,0)"), name="P25-P75",
            ))
            # P50 median
            _fig_fan.add_trace(go.Scatter(
                x=_years, y=_bands[50].tolist(),
                mode="lines+markers", name="P50 (median)",
                line=dict(color=C2, width=2.5),
                marker=dict(size=7, color=C2, line=dict(width=1.5, color=WHT)),
                hovertemplate="Year %{x}: P50 = %{y:+.0f}k EUR<extra></extra>",
            ))
            # Trend-only reference
            _fig_fan.add_trace(go.Scatter(
                x=_years, y=_trend.tolist(),
                mode="lines", name="Trend only (no noise)",
                line=dict(color=C1, width=1.5, dash="dot"),
                hovertemplate="Year %{x}: trend = %{y:+.0f}k EUR<extra></extra>",
            ))
            _fig_fan.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)
            _fig_fan.update_layout(
                height=340, margin=dict(l=50, r=20, t=20, b=50),
                plot_bgcolor=WHT, paper_bgcolor=WHT,
                xaxis=dict(title="Year", tickmode="array", tickvals=_years,
                           gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=11)),
                yaxis=dict(title="Annual P&L (k EUR)", gridcolor="#eee",
                           tickfont=dict(family="Calibri,Arial", size=11), zeroline=False),
                legend=dict(orientation="h", yanchor="bottom", y=-0.30,
                            xanchor="center", x=0.5,
                            font=dict(family="Calibri,Arial", size=11)),
                hovermode="x unified",
            )
            plotly_base(_fig_fan, h=340)
            st.plotly_chart(_fig_fan, use_container_width=True)

            desc(
                f"Fan chart: dark green = P25-P75 (50% of outcomes). "
                f"Light green = P10-P90 (80% of outcomes). "
                f"Dotted = deterministic trend (no noise). "
                f"Source: [{_mc_dist['n_sim']:,} simulations | "
                f"vol std: {vol_std_mc*100:.0f}% | fwd std: {fwd_std_mc*100:.0f}% | "
                f"cannib: {'bootstrap' if _mc_dist['use_bootstrap'] else 'historical std'}]"
            )

        else:
            st.info(
                "Click 'Run Monte Carlo' to simulate 10,000 contract trajectories. "
                "Run bootstrap first for best cannibalization distribution."
            )

    # ─── SECTION 5 : STRESS SCENARIOS ────────────────────────────────────────
    st.markdown("---")
    section(f"Stress Scenarios — Cumulative P&L over {tenor_yr} Years")
    desc(
        "Stacked bars = P50 P&L by component [1]/[2]/[3]. "
        "Diamond + error bar = P50 total with P10-P90 range from cannibalization uncertainty "
        "(P10 = worst cannib at P90 of historical distribution, P90 = best cannib at P10). "
        "This separates the scenario assumption from the cannibalization uncertainty within it."
    )

    vs = vol_stress_pct / 100

    def _sc(name, fwd_mult, sd_delta, vol_delta, imb_s):
        fwd_s = forward_eur * fwd_mult
        def _r(sd_base):
            return _compute_pnl_components(
                prod_mwh, ppa, fwd_s, max(0.0, sd_base + sd_delta),
                vol_delta, da_deboucle_disc, imb_rate, imb_forfait, imb_s,
            )
        rp50 = _r(sd_p50)
        rp10 = _r(sd_p90)   # P10 P&L = worst cannib scenario
        rp90 = _r(sd_p10)   # P90 P&L = best cannib scenario
        return {
            "name":      name,
            "p50_total": rp50["total_keur"] * tenor_yr,
            "p10_total": rp10["total_keur"] * tenor_yr,
            "p90_total": rp90["total_keur"] * tenor_yr,
            "p50_1":     rp50["pnl1_keur"]  * tenor_yr,
            "p50_2":     rp50["pnl2_keur"]  * tenor_yr,
            "p50_3":     rp50["pnl3_keur"]  * tenor_yr,
        }

    scenarios = [
        _sc("Base",                      1.00,  0.00,  0.00,  imb_stress),
        _sc("Fwd +10%",                  1.10,  0.00,  0.00,  imb_stress),
        _sc("Fwd -10%",                  0.90,  0.00,  0.00,  imb_stress),
        _sc("Cannib +10pp",              1.00, +0.10,  0.00,  imb_stress),
        _sc("Cannib -10pp",              1.00, -0.10,  0.00,  imb_stress),
        _sc(f"Over-prod +{vol_stress_pct}%",   1.00,  0.00, +vs,  imb_stress),
        _sc(f"Under-prod -{vol_stress_pct}%",  1.00,  0.00, -vs,  imb_stress),
        _sc("Imb stress +20%",           1.00,  0.00,  0.00, +0.20),
        _sc("Bear (Fwd-10, Cannib+10pp)",0.90, +0.10,  -vs, +0.20),
        _sc("Bull (Fwd+10, Cannib-10pp)",1.10, -0.10,  +vs, -0.20),
    ]

    fig_sc = _chart_scenarios_decomposed(scenarios, tenor_yr, plotly_base)
    st.plotly_chart(fig_sc, use_container_width=True)

    # ─── SECTION 6 : SCENARIO TABLE ──────────────────────────────────────────
    st.markdown("---")
    section("Scenario Detail Table")
    desc(
        "All values in kEUR cumulative over the tenor. "
        "P10 = worst outcome (highest historical cannibalization). "
        "P90 = best outcome (lowest historical cannibalization). "
        "Colour on P50 Total: green = profit, red = loss."
    )

    trows = []
    for s in scenarios:
        trows.append({
            "Scenario":       s["name"],
            "[1] CAL":        _fmt_k(s["p50_1"]),
            "[2] Vol delta":  _fmt_k(s["p50_2"]),
            "[3] Imbalance":  _fmt_k(s["p50_3"]),
            "P50 Total":      _fmt_k(s["p50_total"]),
            "P10 (worst)":    _fmt_k(s["p10_total"]),
            "P90 (best)":     _fmt_k(s["p90_total"]),
        })

    tdf = pd.DataFrame(trows)

    def _style_tdf(row):
        idx = tdf.columns.get_loc("P50 Total")
        try:
            val = float(row["P50 Total"].replace("k", "").replace("+", ""))
        except Exception:
            val = 0
        base = [""] * len(row)
        if row["Scenario"] == "Base":
            return [f"background-color:{C2};color:{WHT};font-weight:bold"] * len(row)
        bg, txt = _pnl_color(val)
        base[idx] = f"background-color:{bg};color:{txt};font-weight:600"
        return base

    st.dataframe(
        tdf.style.apply(_style_tdf, axis=1),
        use_container_width=True, hide_index=True,
    )

    # ─── SECTION 7 : ANNUAL PROJECTION TABLE ─────────────────────────────────
    st.markdown("---")
    section(f"Annual P&L Projection — {tenor_yr}-Year Tenor")
    desc(
        "Shape discount projected year-by-year using the regression trend, "
        "offset by the chosen percentile vs P50. "
        "Shows whether the contract remains profitable as cannibalization grows."
    )

    last_yr_proj = (
        int(asset_ann["Year"].max()) if has_asset
        else (int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025)
    )
    proj_df = project_cp(sl_u, ic_u, last_yr_proj, tenor_yr, anchor_val=None)

    sd_offset = sd_chosen - sd_p50   # shift chosen pct vs median

    ann_rows = []
    for _, row in proj_df.iterrows():
        yr    = int(row["year"])
        # Projected P50 shape disc + offset for chosen pct
        fsd_yr = max(0.0, (1 - row["p50"]) + sd_offset)
        cp_yr  = forward_eur * (1 - fsd_yr)
        r = _compute_pnl_components(
            prod_mwh, ppa, forward_eur, fsd_yr,
            0.0, da_deboucle_disc, imb_rate, imb_forfait, imb_stress,
        )
        ann_rows.append({
            "Year":               yr,
            "Proj. Shape Disc":   f"{fsd_yr*100:.1f}%",
            "Captured (EUR/MWh)": f"{cp_yr:.2f}",
            "PPA (EUR/MWh)":      f"{ppa:.2f}",
            "P&L/MWh":            f"{r['total_mwh']:+.2f}",
            "[1] CAL (kEUR)":     _fmt_k(r["pnl1_keur"]),
            "[2] Vol (kEUR)":     _fmt_k(r["pnl2_keur"]),
            "[3] Imb (kEUR)":     _fmt_k(r["pnl3_keur"]),
            "Total (kEUR)":       _fmt_k(r["total_keur"]),
        })

    adf = pd.DataFrame(ann_rows)

    def _style_ann(row):
        idx = adf.columns.get_loc("Total (kEUR)")
        try:
            val = float(row["Total (kEUR)"].replace("k", "").replace("+", ""))
        except Exception:
            val = 0
        base = [""] * len(row)
        bg, txt = _pnl_color(val)
        base[idx] = f"background-color:{bg};color:{txt};font-weight:700"
        return base

    st.dataframe(
        adf.style.apply(_style_ann, axis=1),
        use_container_width=True, hide_index=True,
    )

    cumul = sum(
        float(r["Total (kEUR)"].replace("k", "").replace("+", ""))
        for r in ann_rows
    )
    c_cum = C2 if cumul > 0 else C5
    st.markdown(
        f'<div style="background:{c_cum};color:{WHT};padding:12px 20px;margin-top:8px;'
        f'border-radius:6px;font-family:Calibri,Arial;font-size:14px;font-weight:700;">'
        f'Cumulative P&L over {tenor_yr} years at P{chosen_pct}: {cumul:+.0f}k EUR'
        f'</div>',
        unsafe_allow_html=True,
    )
