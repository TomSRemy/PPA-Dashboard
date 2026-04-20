"""
app.py — KAL-EL PPA Dashboard v2.7
Thin orchestrator: config, sidebar, data loading, compute, tab dispatch.
All tab UI logic is in tab_*.py files.
All colors and sizes are in theme.py.
"""

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(
    page_title="PPA Pricing Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

from config  import get_css, TECH_CONFIG, DEFAULT_FWD, EXAMPLE_CSV
from theme   import C1, C2, C3, C4, C5, C2L, C3L, WHT, set_mode
from data    import (load_nat, load_hourly, load_log, wind_available,
                     compute_rolling_m0, nat_series, get_nat_sd,
                     load_balancing, load_market_prices, load_xborder_da, load_fcr)
from compute import (compute_asset_annual, fit_reg, project_cp,
                     compute_ppa, compute_pnl_curve, compute_scenarios)
from charts  import chart_scatter_cp_vs_capacity, MK_ZOOM_OPTS, MK_PURPLE, MK_BLUE, MK_GREEN
from ui      import section, desc, status_msg, ppa_card, kpi_card, tech_badge, plotly_base
from excel   import build_excel

from tab_pricer          import render_pricer_tab
from tab_fpc             import render_fpc_tab
from tab_overview        import render_tab_overview
from tab_ppa_pricing     import render_tab_ppa_pricing
from tab_market_dynamics import render_tab_market_dynamics
from tab_market_evolution import render_tab_market_evolution
from tab_market_overview import render_tab_market_overview
from tab_export          import render_tab_export

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### KAL-EL Dashboard")
    st.markdown(f'<div class="update-pill">{load_log().split(chr(10))[0]}</div>',
                unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### Display")
    dark_mode = st.toggle("🌙 Dark mode", value=False, key="dark_mode")

    st.markdown("---")
    st.markdown("### Technology")
    techno = st.selectbox("Select technology", ["Solar","Wind"], index=0,
                          label_visibility="collapsed")
    cfg = TECH_CONFIG[techno]

    st.markdown("---")
    st.markdown("### Market Settings")
    n_reg = st.slider("Regression Years", 2, 12, 3)
    ex22  = st.toggle("Exclude 2022", value=False)

    _hourly_full = load_hourly()
    _yr_min = int(_hourly_full["Year"].min())
    _yr_max = int(_hourly_full["Year"].max())
    yr_range = st.slider("Year range", _yr_min, _yr_max, (_yr_min, _yr_max), key="yr_range")

    st.markdown("---")
    st.markdown("### Pricing Tenor")
    _nat_tmp = load_nat()
    _last_yr = int(_nat_tmp[_nat_tmp["partial"] == False]["year"].max())
    tenor_start = st.number_input("Tenor start (year)", min_value=_last_yr+1, max_value=_last_yr+20,
                                   value=_last_yr+1, step=1, key="tenor_start")
    tenor_end   = st.number_input("Tenor end (year)",   min_value=_last_yr+1, max_value=_last_yr+20,
                                   value=_last_yr+5, step=1, key="tenor_end")

    st.markdown("---")
    st.markdown("### Sensitivity Analysis")
    chosen_pct  = st.slider("Selected Percentile", 1, 100, 74)
    proj_n      = st.slider("Projection Horizon (years)", 1, 10, 5)
    vol_stress  = st.slider("Volume Stress (+/-%%)", 0, 30, 20)
    spot_stress = st.slider("Spot Stress (+/-%%)", 0, 30, 20)

    st.markdown("---")
    st.markdown("### Projection Settings")
    reg_basis = st.radio("Regression basis", ["Asset","National"], horizontal=True,
                         key="reg_basis", help="Which slope to use for CP% projection")

    st.markdown("---")
    st.markdown(f"### {cfg['label']} Asset Upload")
    uploaded = st.file_uploader("", type=["xlsx","csv"], label_visibility="hidden")
    st.caption("Columns: Date | Prod_MWh")
    st.download_button("Download example", data=EXAMPLE_CSV.encode("utf-8"),
                       file_name="example_load_curve.csv", mime="text/csv", key="dl_example")

    sb_date_col = None; sb_prod_col = None; sb_unit = "MWh"
    if uploaded:
        try:
            _raw  = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
            _cols = _raw.columns.tolist()
            sb_date_col = st.selectbox("Date column", _cols,
                index=next((i for i,c in enumerate(_cols) if "date" in c.lower()), 0),
                key="sb_date_col")
            sb_prod_col = st.selectbox("Production column", _cols,
                index=next((i for i,c in enumerate(_cols)
                            if any(k in c.lower() for k in ["prod","mwh","actual","gen","kwh"])),
                           min(1, len(_cols)-1)),
                key="sb_prod_col")
            sb_unit = st.radio("Unit", ["MWh","kWh"], horizontal=True, key="sb_unit")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.markdown("---")
    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.rerun()

# ── Apply theme mode ─────────────────────────────────────────────────────────
import theme as _theme
_dark = st.session_state.get("dark_mode", False)
set_mode(dark=_dark)
# Reload config vars after set_mode (they're module-level, re-import needed)
from config import get_css, TECH_CONFIG, DEFAULT_FWD, EXAMPLE_CSV
from theme import C1, C2, C3, C4, C5, C2L, C3L, WHT
st.markdown(get_css(), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE — PPA premiums
# ══════════════════════════════════════════════════════════════════════════════
defaults = {"imb_eur": 1.9, "add_disc": 0.0, "vol_risk_pct": 0.0,
            "price_risk_pct": 0.0, "goo_value": 1.0, "margin": 1.0}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

imb_eur        = float(st.session_state.imb_eur)
add_disc       = float(st.session_state.add_disc) / 100
vol_risk_pct   = float(st.session_state.vol_risk_pct) / 100
price_risk_pct = float(st.session_state.price_risk_pct) / 100
goo_value      = float(st.session_state.goo_value)
margin         = float(st.session_state.margin)

# ══════════════════════════════════════════════════════════════════════════════
# DATA & COMPUTE
# ══════════════════════════════════════════════════════════════════════════════
nat_ref = load_nat()
hourly  = load_hourly()
hourly  = hourly[hourly["Year"].between(yr_range[0], yr_range[1])]

data_end      = pd.to_datetime(hourly["Date"]).max()
data_start    = pd.to_datetime(hourly["Date"]).min()
current_year  = pd.Timestamp.now().year
partial_years = nat_ref[nat_ref["partial"] == True]["year"].tolist() if "partial" in nat_ref.columns else []
has_wind      = wind_available(hourly)

# Asset upload
asset_ann = None; asset_name = cfg["label"] + " Asset"; asset_raw = None
if uploaded and sb_date_col and sb_prod_col:
    try:
        raw = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        raw[sb_date_col] = pd.to_datetime(raw[sb_date_col], errors="coerce")
        raw[sb_prod_col] = (raw[sb_prod_col].astype(str)
                            .str.replace(" ","").str.replace("-","0").str.replace(",","."))
        raw[sb_prod_col] = pd.to_numeric(raw[sb_prod_col], errors="coerce").fillna(0.0)
        if sb_unit == "kWh":
            raw[sb_prod_col] = raw[sb_prod_col] / 1000
        asset_raw = raw[[sb_date_col, sb_prod_col]].rename(
            columns={sb_date_col:"Date", sb_prod_col:"Prod_MWh"})
        asset_ann  = compute_asset_annual(hourly, asset_raw.copy(), prod_col=cfg["prod_col"])
        asset_name = uploaded.name.rsplit(".",1)[0]
        st.sidebar.success(f"Loaded: {asset_name}")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

has_asset = asset_ann is not None and len(asset_ann) >= 2

nat_ref_complete = nat_ref[nat_ref["partial"] == False] if "partial" in nat_ref.columns else nat_ref
nat_ref          = nat_ref[nat_ref["year"].between(yr_range[0], yr_range[1])]
nat_ref_complete = nat_ref_complete[nat_ref_complete["year"].between(yr_range[0], yr_range[1])]

# Regression
work_nat = nat_ref.rename(columns={"year":"Year"}).copy()
work_nat["shape_disc"] = work_nat[cfg["nat_sd"]].fillna(work_nat["shape_disc"])
sl_nat,  ic_nat,  r2_nat  = fit_reg(work_nat, n_reg, False)
sl_nat2, ic_nat2, r2_nat2 = fit_reg(work_nat, n_reg, True)
sl_nat_u = sl_nat2 if ex22 else sl_nat
ic_nat_u = ic_nat2 if ex22 else ic_nat

sl_ast = sl_nat_u; ic_ast = ic_nat_u; r2_ast = r2_nat2 if ex22 else r2_nat
if has_asset:
    sl_ast,  ic_ast,  r2_ast  = fit_reg(asset_ann, n_reg, False)
    sl_ast2, ic_ast2, r2_ast2 = fit_reg(asset_ann, n_reg, True)
    sl_ast = sl_ast2 if ex22 else sl_ast
    ic_ast = ic_ast2 if ex22 else ic_ast
    r2_ast = r2_ast2 if ex22 else r2_ast

sl_u, ic_u, r2_u = (sl_ast, ic_ast, r2_ast) if (reg_basis == "Asset" and has_asset) \
                   else (sl_nat_u, ic_nat_u, r2_nat2 if ex22 else r2_nat)

last_yr_complete = int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else int(nat_ref["year"].max())
last_yr_proj     = int(asset_ann["Year"].max()) if has_asset else last_yr_complete
anchor_val       = asset_ann["cp_pct"].iloc[-1] if has_asset else None

hist_sd   = (asset_ann["shape_disc"].dropna() if has_asset
             else get_nat_sd(nat_ref_complete, cfg["nat_sd"]))
nc_ex22   = nat_ref_complete[nat_ref_complete["year"] != 2022] if ex22 else nat_ref_complete
hist_sd_f = (asset_ann[asset_ann["Year"] != 2022]["shape_disc"].dropna() if (has_asset and ex22)
             else asset_ann["shape_disc"].dropna() if has_asset
             else get_nat_sd(nc_ex22, cfg["nat_sd"]))
if len(hist_sd_f) == 0:
    hist_sd_f = nat_ref_complete["shape_disc"].dropna()

sd_ch   = float(np.percentile(hist_sd_f, chosen_pct)) if len(hist_sd_f) > 0 else 0.15
vol_mwh = asset_ann["prod_mwh"].mean() if has_asset else 52000.0
proj    = project_cp(sl_u, ic_u, last_yr_proj, proj_n, anchor_val=anchor_val)

fwd_df    = pd.DataFrame([{"year": yr, "forward": float(DEFAULT_FWD.get(yr, 52.0))}
                          for yr in range(tenor_start, tenor_end + 1)])
fwd_curve = dict(zip(fwd_df["year"], fwd_df["forward"]))
ref_fwd   = fwd_df["forward"].mean() if len(fwd_df) > 0 else 55.0

pricing = compute_ppa(ref_fwd, sd_ch, imb_eur, add_disc)
ppa     = pricing["ppa"]

pcts    = list(range(1, 101))
sd_vals = [float(np.percentile(hist_sd_f, p)) if len(hist_sd_f) > 0 else 0.15 for p in pcts]
pnl_v   = compute_pnl_curve(ref_fwd, ppa, vol_mwh, sd_vals)
be      = next((p for p, v in zip(pcts, pnl_v) if v < 0), None)

scenarios = compute_scenarios(ref_fwd, ppa, vol_mwh, hist_sd_f, proj_n, vol_stress, spot_stress)

nat_cp_list      = nat_series(nat_ref,          cfg["nat_cp"],  "cp_nat_pct")
nat_eur_list     = nat_series(nat_ref,          cfg["nat_eur"], "cp_nat")
nat_cp_complete  = nat_series(nat_ref_complete, cfg["nat_cp"],  "cp_nat_pct")
nat_eur_complete = nat_series(nat_ref_complete, cfg["nat_eur"], "cp_nat")

wind_ready    = techno == "Wind" and has_wind
prod_col_roll = cfg["prod_col"] if (techno == "Solar" or wind_ready) else "NatMW"

fig_cap_link, proj_targets = chart_scatter_cp_vs_capacity(
    nat_ref, hourly, cfg["prod_col"], cfg["nat_cp"],
    cfg["color"], cfg["label"], partial_years, techno == "Solar", ex22=ex22)

# ══════════════════════════════════════════════════════════════════════════════
# SHARED CONTEXT — passed to all tab render functions
# ══════════════════════════════════════════════════════════════════════════════
ctx = dict(
    # data
    nat_ref=nat_ref, nat_ref_complete=nat_ref_complete,
    hourly=hourly, asset_ann=asset_ann, asset_raw=asset_raw,
    # flags
    has_asset=has_asset, has_wind=has_wind, wind_ready=wind_ready,
    # tech
    techno=techno, cfg=cfg, asset_name=asset_name,
    # regression
    sl_u=sl_u, ic_u=ic_u, r2_u=r2_u, reg_basis=reg_basis,
    sl_nat_u=sl_nat_u, ic_nat_u=ic_nat_u,
    # pricing
    ppa=ppa, pricing=pricing, ref_fwd=ref_fwd, sd_ch=sd_ch,
    imb_eur=imb_eur, add_disc=add_disc, vol_risk_pct=vol_risk_pct,
    price_risk_pct=price_risk_pct, goo_value=goo_value, margin=margin,
    # series
    nat_cp_list=nat_cp_list, nat_eur_list=nat_eur_list,
    nat_cp_complete=nat_cp_complete, nat_eur_complete=nat_eur_complete,
    hist_sd_f=hist_sd_f, sd_vals=sd_vals, pnl_v=pnl_v, scenarios=scenarios,
    # projections
    proj=proj, proj_n=proj_n, last_yr_proj=last_yr_proj, anchor_val=anchor_val,
    # params
    chosen_pct=chosen_pct, vol_stress=vol_stress, spot_stress=spot_stress,
    partial_years=partial_years, current_year=current_year,
    data_start=data_start, data_end=data_end,
    tenor_start=tenor_start, tenor_end=tenor_end,
    fwd_df=fwd_df, fwd_curve=fwd_curve,
    # pre-computed charts
    fig_cap_link=fig_cap_link, proj_targets=proj_targets,
    vol_mwh=vol_mwh, be=be, prod_col_roll=prod_col_roll,
    # UI helpers
    plotly_base=plotly_base,
    # market data loaders (lazy — only used in tab 6)
    _load_balancing=load_balancing,
    _load_market_prices=load_market_prices,
    _load_xborder_da=load_xborder_da,
    _load_fcr=load_fcr,
    _load_hourly=load_hourly,
    # export helpers
    _get_nat_sd=get_nat_sd,
    _build_excel=build_excel,
)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Overview", "PPA Pricing", "Market Dynamics",
    "Market Evolution", "Pricing & Risk", "Market Overview", "Export",
    "FPC Monte Carlo",
])

with tab1: render_tab_overview(ctx)
with tab2: render_tab_ppa_pricing(ctx)
with tab3: render_tab_market_dynamics(ctx)
with tab4: render_tab_market_evolution(ctx)
with tab5:
    render_pricer_tab(
        hourly=hourly, nat_ref_complete=nat_ref_complete,
        asset_ann=asset_ann, asset_name=asset_name, has_asset=has_asset,
        cfg=cfg, sl_u=sl_u, ic_u=ic_u, hist_sd_f=hist_sd_f,
        plotly_base=plotly_base, asset_raw=asset_raw,
    )
with tab6: render_tab_market_overview(ctx)
with tab7: render_tab_export(ctx)
with tab8:
    render_fpc_tab(
        hourly=hourly, nat_ref_complete=nat_ref_complete,
        asset_ann=asset_ann, asset_raw=asset_raw, has_asset=has_asset,
        asset_name=asset_name, cfg=cfg, sl_u=sl_u, ic_u=ic_u,
        hist_sd_f=hist_sd_f, plotly_base=plotly_base,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
ytd_note = " — 2026 YTD included (excl. regression)" if partial_years else ""
st.markdown(
    f'<span style="font-size:12px;color:#888888;font-family:Calibri,Arial,sans-serif;">'
    f'v2.7 — ENTSO-E France {data_start.year}–{data_end.strftime("%Y-%m-%d")} '
    f'— {len(hourly):,} hours{ytd_note} — Technology: {cfg["label"]} — '
    f'Regression: {reg_basis} — Tenor: {tenor_start}–{tenor_end}'
    f'</span>', unsafe_allow_html=True)
