"""
tab_market_overview.py — KAL-EL PPA Dashboard
Tab 6 — Market Overview: FR spot, commodities, imbalance, ancillary.
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

from charts import (mk_kpis, mk_chart_spot, mk_table_spot, mk_chart_spread, mk_table_spread, mk_chart_neg_bars, mk_chart_neg_calendar, mk_chart_distribution, mk_chart_eua, mk_chart_ttf, mk_chart_brent, mk_table_commodity, mk_chart_renewables_lines, mk_chart_renewables_mix, mk_chart_renewables_hourly, mk_chart_imb_pos_neg, mk_chart_imb_spread, mk_chart_imb_vs_da, mk_table_imbalance, mk_chart_fcr, mk_chart_afrr, mk_chart_europe_map, mk_chart_country_history, _mk_stub, MK_ZOOM_OPTS, MK_PURPLE, MK_BLUE, MK_GREEN)


def render_tab_market_overview(**ctx):
    # Unpack context
    locals().update(ctx)

    st.markdown("## Market Overview — France Power Market")

    # ── Data loading ─────────────────────────────────────────────────────────
    hourly_full = load_hourly()
    bal         = load_balancing()
    xb          = load_xborder_da()
    fcr         = load_fcr()
    mkt         = load_market_prices()

    has_bal = bal is not None and len(bal) > 0
    has_xb  = xb  is not None and len(xb)  > 0
    has_fcr = fcr is not None and len(fcr)  > 0
    has_mkt = mkt is not None and len(mkt)  > 0

    # ── Global time filter ───────────────────────────────────────────────────
    st.markdown("#### Global time window")
    g_zoom = st.radio("", MK_ZOOM_OPTS, index=3, horizontal=True, key="mk_global_zoom")
    st.caption("Each chart also has its own local filter — override the global window per chart.")
    st.markdown("---")

    # ── Helper: local zoom selector ───────────────────────────────────────────
    def local_zoom(key: str, default: str = None) -> str:
        idx = MK_ZOOM_OPTS.index(default or g_zoom)
        return st.radio("", MK_ZOOM_OPTS, index=idx, horizontal=True, key=key)

    # ════════════════════════════════════════════════════════════════════════
    # ROW 1 — KPIs
    # ════════════════════════════════════════════════════════════════════════
    section("Key Market Indicators")
    kpis = mk_kpis(hourly_full, bal if has_bal else None, mkt if has_mkt else None)

    def _kpi_delta(val, prev, unit="", pct=True):
        if val != val or prev != prev or prev == 0:
            return ""
        d   = val - prev
        dp  = d / abs(prev) * 100
        col = C2 if d >= 0 else C5
        arr = "▲" if d >= 0 else "▼"
        txt = f"{arr} {dp:+.1f}%" if pct else f"{arr} {d:+.1f}{unit}"
        return f'<span style="font-size:11px;color:{col};font-weight:700">{txt} vs prev 7D</span>'

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        v = kpis.get("da_7d", float("nan"))
        kpi_card("DA Spot — 7D avg", f"{v:.1f} €/MWh" if v==v else "N/A", color=C1)
        st.markdown(_kpi_delta(v, kpis.get("da_7d_prev", float("nan")), " €/MWh", pct=False),
                    unsafe_allow_html=True)
    with k2:
        v = kpis.get("da_30d", float("nan"))
        kpi_card("DA Spot — 30D avg", f"{v:.1f} €/MWh" if v==v else "N/A", color=C1)
    with k3:
        v = kpis.get("spread_7d", float("nan"))
        kpi_card("DA Spread — 7D avg", f"{v:.1f} €/MWh" if v==v else "N/A",
                 color=C5 if v==v and v>100 else C2)
        st.markdown('<span style="font-size:10px;color:#888">max−min daily</span>',
                    unsafe_allow_html=True)
    with k4:
        v = kpis.get("afrr_7d", float("nan"))
        kpi_card("aFRR — 7D avg", f"{v:.1f} €/MWh" if v==v else "N/A", color=MK_PURPLE)
    with k5:
        v = kpis.get("eua_last", float("nan"))
        kpi_card("EUA Carbon", f"{v:.1f} €/tCO2" if v==v else "N/A", color=MK_BLUE)
        st.markdown(_kpi_delta(v, kpis.get("eua_7d_prev", float("nan")), " €/tCO2", pct=True),
                    unsafe_allow_html=True)

    k6, k7, k8, k9, k10 = st.columns(5)
    with k6:
        v = kpis.get("solar_7d", float("nan"))
        kpi_card("Solar — 7D avg", f"{v:.0f} MW" if v==v else "N/A", color=C3, extra_cls="kpi-gold")
        st.markdown(_kpi_delta(v, kpis.get("solar_7d_prev", float("nan")), " MW", pct=True),
                    unsafe_allow_html=True)
    with k7:
        v = kpis.get("wind_7d", float("nan"))
        kpi_card("Wind — 7D avg", f"{v:.0f} MW" if v==v else "N/A", color=C2)
        st.markdown(_kpi_delta(v, kpis.get("wind_7d_prev", float("nan")), " MW", pct=True),
                    unsafe_allow_html=True)
    with k8:
        v = kpis.get("ttf_last", float("nan"))
        kpi_card("TTF Gas", f"{v:.1f} €/MWh" if v==v else "N/A", color=C4)
        st.markdown(_kpi_delta(v, kpis.get("ttf_7d_prev", float("nan")), " €/MWh", pct=True),
                    unsafe_allow_html=True)
    with k9:
        v = kpis.get("brent_last", float("nan"))
        kpi_card("Brent Oil", f"{v:.1f} $/bbl" if v==v else "N/A", color=MK_GREEN)
        st.markdown(_kpi_delta(v, kpis.get("brent_7d_prev", float("nan")), " $/bbl", pct=True),
                    unsafe_allow_html=True)
    with k10:
        v = kpis.get("da_7d", float("nan"))
        neg_h = int((hourly_full["Spot"] < 0).sum()) if hourly_full is not None and "Spot" in hourly_full.columns else 0
        kpi_card("Neg hours — YTD", f"{neg_h:,} h", color=C5 if neg_h > 200 else C4)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 2 — FR DA Spot (main chart)
    # ════════════════════════════════════════════════════════════════════════
    section("FR Day-Ahead Spot Price")
    desc("Hourly or daily average. Daily mode adds 7D and 30D rolling averages.")
    mode = st.radio("Display mode", ["Hourly", "Daily average"], index=1,
                    horizontal=True, key="mk_spot_mode")
    z = local_zoom("mk_spot_zoom")
    sc, tc = st.columns([3, 1])
    with sc:
        st.plotly_chart(mk_chart_spot(hourly_full, z, mode), use_container_width=True)
    with tc:
        st.markdown("##### Statistics")
        st.plotly_chart(mk_table_spot(hourly_full, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 3 — DA Spread
    # ════════════════════════════════════════════════════════════════════════
    section("DA Daily Spread")
    desc("Daily max−min + 30D rolling average. Measures intraday arbitrage potential.")
    z = local_zoom("mk_spread_zoom")
    sc, tc = st.columns([3, 1])
    with sc:
        st.plotly_chart(mk_chart_spread(hourly_full, z), use_container_width=True)
    with tc:
        st.markdown("##### Statistics")
        st.plotly_chart(mk_table_spread(hourly_full, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 4 — Negative price hours
    # ════════════════════════════════════════════════════════════════════════
    section("Negative DA Price Hours")
    desc("Daily bars + calendar heatmap. Red = high negative hour count.")
    z = local_zoom("mk_neg_zoom")
    st.plotly_chart(mk_chart_neg_bars(hourly_full, z), use_container_width=True)
    st.plotly_chart(mk_chart_neg_calendar(hourly_full, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 5 — Distribution
    # ════════════════════════════════════════════════════════════════════════
    section("DA Spot Price Distribution")
    desc("Histogram of hourly prices. Mean and median shown at different heights to avoid overlap.")
    z = local_zoom("mk_dist_zoom")
    st.plotly_chart(mk_chart_distribution(hourly_full, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 6 — Market drivers (one per row)
    # ════════════════════════════════════════════════════════════════════════
    section("Market Drivers")

    st.markdown("#### Carbon Price (EUA)")
    desc("EUA daily futures (€/tCO2). Source: Ember Climate. Includes 7D and 30D rolling avg.")
    z = local_zoom("mk_eua_zoom")
    sc, tc = st.columns([3, 1])
    with sc:
        st.plotly_chart(mk_chart_eua(mkt if has_mkt else None, z), use_container_width=True)
    with tc:
        st.markdown("##### Statistics")
        st.plotly_chart(mk_table_commodity(mkt, "EUA_EUR_tCO2", "€/tCO2")
                        if has_mkt else _mk_stub("","no data"), use_container_width=True)

    st.markdown("#### TTF Gas Price")
    desc("TTF front-month (€/MWh). Source: Yahoo Finance. Primary marginal cost driver for FR power.")
    z = local_zoom("mk_ttf_zoom")
    sc, tc = st.columns([3, 1])
    with sc:
        st.plotly_chart(mk_chart_ttf(mkt if has_mkt else None, z), use_container_width=True)
    with tc:
        st.markdown("##### Statistics")
        st.plotly_chart(mk_table_commodity(mkt, "TTF_EUR_MWh", "€/MWh")
                        if has_mkt else _mk_stub("","no data"), use_container_width=True)

    st.markdown("#### Brent Crude Oil")
    desc("Brent front-month ($/bbl). Source: Yahoo Finance.")
    z = local_zoom("mk_brent_zoom")
    sc, tc = st.columns([3, 1])
    with sc:
        st.plotly_chart(mk_chart_brent(mkt if has_mkt else None, z), use_container_width=True)
    with tc:
        st.markdown("##### Statistics")
        st.plotly_chart(mk_table_commodity(mkt, "Brent_USD_bbl", "$/bbl")
                        if has_mkt else _mk_stub("","no data"), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 7 — Renewable generation
    # ════════════════════════════════════════════════════════════════════════
    section("Renewable Generation")

    st.markdown("#### Wind & Solar — Daily Trend")
    desc("Daily average + 7D rolling. Separate lines for Wind and Solar.")
    z = local_zoom("mk_ren_lines_zoom")
    st.plotly_chart(mk_chart_renewables_lines(hourly_full, z), use_container_width=True)

    st.markdown("#### Generation Mix — Stacked Area")
    desc("Wind + Solar stacked. Resampled to 6h when zoomed out.")
    z = local_zoom("mk_ren_mix_zoom")
    st.plotly_chart(mk_chart_renewables_mix(hourly_full, z), use_container_width=True)

    st.markdown("#### Raw Hourly Generation")
    desc("Actual hourly MW — no averaging. Best used on 7D or 1M window.")
    z = local_zoom("mk_ren_hourly_zoom", default="7D")
    st.plotly_chart(mk_chart_renewables_hourly(hourly_full, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 8 — Imbalance (one per row)
    # ════════════════════════════════════════════════════════════════════════
    section("Flexibility & Imbalance Markets")
    if not has_bal:
        st.warning("balancing_prices.csv not found — run the ENTSO-E balancing script.")
    else:
        st.markdown("#### Imbalance Prices — Positive vs Negative")
        desc("Daily average. Gap between lines = system asymmetry and imbalance risk.")
        z = local_zoom("mk_imb_pn_zoom")
        sc, tc = st.columns([3, 1])
        with sc:
            st.plotly_chart(mk_chart_imb_pos_neg(bal, z), use_container_width=True)
        with tc:
            st.markdown("##### Statistics")
            st.plotly_chart(mk_table_imbalance(bal, z), use_container_width=True)

        st.markdown("#### Imbalance Spread (Positive − Negative)")
        desc("Measures imbalance market depth. Higher = more volatile system.")
        z = local_zoom("mk_imb_spread_zoom")
        st.plotly_chart(mk_chart_imb_spread(bal, z), use_container_width=True)

        st.markdown("#### Imbalance vs Day-Ahead")
        desc("Imb Pos − DA and Imb Neg − DA. Negative leg below DA = double penalty for short producers.")
        z = local_zoom("mk_imb_da_zoom")
        st.plotly_chart(mk_chart_imb_vs_da(bal, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 9 — Ancillary services
    # ════════════════════════════════════════════════════════════════════════
    section("Ancillary Services")

    st.markdown("#### FCR — Frequency Containment Reserve (France)")
    desc("Contracted capacity price (€/MW/day). Source: ENTSO-E.")
    z = local_zoom("mk_fcr_zoom", default="1Y")
    st.plotly_chart(mk_chart_fcr(fcr if has_fcr else None, z), use_container_width=True)

    st.markdown("#### aFRR & mFRR — Activated Prices")
    desc("Daily average activated energy prices. Source: ENTSO-E balancing_prices.csv.")
    z = local_zoom("mk_afrr_zoom")
    st.plotly_chart(mk_chart_afrr(bal if has_bal else None, z), use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════════════
    # ROW 10 — Regional view
    # ════════════════════════════════════════════════════════════════════════
    section("Regional View — Europe")

    st.markdown("#### DA Spot Map — Europe")
    desc("Average DA price by country for selected window. Green = low, Red = high. "
         "Data: FR from hourly_spot.csv, DE/BE/ES/NL from xborder_da_prices.csv.")
    z = local_zoom("mk_map_zoom", default="7D")
    st.plotly_chart(mk_chart_europe_map(xb if has_xb else None, hourly_full, z),
                    use_container_width=True)

    st.markdown("#### Historical DA Prices — France vs Neighbours")
    desc("Daily average. France in navy. Same controls as main spot chart.")
    z = local_zoom("mk_xb_hist_zoom")
    st.plotly_chart(mk_chart_country_history(xb if has_xb else None, hourly_full, z),
                    use_container_width=True)