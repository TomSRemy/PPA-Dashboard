"""
tab_market_dynamics.py — KAL-EL PPA Dashboard
Tab 3 — Market Dynamics: neg hours, profiles, duck curve.
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

from charts import chart_neg_hours, chart_monthly_profile, chart_scatter_cp_vs_capacity, chart_shape_disc_delta, chart_heatmap, chart_market_value_vs_penetration, chart_duck_curve, chart_canyon_curve


def render_tab_market_dynamics(**ctx):
    # Unpack context
    locals().update(ctx)

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