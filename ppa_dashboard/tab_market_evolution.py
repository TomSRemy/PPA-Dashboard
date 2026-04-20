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


def render_tab_market_evolution(**ctx):
    # Unpack context
    locals().update(ctx)

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