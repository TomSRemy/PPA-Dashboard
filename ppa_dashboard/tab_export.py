"""
tab_export.py — KAL-EL PPA Dashboard
Tab 7 — Export: Excel, load curve converter, ENTSO-E extractor.
"""
import streamlit as st
import pandas as pd
import numpy as np

from theme import C1, C2, C3, C4, C5, C2L, C3L, WHT
from data import get_nat_sd
from excel import build_excel
from ui import section, desc, status_msg, ppa_card, kpi_card, tech_badge, plotly_base


def render_tab_export(ctx):
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