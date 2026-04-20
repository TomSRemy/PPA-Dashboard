"""
tab_market_evolution.py — KAL-EL PPA Dashboard
Tab 4 — Market Evolution: rolling M0 capture rate.
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

from data import compute_rolling_m0
from charts import chart_rolling_cp, chart_rolling_eur


def render_tab_market_evolution(ctx):
    # Unpack context dict
    nat_ref          = ctx.get("nat_ref")
    nat_ref_complete = ctx.get("nat_ref_complete")
    hourly           = ctx.get("hourly")
    asset_ann        = ctx.get("asset_ann")
    asset_raw        = ctx.get("asset_raw")
    has_asset        = ctx.get("has_asset")
    has_wind         = ctx.get("has_wind")
    wind_ready       = ctx.get("wind_ready")
    techno           = ctx.get("techno")
    cfg              = ctx.get("cfg")
    asset_name       = ctx.get("asset_name")
    sl_u             = ctx.get("sl_u")
    ic_u             = ctx.get("ic_u")
    r2_u             = ctx.get("r2_u")
    reg_basis        = ctx.get("reg_basis")
    ppa              = ctx.get("ppa")
    pricing          = ctx.get("pricing")
    ref_fwd          = ctx.get("ref_fwd")
    sd_ch            = ctx.get("sd_ch")
    imb_eur          = ctx.get("imb_eur")
    add_disc         = ctx.get("add_disc")
    vol_risk_pct     = ctx.get("vol_risk_pct")
    price_risk_pct   = ctx.get("price_risk_pct")
    goo_value        = ctx.get("goo_value")
    margin           = ctx.get("margin")
    nat_cp_list      = ctx.get("nat_cp_list")
    nat_eur_list     = ctx.get("nat_eur_list")
    nat_cp_complete  = ctx.get("nat_cp_complete")
    nat_eur_complete = ctx.get("nat_eur_complete")
    hist_sd_f        = ctx.get("hist_sd_f")
    sd_vals          = ctx.get("sd_vals")
    pnl_v            = ctx.get("pnl_v")
    scenarios        = ctx.get("scenarios")
    proj             = ctx.get("proj")
    proj_n           = ctx.get("proj_n")
    last_yr_proj     = ctx.get("last_yr_proj")
    anchor_val       = ctx.get("anchor_val")
    chosen_pct       = ctx.get("chosen_pct")
    vol_stress       = ctx.get("vol_stress")
    spot_stress      = ctx.get("spot_stress")
    partial_years    = ctx.get("partial_years")
    current_year     = ctx.get("current_year")
    data_start       = ctx.get("data_start")
    data_end         = ctx.get("data_end")
    tenor_start      = ctx.get("tenor_start")
    tenor_end        = ctx.get("tenor_end")
    fwd_df           = ctx.get("fwd_df")
    fwd_curve        = ctx.get("fwd_curve")
    fig_cap_link     = ctx.get("fig_cap_link")
    proj_targets     = ctx.get("proj_targets")
    vol_mwh          = ctx.get("vol_mwh")
    be               = ctx.get("be")
    prod_col_roll    = ctx.get("prod_col_roll")
    plotly_base      = ctx.get("plotly_base")
    yr_range         = ctx.get("yr_range", (2020, 2026))
    ex22             = ctx.get("ex22", False)
    get_nat_sd       = ctx.get("_get_nat_sd")
    build_excel      = ctx.get("_build_excel")
    load_balancing   = ctx.get("_load_balancing")
    load_market_prices = ctx.get("_load_market_prices")
    load_xborder_da  = ctx.get("_load_xborder_da")
    load_fcr         = ctx.get("_load_fcr")
    load_hourly      = ctx.get("_load_hourly")

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