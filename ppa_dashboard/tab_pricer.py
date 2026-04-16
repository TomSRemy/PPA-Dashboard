"""
tab_pricer.py — KAL-EL : Pricing & Risk Analysis v3
=====================================================
Clean, consistent, decision-oriented.

No bootstrap. Monte Carlo aligned with regression logic.

Sections:
  S1  Contract parameters (inputs)
  S2  National vs Asset toggle — side-by-side comparison
  S3  PPA Price output
  S4  P&L vs Cannibalization curve (3 components)
  S5  Risk Heatmap (forward × cannibalization)
  S6  Monte Carlo — P&L + Shape Discount + Capture Price fan charts
  S7  Decision table (annual, year-by-year)
  S8  Annual projection (deterministic)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from config  import C1, C2, C3, C4, C5, C2L, C3L, C5L, WHT, DEFAULT_FWD
from compute import compute_ppa, project_cp
from ui      import section, desc

try:
    from montecarlo import run_montecarlo
    _MC_OK = True
except ImportError:
    _MC_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
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
    if v > 50:  return C2,  WHT
    if v > 0:   return C2L, C1
    if v > -50: return C5L, C1
    return C5, WHT


def _fmt_k(v):
    return f"{v:+.0f}k"


def _pnl_components(prod_mwh, ppa, forward, sd, da_disc, imb_rate,
                    imb_forfait, imb_stress, vol_delta=0.0):
    """Compute P&L decomposition. Returns dict (kEUR/yr)."""
    cp  = forward * (1 - sd)
    p1  = prod_mwh * (cp - ppa) / 1000
    delta  = prod_mwh * vol_delta
    da_px  = forward * (1 - da_disc) if vol_delta >= 0 else forward
    p2  = delta * (da_px - ppa) / 1000
    p3  = -(prod_mwh * imb_rate * imb_forfait * (1 + imb_stress) / 1000)
    return {"p1": p1, "p2": p2, "p3": p3, "total": p1 + p2 + p3, "cp": cp}


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders (standalone, no nested columns)
# ─────────────────────────────────────────────────────────────────────────────

def _chart_pnl_curve(forward, ppa, prod_mwh, sd_series, chosen_pct,
                     da_disc, imb_rate, imb_forfait, imb_stress, label, plotly_base):
    """P&L vs cannibalization percentile — 3 components."""
    pcts = list(range(1, 101))
    sd_vals = [float(np.percentile(sd_series, p)) if len(sd_series) > 0 else 0.15
               for p in pcts]
    p1s, p2s, p3s, tots = [], [], [], []
    for sd in sd_vals:
        r = _pnl_components(prod_mwh, ppa, forward, sd, da_disc,
                            imb_rate, imb_forfait, imb_stress)
        p1s.append(r["p1"]); p2s.append(r["p2"])
        p3s.append(r["p3"]); tots.append(r["total"])

    be         = next((p for p, v in zip(pcts, tots) if v < 0), None)
    chosen_pnl = tots[chosen_pct - 1] if chosen_pct <= len(tots) else 0

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pcts, y=p1s, name="[1] Hedged P&L",
        mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(42,157,143,0.22)",
        hovertemplate="P%{x} — Hedged: %{y:+.0f}k EUR<extra></extra>"))
    fig.add_trace(go.Scatter(x=pcts, y=p2s, name="[2] Merchant",
        mode="lines", line=dict(width=2, color=C3, dash="dot"),
        hovertemplate="P%{x} — Merchant: %{y:+.0f}k EUR<extra></extra>"))
    fig.add_trace(go.Scatter(x=pcts, y=p3s, name="[3] Imbalance",
        mode="lines", line=dict(width=2, color=C4, dash="dot"),
        hovertemplate="P%{x} — Imbalance: %{y:+.0f}k EUR<extra></extra>"))
    fig.add_trace(go.Scatter(x=pcts, y=tots, name="Total P&L",
        mode="lines", line=dict(width=3, color=C1),
        hovertemplate="P%{x} — Total: %{y:+.0f}k EUR<extra></extra>"))

    fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)
    fig.add_vline(x=chosen_pct, line_width=1.5, line_dash="dot", line_color=C1,
        annotation_text=f"  P{chosen_pct}: {chosen_pnl:+.0f}k EUR",
        annotation_position="top right",
        annotation_font=dict(size=12, color=C1, family="Calibri,Arial"))
    if be:
        fig.add_vline(x=be, line_width=1.5, line_color=C5,
            annotation_text=f"Break-even P{be}  ",
            annotation_position="top left",
            annotation_font=dict(size=12, color=C5, family="Calibri,Arial"))

    fig.update_layout(
        title=dict(text=f"<b>P&L vs Cannibalization Percentile — {label}</b>",
                   font=dict(size=13, color=C1, family="Calibri,Arial"),
                   x=0.5, xanchor="center"),
        height=400, margin=dict(l=50, r=30, t=50, b=80),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title="Cannibalization Percentile",
                   gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
        yaxis=dict(title="Annual P&L (k EUR)", gridcolor="#eee",
                   tickfont=dict(family="Calibri,Arial", size=12), zeroline=False),
        legend=dict(orientation="h", yanchor="top", y=-0.18,
                    xanchor="center", x=0.5, font=dict(family="Calibri,Arial", size=12)),
        hovermode="x unified")
    return plotly_base(fig, h=400), be, chosen_pnl


def _chart_heatmap(forward_range, cannib_range, prod_mwh, ppa,
                   da_disc, imb_rate, imb_forfait, imb_stress,
                   fwd_central, sd_central, plotly_base):
    """Risk heatmap: forward × cannibalization → total P&L."""
    z = [[_pnl_components(prod_mwh, ppa, fwd, sd, da_disc,
                          imb_rate, imb_forfait, imb_stress)["total"]
          for fwd in forward_range]
         for sd in cannib_range]
    z_arr   = np.array(z)
    abs_max = max(abs(float(z_arr.min())), abs(float(z_arr.max())), 1.0)

    fig = go.Figure(go.Heatmap(
        x=[f"{f:.0f}" for f in forward_range],
        y=[f"{s*100:.0f}%" for s in cannib_range],
        z=z_arr, zmid=0, zmin=-abs_max, zmax=abs_max,
        colorscale=[[0, C5],[0.45,"#FAEAE6"],[0.5,"#F7F4F0"],[0.55,C2L],[1,C2]],
        text=[[f"{v:+.0f}k" for v in row] for row in z_arr],
        texttemplate="%{text}", textfont=dict(size=11, family="Calibri,Arial"),
        hovertemplate="Forward: %{x}<br>Cannib: %{y}<br>P&L: %{z:+.0f}k EUR<extra></extra>",
        colorbar=dict(title=dict(text="P&L (k EUR/yr)",
                                 font=dict(family="Calibri,Arial", size=12)),
                      tickfont=dict(family="Calibri,Arial", size=11))))

    fwd_labels  = [f"{f:.0f}" for f in forward_range]
    cann_labels = [f"{s*100:.0f}%" for s in cannib_range]
    cx = min(range(len(forward_range)), key=lambda i: abs(forward_range[i] - fwd_central))
    cy = min(range(len(cannib_range)),  key=lambda i: abs(cannib_range[i]  - sd_central))
    fig.add_trace(go.Scatter(
        x=[fwd_labels[cx]], y=[cann_labels[cy]], mode="markers",
        marker=dict(symbol="cross", size=18, color=C1, line=dict(width=2.5, color=WHT)),
        name="Current position",
        hovertemplate=f"Current: {fwd_central:.0f} EUR/MWh, {sd_central*100:.0f}% cannib<extra></extra>"))

    fig.update_layout(
        title=dict(text="<b>Risk Heatmap — Forward Price × Cannibalization → Annual P&L</b>",
                   font=dict(size=13, color=C1, family="Calibri,Arial"),
                   x=0.5, xanchor="center"),
        height=420, margin=dict(l=70, r=20, t=50, b=60),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title="Baseload Forward (EUR/MWh)",
                   tickfont=dict(family="Calibri,Arial", size=11)),
        yaxis=dict(title="Shape Discount (Cannibalization)",
                   tickfont=dict(family="Calibri,Arial", size=11)),
        legend=dict(orientation="h", yanchor="top", y=-0.12,
                    xanchor="center", x=0.5, font=dict(family="Calibri,Arial", size=12)))
    return plotly_base(fig, h=420)


def _fan_chart(years, bands, trend, y_title, title, color, suffix="", plotly_base=None):
    """Generic fan chart (P10-P90 + P25-P75 + P50 + trend)."""
    fig = go.Figure()
    alpha_outer = "rgba(42,157,143,0.10)" if color == C2 else "rgba(231,111,81,0.10)"
    alpha_inner = "rgba(42,157,143,0.22)" if color == C2 else "rgba(231,111,81,0.22)"

    p10 = [v + (suffix == "%" and 0 or 0) for v in bands[10]]
    p25 = bands[25]; p50 = bands[50]; p75 = bands[75]; p90 = bands[90]

    fig.add_trace(go.Scatter(
        x=years + years[::-1], y=p90 + p10[::-1],
        fill="toself", fillcolor=alpha_outer,
        line=dict(color="rgba(0,0,0,0)"), name="P10–P90"))
    fig.add_trace(go.Scatter(
        x=years + years[::-1], y=p75 + p25[::-1],
        fill="toself", fillcolor=alpha_inner,
        line=dict(color="rgba(0,0,0,0)"), name="P25–P75"))
    fig.add_trace(go.Scatter(
        x=years, y=p50, mode="lines+markers", name="P50 (median)",
        line=dict(color=color, width=2.5),
        marker=dict(size=7, color=color, line=dict(width=1.5, color=WHT)),
        hovertemplate=f"Year %{{x}}: P50 = %{{y:.1f}}{suffix}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=years, y=trend, mode="lines", name="Regression trend",
        line=dict(color=C1, width=1.5, dash="dot"),
        hovertemplate=f"Year %{{x}}: trend = %{{y:.1f}}{suffix}<extra></extra>"))

    if suffix != "%":
        fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=C5)

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>",
                   font=dict(size=13, color=C1, family="Calibri,Arial"),
                   x=0.5, xanchor="center"),
        height=320, margin=dict(l=50, r=20, t=50, b=80),
        plot_bgcolor=WHT, paper_bgcolor=WHT,
        xaxis=dict(title="Contract Year", tickmode="array", tickvals=years,
                   gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=11)),
        yaxis=dict(title=y_title, gridcolor="#eee",
                   tickfont=dict(family="Calibri,Arial", size=11),
                   zeroline=False,
                   ticksuffix=suffix if suffix == "%" else ""),
        legend=dict(orientation="h", yanchor="top", y=-0.22,
                    xanchor="center", x=0.5, font=dict(family="Calibri,Arial", size=11)),
        hovermode="x unified")
    if plotly_base:
        plotly_base(fig, h=320)
    return fig


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
        f'## Pricing & Risk Analysis '
        f'<span style="font-size:13px;color:#888;font-weight:400">'
        f'— {asset_name}</span>',
        unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S1 — CONTRACT PARAMETERS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Contract Parameters")
    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:{C1};">Production & Tenor</div>',
                    unsafe_allow_html=True)
        _prod_def = max(1.0, min(float(asset_ann["prod_gwh"].mean()) if has_asset else 52.0, 50000.0))
        prod_p50 = st.number_input("P50 production (GWh/yr)", 1.0, 50000.0, _prod_def,
                                   step=0.5, key="pr_prod_p50",
                                   help="Annual P50e — volume hedged in CAL at signature.")
        vol_stress_pct = st.slider("Production variance (% of P50)", 0, 30, 12,
                                   key="pr_vol_stress",
                                   help="Interannual solar variance. Typical FR: 10-15%.")
        tenor_yr    = st.slider("Tenor (years)", 1, 15, 5, key="pr_tenor")
        forward_eur = st.number_input("Baseload forward (EUR/MWh)", 20.0, 200.0,
                                      float(DEFAULT_FWD.get(2026, 55.0)), step=0.5, key="pr_fwd")
        chosen_pct  = st.slider("Cannibalization percentile for pricing", 1, 100, 74,
                                key="pr_pct",
                                help="P74 = WPD reference. Higher = more conservative.")

    with c_right:
        st.markdown(f'<div style="font-size:12px;font-weight:700;color:{C1};">Premiums & Risk</div>',
                    unsafe_allow_html=True)
        imb_forfait = st.number_input("Imbalance forfait (EUR/MWh)", 0.0, 10.0, 1.9,
                                      step=0.1, key="pr_imb",
                                      help="Contractual fixed imbalance cost. WPD ref: 1.9 EUR/MWh.")
        imb_rate    = st.number_input("Imbalance rate (% of production)", 0.5, 15.0, 3.0,
                                      step=0.5, key="pr_imb_rate",
                                      help="% of production going to imbalance. Typical: 2-5%.") / 100
        imb_stress  = st.slider("Imbalance forfait stress (±%)", -30, 30, 0,
                                key="pr_imb_stress",
                                help="+20% = real settlement 20% above forfait.") / 100
        da_deboucle = st.slider("DA deboucle discount vs forward (%)", 0, 40, 20,
                                key="pr_da_disc",
                                help="Solar peak hours: DA depressed vs forward. Typical: 15-25%.") / 100
        add_disc    = st.number_input("Additional discount (%)", 0.0, 10.0, 0.0,
                                      step=0.25, key="pr_add_disc") / 100
        goo_val     = st.number_input("GoO value (EUR/MWh)", 0.0, 10.0, 1.0,
                                      step=0.1, key="pr_goo")
        margin      = st.number_input("Margin (EUR/MWh)", 0.0, 10.0, 1.0,
                                      step=0.1, key="pr_margin")

    prod_mwh = prod_p50 * 1000

    # ═══════════════════════════════════════════════════════════════════════════
    # S2 — NATIONAL vs ASSET TOGGLE
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Analysis Basis — National vs Asset")

    # Build asset shape discount series from asset_ann if available
    if has_asset and asset_ann is not None and len(asset_ann) >= 2:
        _asset_sd_f = asset_ann["shape_disc"].dropna()
        _has_asset_sd = len(_asset_sd_f) >= 2
    else:
        _asset_sd_f  = pd.Series(dtype=float)
        _has_asset_sd = False

    _basis_opts = ["National"]
    if _has_asset_sd:
        _basis_opts.append("Asset")
        _basis_opts.append("Both (side-by-side)")

    analysis_basis = st.radio(
        "Compute shape discount from:",
        _basis_opts, horizontal=True, key="pr_basis",
        help=(
            "National = ENTSO-E France national solar captured price. "
            "Asset = uploaded load curve crossed with spot prices. "
            "Both = side-by-side comparison."
        ))

    # Determine sd_series to use for pricing and static charts
    if analysis_basis == "Asset" and _has_asset_sd:
        sd_series_pricing = _asset_sd_f
        label_pricing     = asset_name
    else:
        sd_series_pricing = hist_sd_f
        label_pricing     = "National"

    # Side-by-side comparison table
    if analysis_basis == "Both (side-by-side)" and _has_asset_sd:
        desc("Comparison of shape discount distribution: National vs Asset historical data.")
        _cmp_rows = []
        for p in [10, 25, 50, 74, 75, 90]:
            _sdn = float(np.percentile(hist_sd_f,     p)) if len(hist_sd_f) > 0    else float("nan")
            _sda = float(np.percentile(_asset_sd_f,   p)) if len(_asset_sd_f) > 0  else float("nan")
            _cmp_rows.append({
                "Percentile":         f"P{p}",
                "Shape Disc National": f"{_sdn*100:.1f}%",
                "CP% National":        f"{(1-_sdn)*100:.1f}%",
                "Captured Nat (EUR)":  f"{forward_eur*(1-_sdn):.2f}",
                "Shape Disc Asset":    f"{_sda*100:.1f}%",
                "CP% Asset":           f"{(1-_sda)*100:.1f}%",
                "Captured Asset (EUR)":f"{forward_eur*(1-_sda):.2f}",
                "Δ Shape Disc":        f"{(_sda-_sdn)*100:+.1f}pp",
            })
        _cmp_df = pd.DataFrame(_cmp_rows)
        def _hi_cmp(row):
            if row["Percentile"] == f"P{chosen_pct}":
                return [f"background-color:{C2};color:{WHT};font-weight:bold"] * len(row)
            if row["Percentile"] == "P74":
                return [f"background-color:{C3L}"] * len(row)
            return [""] * len(row)
        st.dataframe(_cmp_df.style.apply(_hi_cmp, axis=1),
                     use_container_width=True, hide_index=True)
    else:
        _n_yrs = len(sd_series_pricing)
        _sd_p50 = float(np.percentile(sd_series_pricing, 50)) if _n_yrs > 0 else 0.15
        desc(
            f"Using **{label_pricing}** shape discount distribution "
            f"({_n_yrs} historical years). "
            f"P50 = {_sd_p50*100:.1f}% | "
            f"P74 = {float(np.percentile(sd_series_pricing,74))*100:.1f}%."
        )

    # Final sd values for pricing
    sd_chosen = float(np.percentile(sd_series_pricing, chosen_pct)) if len(sd_series_pricing) > 0 else 0.15
    sd_p10    = float(np.percentile(sd_series_pricing, 10))         if len(sd_series_pricing) > 0 else 0.08
    sd_p50    = float(np.percentile(sd_series_pricing, 50))         if len(sd_series_pricing) > 0 else 0.15
    sd_p90    = float(np.percentile(sd_series_pricing, 90))         if len(sd_series_pricing) > 0 else 0.25

    # ═══════════════════════════════════════════════════════════════════════════
    # S3 — PPA PRICE OUTPUT
    # ═══════════════════════════════════════════════════════════════════════════
    pricing    = compute_ppa(forward_eur, sd_chosen, imb_forfait, add_disc,
                             goo_value=goo_val, margin=margin)
    ppa        = pricing["ppa"]
    multiplier = pricing["multiplier"]
    formula_str = f"{multiplier:.4f} × CAL − {imb_forfait:.1f}"

    st.markdown("---")
    section("PPA Price — Output")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(_kpi("PPA Price", f"{ppa:.2f} EUR/MWh", C1, WHT), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi("Multiplier", f"{multiplier:.4f}", C2, WHT), unsafe_allow_html=True)
    with k3:
        sd_d = sd_chosen * 100
        c_sd = C5 if sd_d > 25 else C3 if sd_d > 15 else C2
        t_sd = WHT if sd_d > 25 or sd_d <= 15 else C1
        st.markdown(_kpi(f"Shape Disc P{chosen_pct}", f"{sd_d:.1f}%", c_sd, t_sd),
                    unsafe_allow_html=True)
    with k4:
        cp_input = forward_eur * (1 - sd_chosen)
        st.markdown(_kpi("Capture Price", f"{cp_input:.2f} EUR/MWh", C2L, C1, border=C2),
                    unsafe_allow_html=True)
    with k5:
        st.markdown(_kpi("Indexed Formula", formula_str, C3, C1), unsafe_allow_html=True)

    st.markdown(
        f'<div style="background:{C3L};border-left:4px solid {C3};padding:10px 16px;'
        f'border-radius:0 6px 6px 0;margin:12px 0;font-family:Calibri,Arial;'
        f'font-size:13px;color:{C1};">'
        f'<b>P{chosen_pct}</b> = {chosen_pct}th percentile of {label_pricing} '
        f'historical shape discount ({len(sd_series_pricing)} years). '
        f'Capture price: <b>{cp_input:.2f} EUR/MWh</b> '
        f'({(1-sd_chosen)*100:.1f}% of {forward_eur:.0f} EUR forward).'
        f'</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S4 — P&L vs CANNIBALIZATION CURVE
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section(f"P&L vs Cannibalization Percentile — {label_pricing}")
    desc(
        "Annual P&L decomposed into 3 components: "
        "[1] Hedged P&L (captured price − PPA) × volume, "
        "[2] Merchant P&L (over/under-production deboucled in DA), "
        "[3] Imbalance cost (fixed forfait). "
        "Vertical line = chosen percentile. Red line = break-even."
    )

    fig_pnl, be_pct, chosen_pnl = _chart_pnl_curve(
        forward_eur, ppa, prod_mwh, sd_series_pricing, chosen_pct,
        da_deboucle, imb_rate, imb_forfait, imb_stress, label_pricing, plotly_base)
    st.plotly_chart(fig_pnl, use_container_width=True)

    if be_pct:
        c_be = C5 if be_pct < chosen_pct else C3
        t_be = WHT if be_pct < chosen_pct else C1
        st.markdown(
            f'<div style="background:{c_be};color:{t_be};padding:10px 16px;'
            f'border-radius:6px;font-family:Calibri,Arial;font-size:13px;font-weight:600;">'
            f'Break-even at P{be_pct}. '
            f'{"WARNING: chosen P" + str(chosen_pct) + " is above break-even — position at risk." if chosen_pct > be_pct else "Chosen P" + str(chosen_pct) + " is within profitable range."}'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="background:{C2};color:{WHT};padding:10px 16px;border-radius:6px;'
            f'font-family:Calibri,Arial;font-size:13px;font-weight:600;">'
            f'No break-even in historical range — position profitable across all observed scenarios.'
            f'</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S5 — RISK HEATMAP
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section("Risk Heatmap — Forward Price × Cannibalization → Annual P&L")
    desc(
        "Each cell = annual P&L (kEUR) for a given (forward, shape discount) pair. "
        "Green = profit, red = loss. Cross = current inputs. "
        "Read: how far can forward fall or cannibalization rise before break-even?"
    )

    fwd_range  = [round(f, 1) for f in
                  np.arange(max(20.0, forward_eur-20), min(150.0, forward_eur+21), 5.0)]
    cann_range = [round(c, 3) for c in
                  np.arange(max(0.0, sd_chosen-0.20), min(0.70, sd_chosen+0.21), 0.05)]

    fig_hm = _chart_heatmap(fwd_range, cann_range, prod_mwh, ppa,
                             da_deboucle, imb_rate, imb_forfait, imb_stress,
                             forward_eur, sd_chosen, plotly_base)
    st.plotly_chart(fig_hm, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S6 — MONTE CARLO
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section(f"Monte Carlo — P&L Simulation over {tenor_yr}-Year Tenor")
    desc(
        "Cannibalization level from regression trend (same as Tab 1 projection). "
        "Intra-year variance from historical std. "
        "3 independent risk drivers: cannibalization, production, forward price."
    )

    _mc_dist = st.session_state.get("mc_dist", None)

    # Parameters row
    mc_p1, mc_p2, mc_p3, mc_p4, mc_p5 = st.columns([1, 1, 1, 1, 1])
    with mc_p1:
        vol_std_mc = st.slider("Production std (%)", 5, 30, 12, key="mc_vol_std",
                               help="Interannual solar variance. Typical: 10-15%.") / 100
    with mc_p2:
        fwd_std_mc = st.slider("Forward price std (%)", 2, 25, 10, key="mc_fwd_std",
                               help="Annual forward uncertainty.") / 100
    with mc_p3:
        n_sim_mc = st.select_slider("Simulations", options=[1_000, 5_000, 10_000, 20_000],
                                    value=10_000, key="mc_nsim")
    with mc_p4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        run_mc = st.button("▶ Run Monte Carlo", key="mc_run")
    with mc_p5:
        if _mc_dist is not None:
            _sig = _mc_dist["sigma_cannib"]
            st.markdown(
                f'<div style="font-size:11px;color:{C1};background:{C2L};'
                f'border-left:3px solid {C2};padding:6px 10px;border-radius:4px;">'
                f'σ cannib: ±{_sig*100:.1f}pp<br>'
                f'{_mc_dist["n_sim"]:,} trajectories<br>'
                f'Basis: {label_pricing}'
                f'</div>', unsafe_allow_html=True)

    if run_mc:
        if not _MC_OK:
            st.error("montecarlo.py not found in ppa_dashboard/.")
        else:
            _last_yr_mc = (
                int(asset_ann["Year"].max()) if has_asset
                else (int(nat_ref_complete["year"].max())
                      if len(nat_ref_complete) > 0 else 2025))
            with st.spinner(f"Simulating {n_sim_mc:,} trajectories..."):
                try:
                    _mc_result = run_montecarlo(
                        ppa=ppa, forward_eur=forward_eur,
                        prod_p50_mwh=prod_mwh, sl_u=sl_u, ic_u=ic_u,
                        last_yr=_last_yr_mc, tenor=tenor_yr,
                        hist_sd_f=sd_series_pricing,
                        vol_std=vol_std_mc, fwd_std=fwd_std_mc,
                        imb_rate=imb_rate, imb_forfait=imb_forfait,
                        n_sim=n_sim_mc)
                    st.session_state["mc_dist"] = _mc_result
                    _mc_dist = _mc_result
                except Exception as _e:
                    st.error(f"Monte Carlo failed: {_e}")

    if _mc_dist is None:
        st.info("Click **▶ Run Monte Carlo** to simulate contract trajectories.")
    else:
        _p10c  = _mc_dist["percentiles_cumul"][10]
        _p50c  = _mc_dist["percentiles_cumul"][50]
        _p90c  = _mc_dist["percentiles_cumul"][90]
        _ploss = _mc_dist["prob_loss"] * 100
        _es    = _mc_dist["expected_shortfall"]

        # KPI strip
        ka, kb, kc, kd, ke = st.columns(5)
        with ka:
            _bg, _tx = _pnl_color(_p10c)
            st.markdown(_kpi("P10 Cumul P&L", _fmt_k(_p10c), _bg, _tx), unsafe_allow_html=True)
        with kb:
            _bg, _tx = _pnl_color(_p50c)
            st.markdown(_kpi("P50 Cumul P&L", _fmt_k(_p50c), _bg, _tx), unsafe_allow_html=True)
        with kc:
            _bg, _tx = _pnl_color(_p90c)
            st.markdown(_kpi("P90 Cumul P&L", _fmt_k(_p90c), _bg, _tx), unsafe_allow_html=True)
        with kd:
            _c = C5 if _ploss > 20 else C3 if _ploss > 10 else C2
            _t = WHT if _ploss > 20 or _ploss <= 10 else C1
            st.markdown(_kpi("Prob. of Loss", f"{_ploss:.1f}%", _c, _t), unsafe_allow_html=True)
        with ke:
            _bg, _tx = _pnl_color(_es)
            st.markdown(_kpi("Expected Shortfall", _fmt_k(_es), _bg, _tx), unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # Chart A — Cumulative P&L distribution
        _cum_arr = _mc_dist["cumul_pnl"]
        _fig_hist = go.Figure()
        _fig_hist.add_trace(go.Histogram(
            x=_cum_arr, nbinsx=100,
            marker_color="rgba(42,157,143,0.50)",
            marker_line_color=C2, marker_line_width=0.3,
            hovertemplate="P&L: %{x:.0f}k EUR<br>Frequency: %{y}<extra></extra>"))
        if float(_cum_arr.min()) < 0:
            _fig_hist.add_vrect(
                x0=float(_cum_arr.min()), x1=0,
                fillcolor="rgba(231,111,81,0.10)", line_width=0,
                annotation_text="Loss zone",
                annotation_position="top left",
                annotation_font=dict(size=10, color=C5, family="Calibri,Arial"))
        for _pv, _pl, _pc in [(_p10c,"P10",C5),(_p50c,"P50",C1),(_p90c,"P90",C2)]:
            _fig_hist.add_vline(x=_pv, line_width=2, line_color=_pc, line_dash="dot",
                annotation_text=f"  {_pl}: {_pv:+.0f}k",
                annotation_position="top right",
                annotation_font=dict(size=11, color=_pc, family="Calibri,Arial"))
        _fig_hist.add_vline(x=0, line_width=1.5, line_color=C5)
        _fig_hist.update_layout(
            title=dict(text=f"<b>Cumulative P&L Distribution — {tenor_yr}-Year Tenor</b>",
                       font=dict(size=13, color=C1, family="Calibri,Arial"),
                       x=0.5, xanchor="center"),
            height=280, margin=dict(l=50, r=20, t=50, b=50),
            plot_bgcolor=WHT, paper_bgcolor=WHT,
            xaxis=dict(title=f"Cumulative P&L over {tenor_yr}yr (k EUR)",
                       gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=11)),
            yaxis=dict(title="Frequency", gridcolor="#eee",
                       tickfont=dict(family="Calibri,Arial", size=11)),
            showlegend=False, bargap=0.02)
        plotly_base(_fig_hist, h=280, show_legend=False)
        st.plotly_chart(_fig_hist, use_container_width=True)

        # Charts B + C + D — three fan charts side by side
        _years  = _mc_dist["years"]
        _bands  = _mc_dist["percentile_bands"]
        _sd_b   = _mc_dist["sd_percentile_bands"]
        _cp_b   = _mc_dist["cp_percentile_bands"]
        _trend  = _mc_dist["pnl_trend"]
        _sd_tr  = _mc_dist["sd_trend"]
        _cp_tr  = _mc_dist["cp_trend"]

        ch1, ch2, ch3 = st.columns(3)

        with ch1:
            fig_fan_pnl = _fan_chart(
                _years, _bands, _trend,
                y_title="Annual P&L (k EUR)",
                title="Annual P&L — Fan Chart",
                color=C2, suffix="", plotly_base=plotly_base)
            st.plotly_chart(fig_fan_pnl, use_container_width=True)

        with ch2:
            fig_fan_sd = _fan_chart(
                _years,
                {p: [v*100 for v in _sd_b[p]] for p in _sd_b},
                [v*100 for v in _sd_tr],
                y_title="Shape Discount (%)",
                title="Shape Discount — Cannibalization Fan Chart",
                color=C5, suffix="%", plotly_base=plotly_base)
            st.plotly_chart(fig_fan_sd, use_container_width=True)

        with ch3:
            fig_fan_cp = _fan_chart(
                _years,
                _cp_b,
                _cp_tr,
                y_title="Capture Price (EUR/MWh)",
                title="Capture Price — Fan Chart",
                color=C2, suffix="", plotly_base=plotly_base)
            st.plotly_chart(fig_fan_cp, use_container_width=True)

        # ═══════════════════════════════════════════════════════════════════════
        # S7 — DECISION TABLE
        # ═══════════════════════════════════════════════════════════════════════
        st.markdown("---")
        section("Decision Table — Annual P&L, Shape Discount & Risk")
        desc(
            "Year-by-year summary from Monte Carlo. "
            "SD trend = regression projection. P50/P10/P90 = simulation outcomes. "
            "Downside = P10 − P50. Upside = P90 − P50."
        )

        _sc_df = pd.DataFrame(_mc_dist["scenario_table"])

        def _style_decision(row):
            try:
                val = float(row["P&L P50 (kEUR)"].replace("k","").replace("+",""))
            except Exception:
                val = 0
            _bg, _tx = _pnl_color(val)
            base = [""] * len(row)
            idx  = _sc_df.columns.get_loc("P&L P50 (kEUR)")
            base[idx] = f"background-color:{_bg};color:{_tx};font-weight:700"
            return base

        st.dataframe(_sc_df.style.apply(_style_decision, axis=1),
                     use_container_width=True, hide_index=True)

        # Cumulative summary row
        _cs = _mc_dist["cumul_summary"]
        st.markdown(
            f'<div style="background:{C1};color:{WHT};padding:12px 20px;'
            f'margin-top:8px;border-radius:6px;font-family:Calibri,Arial;font-size:13px;">'
            f'<b>{tenor_yr}-year cumulative:</b> &nbsp;'
            f'P50 = {_cs["P50 cumul (kEUR)"]} &nbsp;|&nbsp; '
            f'P10 = {_cs["P10 cumul (kEUR)"]} &nbsp;|&nbsp; '
            f'P90 = {_cs["P90 cumul (kEUR)"]} &nbsp;|&nbsp; '
            f'Prob. loss = {_cs["Prob. of loss"]} &nbsp;|&nbsp; '
            f'Downside = {_cs["Downside (P10-P50)"]} &nbsp;|&nbsp; '
            f'Upside = {_cs["Upside (P90-P50)"]}'
            f'</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # S8 — ANNUAL DETERMINISTIC PROJECTION
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    section(f"Annual P&L Projection — Deterministic ({tenor_yr}-Year Tenor)")
    desc(
        "Deterministic projection using regression trend for shape discount. "
        "No noise — pure trend. "
        "Shows whether the contract holds over the full tenor at the chosen percentile offset."
    )

    _last_yr_proj = (
        int(asset_ann["Year"].max()) if has_asset
        else (int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else 2025))
    proj_df   = project_cp(sl_u, ic_u, _last_yr_proj, tenor_yr, anchor_val=None)
    sd_offset = sd_chosen - sd_p50

    ann_rows = []
    for _, row in proj_df.iterrows():
        yr     = int(row["year"])
        fsd_yr = max(0.0, (1 - row["p50"]) + sd_offset)
        r = _pnl_components(prod_mwh, ppa, forward_eur, fsd_yr,
                            da_deboucle, imb_rate, imb_forfait, imb_stress)
        ann_rows.append({
            "Year":                   yr,
            "Shape Disc (trend+offset)": f"{fsd_yr*100:.1f}%",
            "Capture Price (EUR/MWh)":   f"{r['cp']:.2f}",
            "PPA (EUR/MWh)":             f"{ppa:.2f}",
            "[1] Hedged (kEUR)":         _fmt_k(r["p1"]),
            "[2] Merchant (kEUR)":       _fmt_k(r["p2"]),
            "[3] Imbalance (kEUR)":      _fmt_k(r["p3"]),
            "Total P&L (kEUR)":          _fmt_k(r["total"]),
        })

    adf = pd.DataFrame(ann_rows)

    def _style_ann(row):
        idx = adf.columns.get_loc("Total P&L (kEUR)")
        try:
            val = float(row["Total P&L (kEUR)"].replace("k","").replace("+",""))
        except Exception:
            val = 0
        _bg, _tx = _pnl_color(val)
        base = [""] * len(row)
        base[idx] = f"background-color:{_bg};color:{_tx};font-weight:700"
        return base

    st.dataframe(adf.style.apply(_style_ann, axis=1),
                 use_container_width=True, hide_index=True)

    cumul = sum(float(r["Total P&L (kEUR)"].replace("k","").replace("+",""))
                for r in ann_rows)
    c_cum = C2 if cumul > 0 else C5
    st.markdown(
        f'<div style="background:{c_cum};color:{WHT};padding:12px 20px;margin-top:8px;'
        f'border-radius:6px;font-family:Calibri,Arial;font-size:14px;font-weight:700;">'
        f'Cumulative P&L over {tenor_yr} years at P{chosen_pct} ({label_pricing}): '
        f'{cumul:+.0f}k EUR'
        f'</div>', unsafe_allow_html=True)
