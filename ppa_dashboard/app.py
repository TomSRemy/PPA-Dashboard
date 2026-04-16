"""
PPA Pricing Dashboard v2.6
Changes v2.6:
- Tab 9 "Market Overview" added: KPIs + FR Spot historical + Generation mix + Nuclear + AI commentary
- update_entsoe.py / update_entsoe_full.py now fetch NuclearMW, GasMW, HydroMW, OtherMW
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

from config  import get_css, TECH_CONFIG, DEFAULT_FWD, C1, C2, C3, C4, C5, C2L, C3L, WHT, EXAMPLE_CSV
from data    import load_nat, load_hourly, load_log, wind_available, compute_rolling_m0, nat_series, get_nat_sd, load_balancing
from compute import compute_asset_annual, fit_reg, project_cp, compute_ppa, compute_pnl_curve, compute_scenarios
from charts  import (
    chart_historical_cp, chart_projection,
    chart_forward,
    chart_neg_hours, chart_monthly_profile, chart_scatter_cp_vs_capacity,
    chart_shape_disc_delta, chart_heatmap,
    chart_market_value_vs_penetration, chart_duck_curve, chart_canyon_curve,
    chart_pnl_percentile, chart_scenarios,
    chart_waterfall,
    chart_rolling_cp, chart_rolling_eur,
    chart_daily_profile_national, chart_daily_profile_asset,
    chart_monthly_production, chart_annual_production,
    chart_last_week, chart_da_monthly, chart_da_heatmap,
    chart_intraday_spread, chart_imbalance_vs_da,
    chart_balancing_services, summary_stats,
)
from ui    import section, desc, status_msg, ppa_card, kpi_card, tech_badge, plotly_base
from excel import build_excel
from tab_pricer import render_pricer_tab
from tab_fpc    import render_fpc_tab
from tab_fpc    import render_fpc_tab

import plotly.graph_objects as go

st.markdown(get_css(), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### KAL-EL Dashboard")
    st.markdown(f'<div class="update-pill">{load_log().split(chr(10))[0]}</div>',
                unsafe_allow_html=True)
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

# ══════════════════════════════════════════════════════════════════════════════
# PPA PREMIUMS — session_state
# ══════════════════════════════════════════════════════════════════════════════
if "imb_eur"        not in st.session_state: st.session_state.imb_eur        = 1.9
if "add_disc"       not in st.session_state: st.session_state.add_disc       = 0.0
if "vol_risk_pct"   not in st.session_state: st.session_state.vol_risk_pct   = 0.0
if "price_risk_pct" not in st.session_state: st.session_state.price_risk_pct = 0.0
if "goo_value"      not in st.session_state: st.session_state.goo_value      = 1.0
if "margin"         not in st.session_state: st.session_state.margin         = 1.0

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
r2_nat_u = r2_nat2 if ex22 else r2_nat

sl_ast = sl_nat_u; ic_ast = ic_nat_u; r2_ast = r2_nat_u
if has_asset:
    sl_ast,  ic_ast,  r2_ast  = fit_reg(asset_ann, n_reg, False)
    sl_ast2, ic_ast2, r2_ast2 = fit_reg(asset_ann, n_reg, True)
    sl_ast = sl_ast2 if ex22 else sl_ast
    ic_ast = ic_ast2 if ex22 else ic_ast
    r2_ast = r2_ast2 if ex22 else r2_ast

if reg_basis == "Asset" and has_asset:
    sl_u, ic_u, r2_u = sl_ast, ic_ast, r2_ast
else:
    sl_u, ic_u, r2_u = sl_nat_u, ic_nat_u, r2_nat_u

last_yr_complete = int(nat_ref_complete["year"].max()) if len(nat_ref_complete)>0 else int(nat_ref["year"].max())
last_yr_proj     = int(asset_ann["Year"].max()) if has_asset else last_yr_complete
anchor_val       = asset_ann["cp_pct"].iloc[-1] if has_asset else None

if has_asset:
    hist_sd   = asset_ann["shape_disc"].dropna()
    hist_sd_f = asset_ann[asset_ann["Year"]!=2022]["shape_disc"].dropna() if ex22 else hist_sd
else:
    hist_sd   = get_nat_sd(nat_ref_complete, cfg["nat_sd"])
    nc_ex22   = nat_ref_complete[nat_ref_complete["year"]!=2022] if ex22 else nat_ref_complete
    hist_sd_f = get_nat_sd(nc_ex22, cfg["nat_sd"])

if len(hist_sd_f) == 0:
    hist_sd_f = nat_ref_complete["shape_disc"].dropna()

sd_ch   = float(np.percentile(hist_sd_f, chosen_pct)) if len(hist_sd_f)>0 else 0.15
vol_mwh = asset_ann["prod_mwh"].mean() if has_asset else 52000.0
proj    = project_cp(sl_u, ic_u, last_yr_proj, proj_n, anchor_val=anchor_val)

fwd_df    = pd.DataFrame([{"year":yr,"forward":float(DEFAULT_FWD.get(yr,52.0))}
                          for yr in range(tenor_start, tenor_end+1)])
fwd_curve = dict(zip(fwd_df["year"], fwd_df["forward"]))
ref_fwd   = fwd_df["forward"].mean() if len(fwd_df)>0 else 55.0

pricing = compute_ppa(ref_fwd, sd_ch, imb_eur, add_disc)
ppa     = pricing["ppa"]

pcts    = list(range(1,101))
sd_vals = [float(np.percentile(hist_sd_f,p)) if len(hist_sd_f)>0 else 0.15 for p in pcts]
cp_vals = [ref_fwd*(1-s) for s in sd_vals]
pnl_v   = compute_pnl_curve(ref_fwd, ppa, vol_mwh, sd_vals)
be      = next((p for p,v in zip(pcts,pnl_v) if v<0), None)

scenarios = compute_scenarios(ref_fwd, ppa, vol_mwh, hist_sd_f, proj_n, vol_stress, spot_stress)

nat_cp_list      = nat_series(nat_ref,          cfg["nat_cp"],  "cp_nat_pct")
nat_eur_list     = nat_series(nat_ref,          cfg["nat_eur"],  "cp_nat")
nat_cp_complete  = nat_series(nat_ref_complete, cfg["nat_cp"],  "cp_nat_pct")
nat_eur_complete = nat_series(nat_ref_complete, cfg["nat_eur"], "cp_nat")

wind_ready    = techno=="Wind" and has_wind
prod_col_roll = cfg["prod_col"] if (techno=="Solar" or wind_ready) else "NatMW"

fig_cap_link, proj_targets = chart_scatter_cp_vs_capacity(
    nat_ref, hourly, cfg["prod_col"], cfg["nat_cp"],
    cfg["color"], cfg["label"], partial_years, techno=="Solar", ex22=ex22)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Overview", "PPA Pricing", "Market Dynamics",
    "Market Evolution", "Pricing & Risk", "Market Overview", "Export",
    "FPC Monte Carlo",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(
        f'## KAL-EL — France {cfg["label"]} {tech_badge(cfg["label"])} '
        f'<span style="font-size:13px;color:#888;font-weight:400">'
        f'{yr_range[0]}–{yr_range[1]}</span>',
        unsafe_allow_html=True)

    ca, cb = st.columns([3,1])
    with ca:
        ytd_note = (f" — <span class='ytd-badge'>2026 YTD included</span>"
                    if current_year in partial_years else "")
        st.markdown(
            f'<span style="font-size:14px;color:#555;">Aggregator View — '
            f'Fixed PPA / Spot Capture — ENTSO-E {data_start.year}–'
            f'{data_end.strftime("%Y-%m-%d")}{ytd_note}</span>',
            unsafe_allow_html=True)
    with cb:
        st.markdown(f'<div class="update-pill" style="float:right">'
                    f'Data as of {data_end.strftime("%d/%m/%Y")}</div>',
                    unsafe_allow_html=True)

    if techno=="Wind" and not has_wind:
        status_msg("Wind data (WindMW) not yet in hourly_spot.csv — "
                   "run the updated ENTSO-E script (B18+B19). Solar shown as fallback.", kind="wind")
    else:
        status_msg("Automatic daily updates via GitHub Actions — ENTSO-E France data.")

    st.markdown("---")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        ppa_card(f"PPA Price (P{chosen_pct})", f"{ppa:.2f}")
    with k2:
        proj_tenor  = proj[proj["year"].between(tenor_start, tenor_end)]
        cp_proj_avg = proj_tenor["p50"].mean()*100 if len(proj_tenor)>0 else 0.0
        c_kpi = C2 if cp_proj_avg>80 else (C4 if cp_proj_avg>65 else C5)
        kpi_card(f"Capture Rate {tenor_start}-{tenor_end}", f"{cp_proj_avg:.0f}%", color=c_kpi)
    with k3:
        sd_proj_avg = (1-proj_tenor["p50"].mean())*100 if len(proj_tenor)>0 else sd_ch*100
        c_sd = C5 if sd_proj_avg>25 else (C3 if sd_proj_avg>15 else C2)
        kpi_card("Shape Discount", f"{sd_proj_avg:.1f}%", color=c_sd, extra_cls="kpi-gold")
    with k4:
        p50_pnl = (vol_mwh*(ref_fwd*(1-float(np.percentile(hist_sd_f,50)))-ppa)/1000
                   if len(hist_sd_f)>0 else 0)
        c_p = C2 if p50_pnl>0 else C5
        kpi_card("P&L P50 (k EUR/yr)", f"{p50_pnl:+.0f}k", color=c_p)
    with k5:
        be_txt = f"P{be}" if be else ">P100"
        c_be   = C2 if be and be>70 else C5
        kpi_card("Break-even Cannib.", be_txt, color=c_be, extra_cls="kpi-red")

    st.markdown("---")
    c1a, c1b = st.columns(2)
    with c1a:
        section(f"Historical Captured Price — {cfg['label']} — {yr_range[0]} onwards")
        desc("Bars: CP% by year. Gold = YTD (excluded from regression).")
        st.plotly_chart(
            chart_historical_cp(nat_ref, asset_ann, has_asset, asset_name,
                                cfg["color"], cfg["label"], nat_cp_list, nat_eur_list,
                                partial_years),
            use_container_width=True)
    with c1b:
        section(f"Projection — {cfg['label']} CP% with Uncertainty Bands")
        desc(f"Anchored on last asset point. {reg_basis} regression slope. Shaded = P10-P90.")
        st.plotly_chart(
            chart_projection(nat_ref, asset_ann, has_asset, proj,
                             nat_cp_list, nat_ref_complete, cfg["nat_cp"],
                             cfg["color"], cfg["label"], sl_u, ic_u, r2_u,
                             last_yr_proj, proj_n, ex22,
                             reg_basis=reg_basis, anchor_val=anchor_val,
                             proj_targets=proj_targets),
            use_container_width=True)

    st.markdown("---")
    section(f"Reference Table — {cfg['label']} Shape Discount and P&L by Percentile")
    desc("Complete years only — YTD excluded. P74 = WPD tender reference.")
    nat_sd_tbl = get_nat_sd(nat_ref_complete, cfg["nat_sd"])
    kp = [5,10,15,20,25,30,35,40,45,50,55,60,65,70,74,75,80,85,90,95,100]
    trows = []
    for p in kp:
        sdn  = float(np.percentile(nat_sd_tbl,p)) if len(nat_sd_tbl)>0 else 0.15
        sda  = float(np.percentile(asset_ann["shape_disc"].dropna(),p)) if has_asset else None
        cpa  = ref_fwd*(1-sda) if sda is not None else None
        pnla = vol_mwh*(cpa-ppa)/1000 if cpa is not None else None
        row  = {"Pct":f"P{p}", "Shape Disc Nat.":f"{sdn*100:.1f}%", "CP Nat.":f"{(1-sdn)*100:.0f}%"}
        if has_asset:
            row["Shape Disc Asset"] = f"{sda*100:.1f}%"
            row["CP Asset"]         = f"{(1-sda)*100:.0f}%"
            row["P&L k EUR/yr"]     = f"{pnla:+.0f}k"
        trows.append(row)
    tdf = pd.DataFrame(trows)
    def _hi(row):
        p = int(row["Pct"][1:])
        if p==chosen_pct: return [f"background-color:{C2};color:white;font-weight:bold"]*len(row)
        if p in [10,50,90]: return [f"background-color:{C2L}"]*len(row)
        if p==74: return [f"background-color:{C3L}"]*len(row)
        return [""]*len(row)
    st.dataframe(tdf.style.apply(_hi,axis=1), use_container_width=True, height=440)

    st.markdown("---")
    section("Production Profile — National vs Asset")
    d1, d2 = st.columns(2)
    with d1:
        section(f"Daily Profile — National {cfg['label']}")
        desc("Average MW by hour of day, one line per month. National ENTSO-E data.")
        st.plotly_chart(
            chart_daily_profile_national(hourly, cfg["prod_col"], cfg["color"], cfg["label"]),
            use_container_width=True)
    with d2:
        section(f"Daily Profile — {asset_name}")
        desc("Same chart for the uploaded asset.")
        if has_asset and asset_raw is not None:
            st.plotly_chart(
                chart_daily_profile_asset(asset_raw, cfg["color"], asset_name),
                use_container_width=True)
        else:
            st.info("Upload an asset load curve in the sidebar to see its daily profile.")

    m1, m2 = st.columns(2)
    with m1:
        section("Monthly Production")
        desc("Bars = asset avg GWh/month. Points = national avg MW.")
        st.plotly_chart(
            chart_monthly_production(hourly, asset_raw, cfg["prod_col"],
                                      cfg["color"], asset_name, has_asset),
            use_container_width=True)
    with m2:
        section("Annual Production")
        desc("Bars = asset GWh/year.")
        st.plotly_chart(
            chart_annual_production(hourly, asset_ann, cfg["prod_col"],
                                     cfg["color"], asset_name, has_asset, partial_years),
            use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PPA Pricing (Forward Curve + Waterfall)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    section("EEX Forward Curve — by Calendar Year")
    desc(f"PPA = Forward x (1 - {cfg['label']} Shape Disc - Imbalance%) - Imbalance EUR.")
    col_i, col_r = st.columns([1,1.6])
    with col_i:
        fwd_rows_live = []
        for yr in range(tenor_start, tenor_end+1):
            px = st.number_input(f"CAL {yr} (EUR/MWh)", 10.0, 200.0,
                                 float(DEFAULT_FWD.get(yr,52.0)), 0.5, key=f"fwd_{yr}")
            fwd_rows_live.append({"year":yr,"forward":px})
        fwd_df_live = pd.DataFrame(fwd_rows_live)
        st.info("API connector coming soon.")
    with col_r:
        rows_ppa = []
        for _, row in fwd_df_live.iterrows():
            fsd    = ic_u + sl_u*row["year"]
            cp     = row["forward"]*(1-fsd)
            ppa_yr = row["forward"]*(1-fsd-imb_eur/row["forward"])-imb_eur
            rows_ppa.append({"Year":int(row["year"]), "Forward":f"{row['forward']:.2f}",
                             f"{cfg['label']} Proj. SD":f"{fsd*100:.1f}%",
                             "Captured (EUR/MWh)":f"{cp:.2f}",
                             "PPA Price (EUR/MWh)":f"{ppa_yr:.2f}",
                             "P&L/MWh":f"{cp-ppa_yr:+.2f}"})
        st.dataframe(pd.DataFrame(rows_ppa), use_container_width=True, hide_index=True)
    st.plotly_chart(chart_forward(fwd_df_live), use_container_width=True)


    st.markdown("---")
    section(f"PPA Price Waterfall — {cfg['label']} Component Breakdown")
    desc("All values feed into the PPA price used across all tabs. Adjust premiums here.")

    w1, w2 = st.columns(2)
    with w1:
        st.number_input("Imbalance Cost (EUR/MWh)", 0.0, 10.0, step=0.1,
                        key="imb_eur", help="Suggested: 1.9 EUR/MWh")
        st.number_input("Volume Risk (%)", 0.0, 10.0, step=0.1,
                        key="vol_risk_pct", help="Suggested: 0-2.5%")
        st.number_input("Price Risk (%)", 0.0, 10.0, step=0.1,
                        key="price_risk_pct", help="Suggested: 0-3.0%")
    with w2:
        st.slider("Additional Discount (%)", 0.0, 10.0, step=0.25, key="add_disc")
        st.number_input("GoO Value (EUR/MWh)", 0.0, 10.0, step=0.1,
                        key="goo_value", help="Suggested: 1.0 EUR/MWh")
        st.number_input("Margin (EUR/MWh)", 0.0, 10.0, step=0.1,
                        key="margin", help="Suggested: 1.0 EUR/MWh")

    imb_eur        = float(st.session_state.imb_eur)
    add_disc       = float(st.session_state.add_disc) / 100
    vol_risk_pct   = float(st.session_state.vol_risk_pct) / 100
    price_risk_pct = float(st.session_state.price_risk_pct) / 100
    goo_value      = float(st.session_state.goo_value)
    margin         = float(st.session_state.margin)

    st.markdown("---")
    ppa_wf = (ref_fwd - ref_fwd*sd_ch - ref_fwd*add_disc
              - ref_fwd*vol_risk_pct - ref_fwd*price_risk_pct
              - imb_eur + goo_value + margin)

    params_df = pd.DataFrame([
        {"Component":"Baseload Forward",  "Value (EUR/MWh)":f"{ref_fwd:.2f}",           "Type":"Base"},
        {"Component":"Shape Discount",    "Value (EUR/MWh)":f"-{ref_fwd*sd_ch:.2f}",     "Type":"Deduction"},
        {"Component":"Add. Discount",     "Value (EUR/MWh)":f"-{ref_fwd*add_disc:.2f}",  "Type":"Deduction"},
        {"Component":"Volume Risk",       "Value (EUR/MWh)":f"-{ref_fwd*vol_risk_pct:.2f}", "Type":"Deduction"},
        {"Component":"Price Risk",        "Value (EUR/MWh)":f"-{ref_fwd*price_risk_pct:.2f}", "Type":"Deduction"},
        {"Component":"Balancing Cost",    "Value (EUR/MWh)":f"-{imb_eur:.2f}",           "Type":"Deduction"},
        {"Component":"GoO Value",         "Value (EUR/MWh)":f"+{goo_value:.2f}",         "Type":"Addition"},
        {"Component":"Margin",            "Value (EUR/MWh)":f"+{margin:.2f}",            "Type":"Addition"},
        {"Component":"PPA Price",         "Value (EUR/MWh)":f"{ppa_wf:.2f}",             "Type":"Total"},
    ])
    def _style_params(row):
        if row["Type"]=="Base":      return [f"background-color:{C2};color:white;font-weight:bold"]*len(row)
        if row["Type"]=="Addition":  return [f"background-color:{C2L}"]*len(row)
        if row["Type"]=="Total":     return [f"background-color:{C1};color:white;font-weight:bold"]*len(row)
        return [""]*len(row)
    st.dataframe(params_df.style.apply(_style_params,axis=1),
                 use_container_width=True, hide_index=True,
                 column_order=["Component","Value (EUR/MWh)"])

    st.plotly_chart(
        chart_waterfall(ref_fwd, sd_ch, imb_eur, cfg["label"],
                        vol_risk_pct=vol_risk_pct, price_risk_pct=price_risk_pct,
                        cannib_risk_pct=0.0, goo_value=goo_value,
                        add_disc=add_disc, margin=margin),
        use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Market Dynamics
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    section("Negative Price Hours — by Year")
    desc("Hours with day-ahead price < 0. Trend line excludes YTD. CRE threshold: 15h/yr.")
    st.plotly_chart(chart_neg_hours(hourly, partial_years, cfg["color"]), use_container_width=True)

    st.markdown("---")
    c3a, c3b = st.columns(2)
    with c3a:
        section(f"Monthly Cannibalization Profile — {cfg['label']}")
        desc("Average shape discount by calendar month. Error bars = year-to-year std dev.")
        fig_mo, monthly_agg = chart_monthly_profile(hourly, cfg["prod_col"], cfg["color"], cfg["label"])
        st.plotly_chart(fig_mo, use_container_width=True)
    with c3b:
        section(f"CP% vs National {cfg['label']} Capacity")
        desc("Each point = one year. X-axis = average national installed capacity (MW).")
        st.plotly_chart(fig_cap_link, use_container_width=True)

    st.markdown("---")
    section(f"Annual Shape Discount Change — {cfg['label']}")
    desc("Year-on-year delta in shape discount (pp). Positive = more cannibalization.")
    st.plotly_chart(chart_shape_disc_delta(nat_ref, cfg["nat_sd"], cfg["color"], cfg["label"]),
                    use_container_width=True)

    st.markdown("---")
    section(f"Heatmap — Monthly Shape Discount by Year — {cfg['label']}")
    desc("Shape discount by month and year. Darker = higher cannibalization.")
    st.plotly_chart(chart_heatmap(monthly_agg, cfg["color"], cfg["label"]), use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Market Value Analysis — Jomaux / GEM Energy Analytics</div>',
                unsafe_allow_html=True)
    section(f"Market Value vs {cfg['label']} Generation Output")
    desc("Average day-ahead price per MW bin. Method: GEM Energy Analytics (Oct 2024).")
    st.plotly_chart(
        chart_market_value_vs_penetration(hourly, cfg["prod_col"], cfg["color"], cfg["label"], partial_years),
        use_container_width=True)

    st.markdown("---")
    j1, j2 = st.columns(2)
    with j1:
        season_lbl = "Apr-Sep" if cfg["duck_months"]==list(range(4,10)) else "All months"
        section(f"Duck / Canyon Curve — {cfg['label']} ({season_lbl})")
        desc("Normalised day-ahead prices by hour. Method: GEM Energy Analytics (Mar 2025).")
        st.plotly_chart(chart_duck_curve(hourly, cfg["color"], cfg["label"], cfg["duck_months"]),
                        use_container_width=True)
    with j2:
        section(f"Canyon Curve — Last 4 Years ({cfg['label']})")
        desc("Same normalisation, last 4 complete years. Grey = older, colour = most recent.")
        st.plotly_chart(chart_canyon_curve(hourly, cfg["color"], cfg["label"],
                                           cfg["duck_months"], recent_years=4),
                        use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Market Evolution
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown(f"## Market Evolution — Rolling Capture Rate ({cfg['label']})")
    if techno=="Wind" and not has_wind:
        status_msg("Wind data not yet available — run the ENTSO-E update script. "
                   "Solar rolling M0 shown as fallback.", kind="wind")
    desc(f"Rolling M0 on RAW hourly data. M0(t) = sum({prod_col_roll} x Spot) / sum({prod_col_roll}) over last N days.")

    if st.button("Compute rolling M0", key="compute_roll"):
        roll = compute_rolling_m0(hourly[["Date","Spot",prod_col_roll]].copy(),
                                  prod_col=prod_col_roll, windows=(30,90,365))
    else:
        roll = None

    if roll is None or len(roll) < 10:
        if roll is not None:
            st.warning("Not enough data to compute rolling windows.")
    else:
        section(f"Rolling Capture Rate — M0 / Baseload (%) — {cfg['label']}")
        desc("100% = no cannibalization. 30d dotted = short-term. 365d solid = structural trend.")
        st.plotly_chart(
            chart_rolling_cp(roll, nat_ref_complete, nat_ref, cfg["nat_cp"],
                              nat_cp_complete, cfg["color"], cfg["label"], partial_years),
            use_container_width=True)

        st.markdown("---")
        section(f"Rolling Captured Price — M0 (EUR/MWh) — {cfg['label']}")
        desc("Gap between grey baseload and M0 = shape discount in EUR/MWh.")
        st.plotly_chart(
            chart_rolling_eur(roll, nat_ref_complete, nat_eur_complete, cfg["color"], cfg["label"]),
            use_container_width=True)

        st.markdown("---")
        section("Recent Period Summary")
        latest   = pd.to_datetime(hourly["Date"]).max().normalize()
        sum_rows = []
        for w in [30,90,365]:
            cutoff  = latest - pd.Timedelta(days=w)
            h_slice = hourly[pd.to_datetime(hourly["Date"]).dt.normalize()>cutoff]
            if len(h_slice)<w*12: continue
            sum_rev  = (h_slice[prod_col_roll]*h_slice["Spot"]).sum()
            sum_prod = h_slice[prod_col_roll].sum()
            bl_val   = h_slice["Spot"].sum()/len(h_slice)
            m0_val   = sum_rev/sum_prod if sum_prod>0 else np.nan
            cp_val   = m0_val/bl_val if bl_val else np.nan
            sum_rows.append({"Window":f"Last {w} days",
                             "From":cutoff.strftime("%d/%m/%Y"),"To":latest.strftime("%d/%m/%Y"),
                             "Baseload (EUR/MWh)":f"{bl_val:.2f}",
                             "M0 Captured (EUR/MWh)":f"{m0_val:.2f}",
                             "Capture Rate":f"{cp_val*100:.1f}%",
                             "Shape Discount":f"{(1-cp_val)*100:.1f}%"})
        if sum_rows:
            def _hi_sum(row):
                if "365" in row["Window"]: return [f"background-color:{C2L}"]*len(row)
                if "90"  in row["Window"]: return [f"background-color:{C3L}"]*len(row)
                return [""]*len(row)
            st.dataframe(pd.DataFrame(sum_rows).style.apply(_hi_sum,axis=1),
                         use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Pricing & Risk (Asset Pricer)
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
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
        asset_raw=asset_raw,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Market Overview (Prices + Spot + Mix + Commentary)
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("## Market Overview — France Power Market")
    bal = load_balancing()

    if bal is None or len(bal) == 0:
        st.warning("Balancing data not yet available. Run the updated ENTSO-E script to fetch data.")
    else:
        bal_end   = pd.to_datetime(bal["Date"]).max()
        bal_start = pd.to_datetime(bal["Date"]).min()
        status_msg(f"Balancing data: {bal_start.strftime('%Y-%m-%d')} to "
                   f"{bal_end.strftime('%Y-%m-%d')} — {len(bal):,} hourly rows.")

        st.markdown("---")
        section("Last 7 Days — DA & Imbalance Prices (hourly)")
        desc("Day-ahead, positive and negative imbalance prices over the last 7 days.")
        st.plotly_chart(chart_last_week(bal), use_container_width=True)

        st.markdown("---")
        section("Monthly History — Day-Ahead Price")
        desc("Monthly average DA price — full history.")
        st.plotly_chart(chart_da_monthly(bal), use_container_width=True)

        section("DA Price Heatmap — Hour x Month")
        desc("Average DA price by hour of day and month — reveals intraday and seasonal patterns.")
        st.plotly_chart(chart_da_heatmap(bal), use_container_width=True)

        st.markdown("---")
        section("Price Spreads")
        s1, s2 = st.columns(2)
        with s1:
            section("DA Intraday Spread (Max-Min)")
            desc("Monthly average of daily DA max minus min. Measures intraday price volatility.")
            st.plotly_chart(chart_intraday_spread(bal), use_container_width=True)
        with s2:
            section("Imbalance Negative vs DA")
            desc("Imb_Neg minus DA = real additional cost of negative imbalance for a producer.")
            st.plotly_chart(chart_imbalance_vs_da(bal), use_container_width=True)

        st.markdown("---")
        section("Balancing Services — aFRR & mFRR")
        desc("Activated energy prices for aFRR and mFRR. Data sparse before 2022 for France.")
        st.plotly_chart(chart_balancing_services(bal), use_container_width=True)

        st.markdown("---")
        section("Last 12 Months — Summary Statistics")
        desc("Mean, min, max, std of each price series over the last 12 months.")
        stats = summary_stats(bal)
        if stats:
            cols_kpi = st.columns(len(stats))
            for i, (label, s) in enumerate(stats.items()):
                with cols_kpi[i]:
                    kpi_card(label, f"{s['mean']:.1f}", color=C2 if s["mean"]>0 else C5)
                    st.markdown(
                        f'<div style="font-size:11px;color:#888;margin-top:4px;">'
                        f'Min: {s["min"]:.0f} | Max: {s["max"]:.0f} | Std: {s["std"]:.0f} EUR/MWh</div>',
                        unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("## Market Overview — France Power")

    # ── helpers ──────────────────────────────────────────────────────────────
    hourly_full = load_hourly()  # unfiltered by yr_range
    has_gen_mix = all(c in hourly_full.columns for c in ["NuclearMW","GasMW","HydroMW","OtherMW"])

    # Daily spot average
    hourly_full["_date"] = pd.to_datetime(hourly_full["Date"]).dt.normalize()
    daily_spot = (hourly_full.groupby("_date")["Spot"].mean().reset_index()
                  .rename(columns={"_date":"Date","Spot":"spot_avg"}))
    daily_spot["Date"] = pd.to_datetime(daily_spot["Date"])

    # Latest values
    last_spot       = daily_spot["spot_avg"].iloc[-1] if len(daily_spot) > 0 else np.nan
    spot_d1         = daily_spot["spot_avg"].iloc[-2] if len(daily_spot) > 1 else np.nan
    spot_chg        = last_spot - spot_d1
    spot_chg_pct    = spot_chg / spot_d1 * 100 if spot_d1 else 0

    last_solar_mw   = hourly_full[hourly_full["NatMW"] > 0]["NatMW"].iloc[-24:].mean() \
                      if "NatMW" in hourly_full.columns else np.nan
    last_nuclear_mw = hourly_full["NuclearMW"].iloc[-24:].mean() \
                      if "NuclearMW" in hourly_full.columns else np.nan
    last_wind_mw    = hourly_full["WindMW"].iloc[-24:].mean() \
                      if "WindMW" in hourly_full.columns else np.nan

    # ── Manual forward inputs ─────────────────────────────────────────────────
    st.markdown("### Forward Prices (manual)")
    fi1, fi2, fi3, fi4 = st.columns(4)
    with fi1: cal27 = st.number_input("CAL 27 (EUR/MWh)", 30.0, 150.0, float(DEFAULT_FWD.get(2027, 55.0)), 0.5, key="mo_cal27")
    with fi2: cal28 = st.number_input("CAL 28 (EUR/MWh)", 30.0, 150.0, float(DEFAULT_FWD.get(2028, 52.0)), 0.5, key="mo_cal28")
    with fi3: cal29 = st.number_input("CAL 29 (EUR/MWh)", 30.0, 150.0, float(DEFAULT_FWD.get(2029, 52.0)), 0.5, key="mo_cal29")
    with fi4: nuclear_avail = st.number_input("Nuclear avail. (GW)", 30.0, 65.0, 45.0, 0.5, key="mo_nuc")

    st.markdown("---")

    # ── KPI strip ─────────────────────────────────────────────────────────────
    section("Key Indicators")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    spot_color = C2 if spot_chg >= 0 else C5

    with k1:
        kpi_card("FR Spot (DA)", f"{last_spot:.1f}" if not np.isnan(last_spot) else "N/A",
                 color=spot_color)
        arrow = "+" if spot_chg >= 0 else ""
        st.markdown(f'<div style="font-size:11px;color:#888;margin-top:2px;">'
                    f'D-1: {arrow}{spot_chg:.1f} EUR/MWh ({arrow}{spot_chg_pct:.1f}%)</div>',
                    unsafe_allow_html=True)
    with k2:
        kpi_card("CAL 27", f"{cal27:.1f}", color=C1)
    with k3:
        kpi_card("CAL 28", f"{cal28:.1f}", color=C1)
    with k4:
        kpi_card("CAL 29", f"{cal29:.1f}", color=C1)
    with k5:
        nuc_color = C5 if nuclear_avail < 43 else (C3 if nuclear_avail < 48 else C2)
        kpi_card("Nuclear (GW)", f"{nuclear_avail:.1f}", color=nuc_color, extra_cls="kpi-gold")
    with k6:
        if not np.isnan(last_solar_mw):
            kpi_card("Solar avg 24h (MW)", f"{last_solar_mw:.0f}", color=C2)
        else:
            kpi_card("Solar avg 24h (MW)", "N/A", color=C1)

    st.markdown("---")

    # ── Chart 1: FR Spot historical (daily avg) ───────────────────────────────
    section("FR Day-Ahead Spot Price — Historical (daily average)")
    desc("Daily average of hourly DA prices. Source: ENTSO-E France.")

    # Zoom selector
    zoom_opts = {"1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "All": None}
    z_col = st.columns(len(zoom_opts))
    selected_zoom = st.radio("Zoom", list(zoom_opts.keys()), index=3,
                              horizontal=True, key="spot_zoom")
    z_days = zoom_opts[selected_zoom]
    if z_days:
        cutoff_spot = daily_spot["Date"].max() - pd.Timedelta(days=z_days)
        spot_plot   = daily_spot[daily_spot["Date"] >= cutoff_spot]
    else:
        spot_plot = daily_spot

    if len(spot_plot) == 0:
        st.info("No spot data available for the selected zoom window.")
    else:
        fig_spot = go.Figure()
        fig_spot.add_trace(go.Scatter(
            x=spot_plot["Date"].dt.to_pydatetime(),
            y=spot_plot["spot_avg"].astype(float).tolist(),
            mode="lines", name="FR DA Spot",
            line=dict(color=C1, width=1.5),
            fill="tozeroy", fillcolor="rgba(29,58,74,0.08)"
        ))
        fig_spot.update_layout(
            height=350, margin=dict(l=40,r=20,t=30,b=40),
            plot_bgcolor=WHT, paper_bgcolor=WHT,
            yaxis=dict(title="EUR/MWh", gridcolor="#eee",
                       tickfont=dict(family="Calibri,Arial", size=12)),
            xaxis=dict(gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
            font=dict(family="Calibri,Arial", size=13),
            showlegend=False,
            hovermode="x unified"
        )
        plotly_base(fig_spot, h=350, show_legend=False)
        st.plotly_chart(fig_spot, use_container_width=True)

    st.markdown("---")

    # ── Chart 2: Generation mix ───────────────────────────────────────────────
    section("FR Power Generation Mix — Last 30 Days")
    desc("Stacked area chart — hourly MW by source. Source: ENTSO-E France.")

    if not has_gen_mix:
        st.info("Generation mix columns (NuclearMW, GasMW, HydroMW, OtherMW) not yet in hourly_spot.csv. "
                "Run the Full Refresh ENTSO-E workflow once to populate them.")
    else:
        cutoff_mix = pd.to_datetime(hourly_full["Date"]).max() - pd.Timedelta(days=30)
        mix_data   = hourly_full[pd.to_datetime(hourly_full["Date"]) >= cutoff_mix].copy()
        mix_data["_date"] = pd.to_datetime(mix_data["Date"]).dt.floor("6h")

        # Resample to 6h for readability
        mix_agg = mix_data.groupby("_date").agg(
            NuclearMW=("NuclearMW","mean"),
            HydroMW  =("HydroMW",  "mean"),
            WindMW   =("WindMW",   "mean"),
            NatMW    =("NatMW",    "mean"),
            GasMW    =("GasMW",    "mean"),
            OtherMW  =("OtherMW",  "mean"),
        ).reset_index()

        MIX_COLORS = {
            "Nuclear": "#2A9D8F",
            "Hydro":   "#1D3A4A",
            "Wind":    "#264653",
            "Solar":   "#E9C46A",
            "Gas":     "#F4A261",
            "Other":   "#ccc",
        }
        col_map = {
            "Nuclear": "NuclearMW",
            "Hydro":   "HydroMW",
            "Wind":    "WindMW",
            "Solar":   "NatMW",
            "Gas":     "GasMW",
            "Other":   "OtherMW",
        }
        fig_mix = go.Figure()
        for label, col in col_map.items():
            if col in mix_agg.columns:
                fig_mix.add_trace(go.Scatter(
                    x=mix_agg["_date"], y=mix_agg[col],
                    mode="lines", name=label,
                    stackgroup="one",
                    line=dict(width=0.5, color=MIX_COLORS[label]),
                    fillcolor=MIX_COLORS[label],
                    hovertemplate=f"<b>{label}</b>: %{{y:.0f}} MW<extra></extra>"
                ))
        fig_mix.update_layout(
            height=380, margin=dict(l=40,r=20,t=30,b=40),
            plot_bgcolor=WHT, paper_bgcolor=WHT,
            yaxis=dict(title="MW", gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
            xaxis=dict(gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
            font=dict(family="Calibri,Arial", size=13),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                        font=dict(family="Calibri,Arial", size=12)),
            hovermode="x unified"
        )
        plotly_base(fig_mix, h=380)
        st.plotly_chart(fig_mix, use_container_width=True)

    st.markdown("---")

    # ── Chart 3: Nuclear capacity trend ──────────────────────────────────────
    section("FR Nuclear Generation — Last 90 Days (daily average)")
    desc("Daily average nuclear output (MW). Declining trend = maintenance / outages.")

    if "NuclearMW" not in hourly_full.columns or hourly_full["NuclearMW"].sum() == 0:
        st.info("NuclearMW not yet available. Run the Full Refresh ENTSO-E workflow.")
    else:
        cutoff_nuc = pd.to_datetime(hourly_full["Date"]).max() - pd.Timedelta(days=90)
        nuc_data   = hourly_full[pd.to_datetime(hourly_full["Date"]) >= cutoff_nuc].copy()
        nuc_data["_date"] = pd.to_datetime(nuc_data["Date"]).dt.normalize()
        nuc_daily  = nuc_data.groupby("_date")["NuclearMW"].mean().reset_index()

        fig_nuc = go.Figure()
        fig_nuc.add_trace(go.Scatter(
            x=nuc_daily["_date"], y=nuc_daily["NuclearMW"],
            mode="lines", name="Nuclear MW",
            line=dict(color=C2, width=2),
            fill="tozeroy", fillcolor="rgba(42,157,143,0.12)",
            hovertemplate="<b>%{x|%d %b}</b>: %{y:.0f} MW<extra></extra>"
        ))
        # Rolling 7-day average
        nuc_daily["roll7"] = nuc_daily["NuclearMW"].rolling(7, min_periods=1).mean()
        fig_nuc.add_trace(go.Scatter(
            x=nuc_daily["_date"], y=nuc_daily["roll7"],
            mode="lines", name="7-day avg",
            line=dict(color=C3, width=2, dash="dot"),
            hovertemplate="<b>7d avg</b>: %{y:.0f} MW<extra></extra>"
        ))
        fig_nuc.update_layout(
            height=320, margin=dict(l=40,r=20,t=30,b=40),
            plot_bgcolor=WHT, paper_bgcolor=WHT,
            yaxis=dict(title="MW", gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
            xaxis=dict(gridcolor="#eee", tickfont=dict(family="Calibri,Arial", size=12)),
            font=dict(family="Calibri,Arial", size=13),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5,
                        font=dict(family="Calibri,Arial", size=12)),
            hovermode="x unified"
        )
        plotly_base(fig_nuc, h=320)
        st.plotly_chart(fig_nuc, use_container_width=True)

    st.markdown("---")

    # ── AI Market Commentary ──────────────────────────────────────────────────
    section("AI Market Commentary")
    desc("Generated by Claude from today's data. Click to refresh.")

    if st.button("Generate market commentary", key="gen_commentary"):
        # Build context string from available data
        spot_str    = f"{last_spot:.1f} EUR/MWh" if not np.isnan(last_spot) else "N/A"
        spot_mv_str = (f"{'+' if spot_chg >= 0 else ''}{spot_chg:.1f} EUR/MWh vs yesterday"
                       if not np.isnan(spot_chg) else "N/A")
        nuc_str     = f"{nuclear_avail:.1f} GW" if nuclear_avail else "N/A"
        solar_str   = f"{last_solar_mw:.0f} MW (24h avg)" if not np.isnan(last_solar_mw) else "N/A"
        wind_str    = f"{last_wind_mw:.0f} MW (24h avg)" if not np.isnan(last_wind_mw) else "N/A"
        cal27_str   = f"{cal27:.1f} EUR/MWh"

        data_today = f"""
    Today's date: {pd.Timestamp.now().strftime('%d %B %Y')}

    France power market data:
    - FR DA spot price (latest daily avg): {spot_str} ({spot_mv_str})
    - CAL 27 forward: {cal27_str}
    - Nuclear availability: {nuc_str}
    - Solar generation 24h avg: {solar_str}
    - Wind generation 24h avg: {wind_str}
    """

        prompt = f"""You are a senior energy market analyst specialising in the French power market and solar PPAs.
    Write a concise market commentary (4-5 sentences, no bullet points) for an origination team based on the following data.
    Focus on: spot price drivers, renewable output, nuclear availability, and any implications for PPA pricing or cannibalization risk.
    Be factual and direct. Do not use filler phrases.

    {data_today}"""

        with st.spinner("Generating commentary..."):
            try:
                import requests, json
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=30
                )
                result = response.json()
                commentary = result["content"][0]["text"]
                st.markdown(
                    f'<div style="background-color:{C3L};border-left:4px solid {C3};'
                    f'padding:16px 20px;border-radius:4px;font-family:Calibri,Arial,sans-serif;'
                    f'font-size:14px;color:{C1};line-height:1.7;">'
                    f'{commentary}</div>',
                    unsafe_allow_html=True)
                st.caption(f"Generated {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')} — Claude Sonnet")
            except Exception as e:
                st.error(f"Commentary generation failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — Export & SPOT Extractor
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        section("Excel Export — All Dashboard Data")
        if st.button("Generate Excel File"):
            with st.spinner("Generating..."):
                hist_sd_export = get_nat_sd(nat_ref_complete, cfg["nat_sd"]).values
                buf = build_excel(nat_ref, hourly, asset_ann, has_asset, asset_name,
                                  proj, pnl_v, ppa, scenarios, fwd_curve, hist_sd_export)
            st.download_button(label="Download ppa_dashboard_export.xlsx", data=buf,
                               file_name="ppa_dashboard_export.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.success("File ready.")
    with col_e2:
        section("Expected Load Curve Format")
        st.code("Date,Prod_MWh\n2024-01-01 00:00:00,0.0\n2024-01-01 10:00:00,4.2", language="text")

    st.markdown("---")
    section("Load Curve Converter")
    desc("Upload any Excel or CSV, map your columns to Date and Prod_MWh, download the converted file.")
    uploaded_conv = st.file_uploader("Upload file to convert", type=["xlsx","csv","xls"], key="converter")
    if uploaded_conv:
        try:
            df_conv = (pd.read_csv(uploaded_conv) if uploaded_conv.name.endswith(".csv")
                       else pd.read_excel(uploaded_conv))
            st.markdown(f"**{len(df_conv):,} rows — {len(df_conv.columns)} columns detected**")
            st.dataframe(df_conv.head(5), use_container_width=True)
            cols = df_conv.columns.tolist()
            c1, c2 = st.columns(2)
            with c1: date_col     = st.selectbox("Date column", cols, key="conv_date")
            with c2: prod_col_conv = st.selectbox("Production column (MWh or kWh)", cols, key="conv_prod")
            unit = st.radio("Unit of production column", ["MWh","kWh"], horizontal=True, key="conv_unit")
            if st.button("Convert", key="conv_btn"):
                out = df_conv[[date_col, prod_col_conv]].copy()
                out.columns = ["Date","Prod_MWh"]
                out["Date"]     = pd.to_datetime(out["Date"], errors="coerce")
                out["Prod_MWh"] = pd.to_numeric(out["Prod_MWh"], errors="coerce")
                if unit=="kWh": out["Prod_MWh"] = out["Prod_MWh"]/1000
                out = out.dropna(subset=["Date","Prod_MWh"]).sort_values("Date").reset_index(drop=True)
                st.success(f"{len(out):,} rows converted — {out['Prod_MWh'].sum():,.0f} MWh total")
                st.dataframe(out.head(10), use_container_width=True)
                st.download_button("Download converted file",
                                   data=out.to_csv(index=False).encode("utf-8"),
                                   file_name="load_curve_converted.csv", mime="text/csv")
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")
    section("SPOT Data Extractor — ENTSO-E")
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        api_key_in = st.text_input("ENTSO-E API Key", type="password")
        country_c  = st.selectbox("Country", ["FR","DE","ES","BE","NL","IT","GB"], index=0)
        d_start    = st.date_input("Start Date", value=pd.Timestamp("2024-01-01"))
        d_end      = st.date_input("End Date",   value=pd.Timestamp("2024-12-31"))
        incl_solar = st.checkbox("Include Solar Production (NatMW)", value=True)
        incl_wind  = st.checkbox("Include Wind Production (WindMW)", value=True)
    with col_ex2:
        st.code("Date,Year,Month,Hour,Spot,NatMW,WindMW", language="text")
        if api_key_in and st.button("Extract Data", key="extract_btn"):
            with st.spinner("Connecting to ENTSO-E..."):
                try:
                    from entsoe import EntsoePandasClient
                    import time
                    client = EntsoePandasClient(api_key=api_key_in)
                    start  = pd.Timestamp(d_start, tz="Europe/Paris")
                    end    = pd.Timestamp(d_end,   tz="Europe/Paris") + pd.Timedelta(days=1)
                    prices = client.query_day_ahead_prices(country_c, start=start, end=end)
                    prices = prices.resample("1h").mean()
                    df_out = pd.DataFrame({"Spot":prices}).reset_index()
                    df_out.columns = ["Date","Spot"]
                    df_out["Date"]  = df_out["Date"].dt.tz_localize(None)
                    df_out["Year"]  = df_out["Date"].dt.year
                    df_out["Month"] = df_out["Date"].dt.month
                    df_out["Hour"]  = df_out["Date"].dt.hour
                    df_out["NatMW"] = 0.0; df_out["WindMW"] = 0.0
                    def _fetch_gen(psr):
                        time.sleep(1)
                        g = client.query_generation(country_c, start=start, end=end, psr_type=psr)
                        if isinstance(g, pd.DataFrame): g = g.sum(axis=1)
                        return g.resample("1h").mean()
                    if incl_solar:
                        try:
                            s = _fetch_gen("B16"); s.index = s.index.tz_localize(None)
                            df_out = df_out.set_index("Date").join(s.rename("_s"), how="left")
                            df_out["NatMW"] = df_out["_s"].fillna(0)
                            df_out = df_out.drop(columns=["_s"]).reset_index()
                        except Exception as e2: st.warning(f"Solar unavailable: {e2}")
                    if incl_wind:
                        try:
                            on  = _fetch_gen("B19"); on.index  = on.index.tz_localize(None)
                            off = _fetch_gen("B18"); off.index = off.index.tz_localize(None)
                            wtot = on.add(off, fill_value=0)
                            df_out = df_out.set_index("Date").join(wtot.rename("_w"), how="left")
                            df_out["WindMW"] = df_out["_w"].fillna(0)
                            df_out = df_out.drop(columns=["_w"]).reset_index()
                        except Exception as e3: st.warning(f"Wind unavailable: {e3}")
                    df_out = df_out[["Date","Year","Month","Hour","Spot","NatMW","WindMW"]].dropna(subset=["Spot"])
                    st.success(f"{len(df_out):,} hours extracted")
                    st.dataframe(df_out.head(24), use_container_width=True)
                    st.download_button("Download CSV", data=df_out.to_csv(index=False).encode("utf-8"),
                                       file_name=f"spot_{country_c}_{d_start}_{d_end}.csv", mime="text/csv")
                except ImportError: st.error("entsoe-py not installed.")
                except Exception as e: st.error(f"ENTSO-E Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — FPC Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════
with tab8:
    render_fpc_tab(
        hourly=hourly,
        nat_ref_complete=nat_ref_complete,
        asset_ann=asset_ann,
        asset_raw=asset_raw,
        has_asset=has_asset,
        asset_name=asset_name,
        cfg=cfg,
        sl_u=sl_u, ic_u=ic_u,
        hist_sd_f=hist_sd_f,
        plotly_base=plotly_base,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — FPC Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════
with tab8:
    render_fpc_tab(
        hourly=hourly,
        nat_ref_complete=nat_ref_complete,
        asset_ann=asset_ann,
        asset_raw=asset_raw,
        has_asset=has_asset,
        asset_name=asset_name,
        cfg=cfg,
        sl_u=sl_u, ic_u=ic_u,
        hist_sd_f=hist_sd_f,
        plotly_base=plotly_base,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
ytd_note = " — 2026 YTD included (excl. regression)" if partial_years else ""
st.markdown(
    f'<span style="font-size:12px;color:#888;font-family:Calibri,Arial,sans-serif;">'
    f'v2.7 — ENTSO-E France {data_start.year}–{data_end.strftime("%Y-%m-%d")} '
    f'— {len(hourly):,} hours{ytd_note} — Technology: {cfg["label"]} — '
    f'Regression: {reg_basis} — Tenor: {tenor_start}–{tenor_end}'
    f'</span>', unsafe_allow_html=True)
