"""
tab_market_dynamics.py — KAL-EL PPA Dashboard
Tab 3 — Market Dynamics: neg hours, profiles, duck curve.
"""
import streamlit as st
import pandas as pd
import numpy as np

from theme import C1, C2, C3, C4, C5, C2L, C3L, WHT
from ui import section, desc, status_msg, ppa_card, kpi_card, tech_badge, plotly_base
from charts import (
    chart_neg_hours, chart_monthly_profile, chart_shape_disc_delta,
    chart_heatmap, chart_market_value_vs_penetration,
    chart_duck_curve, chart_canyon_curve,
)

def render_tab_market_dynamics(ctx):
    # Unpack context
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
    yr_range         = ctx.get("yr_range", (2020, 2026))
    ex22             = ctx.get("ex22", False)
    get_nat_sd       = ctx.get("_get_nat_sd")
    build_excel      = ctx.get("_build_excel")
    load_balancing   = ctx.get("_load_balancing")
    load_market_prices = ctx.get("_load_market_prices")
    load_xborder_da  = ctx.get("_load_xborder_da")
    load_fcr         = ctx.get("_load_fcr")
    load_hourly      = ctx.get("_load_hourly")

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