"""
PPA Pricing Dashboard — KAL-EL v2.4
Modular architecture. Logic in compute.py | charts.py | data.py | ui.py | config.py | excel.py
Changes v2.4:
- Projection anchored on last asset point, slope chosen (Asset/National radio)
- 4 production charts moved to Overview tab
- Year range slider in sidebar
- Annual production: asset only (no national)
- Monthly production: rounded to 0 decimal
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
from data    import load_nat, load_hourly, load_log, wind_available, compute_rolling_m0, nat_series, get_nat_sd
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
    chart_daily_profile_national,
    chart_daily_profile_asset,
    chart_monthly_production,
    chart_annual_production,
)
from ui    import section, desc, status_msg, ppa_card, kpi_card, tech_badge, plotly_base
from excel import build_excel

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

    # Year range slider — loaded after data
    _hourly_full = load_hourly()
    _yr_min = int(_hourly_full["Year"].min())
    _yr_max = int(_hourly_full["Year"].max())
    yr_range = st.slider("Year range", _yr_min, _yr_max, (_yr_min, _yr_max), key="yr_range")

    st.markdown("---")
    st.markdown("### PPA Parameters")
    imb_eur  = st.number_input("Imbalance Cost (EUR/MWh)", 0.0, 10.0, 1.9, 0.1)
    add_disc = st.slider("Additional Discount (%)", 0.0, 10.0, 0.0, 0.25) / 100

    st.markdown("---")
    st.markdown("### Pricing Tenor")
    _nat_tmp    = load_nat()
    _last_yr    = int(_nat_tmp[_nat_tmp["partial"] == False]["year"].max())
    tenor_start = st.number_input("Tenor start (year)",
                                   min_value=_last_yr+1, max_value=_last_yr+20,
                                   value=_last_yr+1, step=1, key="tenor_start")
    tenor_end   = st.number_input("Tenor end (year)",
                                   min_value=_last_yr+1, max_value=_last_yr+20,
                                   value=_last_yr+5, step=1, key="tenor_end")
    
    st.markdown("---")
    st.markdown("### Sensitivity Analysis")
    chosen_pct  = st.slider("Selected Percentile", 1, 100, 74)
    proj_n      = st.slider("Projection Horizon (years)", 1, 10, 5)
    vol_stress  = st.slider("Volume Stress (+/-%%)", 0, 30, 20)
    spot_stress = st.slider("Spot Stress (+/-%%)", 0, 30, 20)

    st.markdown("---")
    st.markdown("### Projection Settings")
    reg_basis = st.radio("Regression basis", ["Asset","National"],
                         horizontal=True, key="reg_basis",
                         help="Which slope to use for CP% projection")

    st.markdown("---")
    st.markdown(f"### {cfg['label']} Asset Upload")
    uploaded = st.file_uploader("", type=["xlsx","csv"], label_visibility="hidden")
    st.caption("Columns: Date | Prod_MWh")
    st.download_button("Download example", data=EXAMPLE_CSV.encode("utf-8"),
                       file_name="example_load_curve.csv", mime="text/csv",
                       key="dl_example")

    sb_date_col = None
    sb_prod_col = None
    sb_unit     = "MWh"

    if uploaded:
        try:
            _raw  = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                     else pd.read_excel(uploaded))
            _cols = _raw.columns.tolist()
            sb_date_col = st.selectbox(
                "Date column", _cols,
                index=next((i for i, c in enumerate(_cols) if "date" in c.lower()), 0),
                key="sb_date_col")
            sb_prod_col = st.selectbox(
                "Production column", _cols,
                index=next((i for i, c in enumerate(_cols)
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
# DATA & COMPUTE
# ══════════════════════════════════════════════════════════════════════════════
nat_ref = load_nat()
hourly  = load_hourly()

# Apply year range filter
hourly = hourly[hourly["Year"].between(yr_range[0], yr_range[1])]

data_end      = pd.to_datetime(hourly["Date"]).max()
data_start    = pd.to_datetime(hourly["Date"]).min()
current_year  = pd.Timestamp.now().year
partial_years = nat_ref[nat_ref["partial"] == True]["year"].tolist() if "partial" in nat_ref.columns else []
has_wind      = wind_available(hourly)

# Asset upload
asset_ann  = None
asset_name = cfg["label"] + " Asset"
asset_raw  = None

if uploaded and sb_date_col and sb_prod_col:
    try:
        raw = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
               else pd.read_excel(uploaded))
        raw[sb_date_col] = pd.to_datetime(raw[sb_date_col], errors="coerce")
        raw[sb_prod_col] = (raw[sb_prod_col].astype(str)
                            .str.replace(" ", "").str.replace("-", "0").str.replace(",", "."))
        raw[sb_prod_col] = pd.to_numeric(raw[sb_prod_col], errors="coerce").fillna(0.0)
        if sb_unit == "kWh":
            raw[sb_prod_col] = raw[sb_prod_col] / 1000
        asset_raw  = raw[[sb_date_col, sb_prod_col]].rename(
            columns={sb_date_col: "Date", sb_prod_col: "Prod_MWh"})
        asset_ann  = compute_asset_annual(hourly, asset_raw.copy(), prod_col=cfg["prod_col"])
        asset_name = uploaded.name.rsplit(".", 1)[0]
        st.sidebar.success(f"Loaded: {asset_name}")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

has_asset = asset_ann is not None and len(asset_ann) >= 2

nat_ref_complete = nat_ref[nat_ref["partial"] == False] if "partial" in nat_ref.columns else nat_ref

# Apply year range filter to national reference
nat_ref          = nat_ref[nat_ref["year"].between(yr_range[0], yr_range[1])]
nat_ref_complete = nat_ref_complete[nat_ref_complete["year"].between(yr_range[0], yr_range[1])]

# Regression — two slopes: asset and national
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

# Active slope based on radio
if reg_basis == "Asset" and has_asset:
    sl_u, ic_u, r2_u = sl_ast, ic_ast, r2_ast
else:
    sl_u, ic_u, r2_u = sl_nat_u, ic_nat_u, r2_nat_u

last_yr_complete = int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else int(nat_ref["year"].max())
last_yr_proj = int(asset_ann["Year"].max()) if has_asset else last_yr_complete

# Anchor for projection — last asset CP% value
anchor_val = asset_ann["cp_pct"].iloc[-1] if has_asset else None

# Shape discount series
if has_asset:
    hist_sd   = asset_ann["shape_disc"].dropna()
    hist_sd_f = asset_ann[asset_ann["Year"] != 2022]["shape_disc"].dropna() if ex22 else hist_sd
else:
    hist_sd   = get_nat_sd(nat_ref_complete, cfg["nat_sd"])
    nc_ex22   = nat_ref_complete[nat_ref_complete["year"] != 2022] if ex22 else nat_ref_complete
    hist_sd_f = get_nat_sd(nc_ex22, cfg["nat_sd"])

if len(hist_sd_f) == 0:
    hist_sd_f = nat_ref_complete["shape_disc"].dropna()

sd_ch   = float(np.percentile(hist_sd_f, chosen_pct)) if len(hist_sd_f) > 0 else 0.15
vol_mwh = asset_ann["prod_mwh"].mean() if has_asset else 52000.0

# Projection — anchored on last asset point
proj = project_cp(sl_u, ic_u, last_yr_proj, proj_n, anchor_val=anchor_val)

# Forward curve
fwd_df    = pd.DataFrame([{"year": yr, "forward": float(DEFAULT_FWD.get(yr, 52.0))}
                          for yr in range(last_yr_proj+1, last_yr_proj+proj_n+1)])
fwd_curve = dict(zip(fwd_df["year"], fwd_df["forward"]))
ref_fwd   = fwd_df["forward"].iloc[0] if len(fwd_df) > 0 else 55.0

pricing   = compute_ppa(ref_fwd, sd_ch, imb_eur, add_disc)
ppa       = pricing["ppa"]

pcts    = list(range(1, 101))
sd_vals = [float(np.percentile(hist_sd_f, p)) if len(hist_sd_f) > 0 else 0.15 for p in pcts]
cp_vals = [ref_fwd * (1-s) for s in sd_vals]
pnl_v   = compute_pnl_curve(ref_fwd, ppa, vol_mwh, sd_vals)
be      = next((p for p, v in zip(pcts, pnl_v) if v < 0), None)

scenarios = compute_scenarios(ref_fwd, ppa, vol_mwh, hist_sd_f, proj_n, vol_stress, spot_stress)

nat_cp_list      = nat_series(nat_ref,          cfg["nat_cp"],  "cp_nat_pct")
nat_eur_list     = nat_series(nat_ref,          cfg["nat_eur"],  "cp_nat")
nat_cp_complete  = nat_series(nat_ref_complete, cfg["nat_cp"],  "cp_nat_pct")
nat_eur_complete = nat_series(nat_ref_complete, cfg["nat_eur"], "cp_nat")

wind_ready    = techno == "Wind" and has_wind
prod_col_roll = cfg["prod_col"] if (techno == "Solar" or wind_ready) else "NatMW"

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview", "Forward Curve & Pricing", "Market Dynamics",
    "Sensitivity & Scenarios", "Price Waterfall", "Market Evolution",
    "Export & SPOT Extractor",
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

    ca, cb = st.columns([3, 1])
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

    if techno == "Wind" and not has_wind:
        status_msg("Wind data (WindMW) not yet in hourly_spot.csv — "
                   "run the updated ENTSO-E script (B18+B19). Solar shown as fallback.", kind="wind")
    else:
        status_msg("Automatic daily updates via GitHub Actions — ENTSO-E France data.")

    st.markdown("---")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        ppa_card(f"PPA Price (P{chosen_pct})", f"{ppa:.2f}")
    with k2:
        # Average projected CP% over tenor period
        proj_tenor = proj[proj["year"].between(tenor_start, tenor_end)]
        cp_proj_avg = proj_tenor["p50"].mean() * 100 if len(proj_tenor) > 0 else cp_l
        c_kpi = C2 if cp_proj_avg > 80 else (C4 if cp_proj_avg > 65 else C5)
        kpi_card(f"Capture Rate — {tenor_start}-{tenor_end}",
                 f"{cp_proj_avg:.0f}%", color=c_kpi)
    with k3:
        sd_proj_avg = (1 - proj_tenor["p50"].mean()) * 100 if len(proj_tenor) > 0 else sd_cur
        c_sd = C5 if sd_proj_avg > 25 else (C3 if sd_proj_avg > 15 else C2)
        kpi_card("Shape Discount", f"{sd_proj_avg:.1f}%", color=c_sd, extra_cls="kpi-gold")
    with k4:
        p50_pnl = (vol_mwh * (ref_fwd * (1 - float(np.percentile(hist_sd_f, 50))) - ppa) / 1000
                   if len(hist_sd_f) > 0 else 0)
        c_p = C2 if p50_pnl > 0 else C5
        kpi_card("P&L P50 (k EUR/yr)", f"{p50_pnl:+.0f}k", color=c_p)
    with k5:
        be_txt = f"P{be}" if be else ">P100"
        c_be   = C2 if be and be > 70 else C5
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
                             reg_basis=reg_basis, anchor_val=anchor_val),
            use_container_width=True)

    st.markdown("---")
    section(f"Reference Table — {cfg['label']} Shape Discount and P&L by Percentile")
    desc("Complete years only — YTD excluded. P74 = WPD tender reference.")
    nat_sd_tbl = get_nat_sd(nat_ref_complete, cfg["nat_sd"])
    kp = [5,10,15,20,25,30,35,40,45,50,55,60,65,70,74,75,80,85,90,95,100]
    trows = []
    for p in kp:
        sdn  = float(np.percentile(nat_sd_tbl, p)) if len(nat_sd_tbl) > 0 else 0.15
        sda  = float(np.percentile(asset_ann["shape_disc"].dropna(), p)) if has_asset else None
        cpa  = ref_fwd * (1 - sda) if sda is not None else None
        pnla = vol_mwh * (cpa - ppa) / 1000 if cpa is not None else None
        row  = {"Pct": f"P{p}",
                "Shape Disc Nat.": f"{sdn*100:.1f}%",
                "CP Nat.":         f"{(1-sdn)*100:.0f}%"}
        if has_asset:
            row["Shape Disc Asset"] = f"{sda*100:.1f}%"
            row["CP Asset"]         = f"{(1-sda)*100:.0f}%"
            row["P&L k EUR/yr"]     = f"{pnla:+.0f}k"
        trows.append(row)
    tdf = pd.DataFrame(trows)
    def _hi(row):
        p = int(row["Pct"][1:])
        if p == chosen_pct: return [f"background-color:{C2};color:white;font-weight:bold"] * len(row)
        if p in [10,50,90]:  return [f"background-color:{C2L}"] * len(row)
        if p == 74:           return [f"background-color:{C3L}"] * len(row)
        return [""] * len(row)
    st.dataframe(tdf.style.apply(_hi, axis=1), use_container_width=True, height=440)

    # ── Production Profile (4 charts) ─────────────────────────────────────────
    st.markdown("---")
    section(f"Production Profile — National vs Asset")
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
                                     cfg["color"], asset_name, has_asset,
                                     partial_years),
            use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Forward Curve & Pricing
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    section("EEX Forward Curve — by Calendar Year")
    desc(f"PPA = Forward x (1 - {cfg['label']} Shape Disc - Imbalance%) - Imbalance EUR.")
    col_i, col_r = st.columns([1, 1.6])
    with col_i:
        fwd_rows_live = []
        for yr in range(last_yr_proj+1, last_yr_proj+proj_n+1):
            px = st.number_input(f"CAL {yr} (EUR/MWh)", 10.0, 200.0,
                                 float(DEFAULT_FWD.get(yr, 52.0)), 0.5, key=f"fwd_{yr}")
            fwd_rows_live.append({"year": yr, "forward": px})
        fwd_df_live = pd.DataFrame(fwd_rows_live)
        st.info("API connector coming soon.")
    with col_r:
        rows_ppa = []
        for _, row in fwd_df_live.iterrows():
            fsd    = ic_u + sl_u * row["year"]
            cp     = row["forward"] * (1 - fsd)
            ppa_yr = row["forward"] * (1 - fsd - imb_eur / row["forward"]) - imb_eur
            rows_ppa.append({"Year": int(row["year"]),
                             "Forward": f"{row['forward']:.2f}",
                             f"{cfg['label']} Proj. SD": f"{fsd*100:.1f}%",
                             "Captured (EUR/MWh)": f"{cp:.2f}",
                             "PPA Price (EUR/MWh)": f"{ppa_yr:.2f}",
                             "P&L/MWh": f"{cp-ppa_yr:+.2f}"})
        st.dataframe(pd.DataFrame(rows_ppa), use_container_width=True, hide_index=True)
    st.plotly_chart(chart_forward(fwd_df_live), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Market Dynamics
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    section("Negative Price Hours — by Year")
    desc("Hours with day-ahead price < 0. Trend line excludes YTD. CRE threshold: 15h/yr.")
    st.plotly_chart(chart_neg_hours(hourly, partial_years, cfg["color"]),
                    use_container_width=True)

    st.markdown("---")
    c3a, c3b = st.columns(2)
    with c3a:
        section(f"Monthly Cannibalization Profile — {cfg['label']}")
        desc("Average shape discount by calendar month. Error bars = year-to-year std dev.")
        fig_mo, monthly_agg = chart_monthly_profile(hourly, cfg["prod_col"],
                                                     cfg["color"], cfg["label"])
        st.plotly_chart(fig_mo, use_container_width=True)
    with c3b:
        section(f"CP% vs National {cfg['label']} Capacity")
        desc("Each point = one year. X-axis = average national installed capacity (MW).")
        st.plotly_chart(
            chart_scatter_cp_vs_capacity(nat_ref, hourly, cfg["prod_col"], cfg["nat_cp"],
                                          cfg["color"], cfg["label"], partial_years,
                                          techno == "Solar"),
            use_container_width=True)

    st.markdown("---")
    section(f"Annual Shape Discount Change — {cfg['label']}")
    desc("Year-on-year delta in shape discount (pp). Positive = more cannibalization.")
    st.plotly_chart(chart_shape_disc_delta(nat_ref, cfg["nat_sd"], cfg["color"], cfg["label"]),
                    use_container_width=True)

    st.markdown("---")
    section(f"Heatmap — Monthly Shape Discount by Year — {cfg['label']}")
    desc("Shape discount by month and year. Darker = higher cannibalization.")
    st.plotly_chart(chart_heatmap(monthly_agg, cfg["color"], cfg["label"]),
                    use_container_width=True)

    st.markdown("---")
    st.markdown(f'<div class="section-title">Market Value Analysis — Jomaux / GEM Energy Analytics</div>',
                unsafe_allow_html=True)
    section(f"Market Value vs {cfg['label']} Generation Output")
    desc(f"Average day-ahead price per MW bin. Cannibalization mechanism. "
         f"Method: GEM Energy Analytics 'The decreasing market value of renewables' (Oct 2024).")
    st.plotly_chart(
        chart_market_value_vs_penetration(hourly, cfg["prod_col"], cfg["color"],
                                           cfg["label"], partial_years),
        use_container_width=True)

    st.markdown("---")
    j1, j2 = st.columns(2)
    with j1:
        season_lbl = "Apr-Sep" if cfg["duck_months"] == list(range(4,10)) else "All months"
        section(f"Duck / Canyon Curve — {cfg['label']} ({season_lbl})")
        desc("Normalised day-ahead prices by hour of day, one line per year. "
             "Normalisation: each hour / monthly average. "
             "Method: GEM Energy Analytics 'The duck is growing' (Mar 2025).")
        st.plotly_chart(
            chart_duck_curve(hourly, cfg["color"], cfg["label"], cfg["duck_months"]),
            use_container_width=True)
    with j2:
        section(f"Canyon Curve — Last 4 Years ({cfg['label']})")
        desc("Same normalisation, last 4 complete years only. Grey = older, colour = most recent.")
        st.plotly_chart(
            chart_canyon_curve(hourly, cfg["color"], cfg["label"],
                               cfg["duck_months"], recent_years=4),
            use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Sensitivity & Scenarios
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    section(f"Annual P&L by Cannibalization Percentile — {cfg['label']}")
    desc(f"P&L = (Captured Price - PPA Price) x Volume. Shaded = +/-{vol_stress}% volume stress.")
    st.plotly_chart(
        chart_pnl_percentile(pcts, pnl_v, cp_vals, ppa, vol_mwh,
                              chosen_pct, vol_stress, be, cfg["label"]),
        use_container_width=True)
    if be:
        st.warning(f"Break-even at P{be}.")

    st.markdown("---")
    section(f"Stress Scenarios — Cumulative P&L over {proj_n} Years")
    desc("P50 bars. Triangles = P10 (down) / P90 (up).")
    st.plotly_chart(chart_scenarios(scenarios, proj_n, cfg["label"]), use_container_width=True)

    st.markdown("---")
    section("Scenario Details")
    st.dataframe(
        pd.DataFrame([{"Scenario": s["Scenario"],
                       "P10 (k EUR)": f"{s['p10']:+.0f}k",
                       "P50 (k EUR)": f"{s['p50']:+.0f}k",
                       "P90 (k EUR)": f"{s['p90']:+.0f}k"} for s in scenarios]),
        use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Price Waterfall
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    section(f"PPA Price Waterfall — {cfg['label']} Component Breakdown")
    desc("Waterfall from baseload forward to final PPA price.")
    st.plotly_chart(chart_waterfall(ref_fwd, sd_ch, imb_eur, cfg["label"]),
                    use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Market Evolution
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown(f"## Market Evolution — Rolling Capture Rate ({cfg['label']})")
    if techno == "Wind" and not has_wind:
        status_msg("Wind data not yet available — run the ENTSO-E update script. "
                   "Solar rolling M0 shown as fallback.", kind="wind")
    desc(f"Rolling M0 on RAW hourly data. "
         f"M0(t) = sum({prod_col_roll} x Spot) / sum({prod_col_roll}) over last N days.")

    with st.spinner("Computing rolling windows — please wait..."):
        roll = compute_rolling_m0(
        hourly[["Date", "Spot", prod_col_roll]].copy(),
        prod_col=prod_col_roll,
        windows=(30, 90, 365)
        )(hourly, prod_col=prod_col_roll, windows=(30, 90, 365))

    if roll is None or len(roll) < 10:
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
            chart_rolling_eur(roll, nat_ref_complete, nat_eur_complete,
                               cfg["color"], cfg["label"]),
            use_container_width=True)

        st.markdown("---")
        section("Recent Period Summary")
        latest  = pd.to_datetime(hourly["Date"]).max().normalize()
        sum_rows = []
        for w in [30, 90, 365]:
            cutoff  = latest - pd.Timedelta(days=w)
            h_slice = hourly[pd.to_datetime(hourly["Date"]).dt.normalize() > cutoff]
            if len(h_slice) < w * 12: continue
            sum_rev  = (h_slice[prod_col_roll] * h_slice["Spot"]).sum()
            sum_prod = h_slice[prod_col_roll].sum()
            bl_val   = h_slice["Spot"].sum() / len(h_slice)
            m0_val   = sum_rev / sum_prod if sum_prod > 0 else np.nan
            cp_val   = m0_val / bl_val if bl_val else np.nan
            sum_rows.append({"Window": f"Last {w} days",
                             "From": cutoff.strftime("%d/%m/%Y"),
                             "To":   latest.strftime("%d/%m/%Y"),
                             "Baseload (EUR/MWh)":    f"{bl_val:.2f}",
                             "M0 Captured (EUR/MWh)": f"{m0_val:.2f}",
                             "Capture Rate":          f"{cp_val*100:.1f}%",
                             "Shape Discount":        f"{(1-cp_val)*100:.1f}%"})
        if sum_rows:
            def _hi_sum(row):
                if "365" in row["Window"]: return [f"background-color:{C2L}"] * len(row)
                if "90"  in row["Window"]: return [f"background-color:{C3L}"] * len(row)
                return [""] * len(row)
            st.dataframe(pd.DataFrame(sum_rows).style.apply(_hi_sum, axis=1),
                         use_container_width=True, hide_index=True)

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
    uploaded_conv = st.file_uploader("Upload file to convert", type=["xlsx","csv","xls"],
                                      key="converter")
    if uploaded_conv:
        try:
            df_conv = (pd.read_csv(uploaded_conv) if uploaded_conv.name.endswith(".csv")
                       else pd.read_excel(uploaded_conv))
            st.markdown(f"**{len(df_conv):,} rows — {len(df_conv.columns)} columns detected**")
            st.dataframe(df_conv.head(5), use_container_width=True)
            cols = df_conv.columns.tolist()
            c1, c2 = st.columns(2)
            with c1:
                date_col = st.selectbox("Date column", cols, key="conv_date")
            with c2:
                prod_col_conv = st.selectbox("Production column (MWh or kWh)", cols, key="conv_prod")
            unit = st.radio("Unit of production column", ["MWh","kWh"], horizontal=True, key="conv_unit")
            if st.button("Convert", key="conv_btn"):
                out = df_conv[[date_col, prod_col_conv]].copy()
                out.columns = ["Date","Prod_MWh"]
                out["Date"]     = pd.to_datetime(out["Date"], errors="coerce")
                out["Prod_MWh"] = pd.to_numeric(out["Prod_MWh"], errors="coerce")
                if unit == "kWh":
                    out["Prod_MWh"] = out["Prod_MWh"] / 1000
                out = out.dropna(subset=["Date","Prod_MWh"])
                out = out.sort_values("Date").reset_index(drop=True)
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
                    df_out = pd.DataFrame({"Spot": prices}).reset_index()
                    df_out.columns  = ["Date","Spot"]
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
                    st.download_button("Download CSV",
                                       data=df_out.to_csv(index=False).encode("utf-8"),
                                       file_name=f"spot_{country_c}_{d_start}_{d_end}.csv",
                                       mime="text/csv")
                except ImportError: st.error("entsoe-py not installed.")
                except Exception as e: st.error(f"ENTSO-E Error: {e}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
ytd_note = " — 2026 YTD included (excl. regression)" if partial_years else ""
st.markdown(
    f'<span style="font-size:12px;color:#888;font-family:Calibri,Arial,sans-serif;">'
    f'v2.4 — ENTSO-E France {data_start.year}–{data_end.strftime("%Y-%m-%d")} '
    f'— {len(hourly):,} hours{ytd_note} — Technology: {cfg["label"]} — '
    f'Regression: {reg_basis} — Year range: {yr_range[0]}–{yr_range[1]}'
    f'</span>', unsafe_allow_html=True)
