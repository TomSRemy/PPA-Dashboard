"""
tab_ppa_pricing.py — KAL-EL PPA Dashboard
Tab 2 — PPA Pricing: forward curve, waterfall, premiums.
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

from config import DEFAULT_FWD
from compute import compute_ppa
from charts import chart_forward, chart_waterfall


def render_tab_ppa_pricing(**ctx):
    # Unpack context
    locals().update(ctx)

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