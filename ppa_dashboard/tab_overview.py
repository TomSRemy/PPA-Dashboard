"""
tab_overview.py — KAL-EL PPA Dashboard
Tab 1 — Overview: historical CP, projection, profiles.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from theme import (
    C1, C2, C3, C4, C5, C2L, C3L, WHT,
    ACCENT_PRIMARY, ACCENT_WARN, ACCENT_NEG, TEXT_DARK, TEXT_MUTED,
    CHART_H_XS, CHART_H_SM, CHART_H_MD, CHART_H_LG, CHART_H_XL,
)
from ui import section, desc, status_msg, ppa_card, kpi_card, tech_badge, plotly_base

from compute import compute_ppa


def render_tab_overview(**ctx):
    # Unpack context
    locals().update(ctx)

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