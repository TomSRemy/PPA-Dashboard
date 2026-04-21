"""
tab_market_dynamics.py — KAL-EL PPA Dashboard
Tab 3 — Market Dynamics: neg hours, profiles, duck curve.
Migrated to ECharts via streamlit-echarts.
"""
import streamlit as st

from theme import C1, C2, C3, C4, C5, WHT
from ui import section, desc, status_msg
from charts_overview_dynamics import (
    chart_neg_hours, chart_monthly_profile, chart_shape_disc_delta,
    chart_heatmap, chart_market_value_vs_penetration, chart_duck_curve,
)
from streamlit_echarts import st_echarts


def _ec(opt, height="420px", key=None):
    if opt is None:
        st.info("Données non disponibles.")
        return
    if isinstance(opt, dict) and "graphic" in opt and "series" not in opt:
        st.info(opt["graphic"][0]["style"]["text"])
        return
    st_echarts(options=opt, height=height, key=key)


def render_tab_market_dynamics(ctx):
    nat_ref       = ctx.get("nat_ref")
    hourly        = ctx.get("hourly")
    has_asset     = ctx.get("has_asset")
    cfg           = ctx.get("cfg")
    asset_name    = ctx.get("asset_name")
    partial_years = ctx.get("partial_years")
    fig_cap_link  = ctx.get("fig_cap_link")   # still a Plotly fig from compute — keep for now

    # ── Negative hours ────────────────────────────────────────────────────────
    section("Negative Price Hours — by Year")
    desc("Heures avec prix DA < 0. Tendance hors YTD. Seuil CRE : 15h/an.")
    _ec(chart_neg_hours(hourly, partial_years, cfg["color"]),
        height="380px", key="neg_hours")

    st.markdown("---")

    # ── Monthly profile + scatter ─────────────────────────────────────────────
    c3a, c3b = st.columns(2)
    with c3a:
        section(f"Monthly Cannibalization Profile — {cfg['label']}")
        desc("Shape discount moyen par mois calendaire. Barres d'erreur = écart-type annuel.")
        opt_mo, monthly_agg = chart_monthly_profile(hourly, cfg["prod_col"],
                                                     cfg["color"], cfg["label"])
        _ec(opt_mo, height="360px", key="monthly_profile")
    with c3b:
        section(f"CP% vs National {cfg['label']} Capacity")
        desc("Chaque point = une année. Axe X = capacité nationale installée.")
        # fig_cap_link is computed upstream — still Plotly for now
        if fig_cap_link is not None:
            st.plotly_chart(fig_cap_link, use_container_width=True)
        else:
            st.info("Graphique de capacité non disponible.")

    st.markdown("---")

    # ── Shape disc delta ──────────────────────────────────────────────────────
    section(f"Annual Shape Discount Change — {cfg['label']}")
    desc("Delta annuel du shape discount (pp). Positif = cannibalization accrue.")
    _ec(chart_shape_disc_delta(nat_ref, cfg["nat_sd"], cfg["color"], cfg["label"]),
        height="340px", key="sd_delta")

    st.markdown("---")

    # ── Heatmap ───────────────────────────────────────────────────────────────
    section(f"Heatmap — Monthly Shape Discount by Year — {cfg['label']}")
    desc("Shape discount par mois et année. Plus foncé = plus de cannibalization.")
    _ec(chart_heatmap(monthly_agg, cfg["color"], cfg["label"]),
        height="360px", key="heatmap")

    st.markdown("---")

    # ── Market value ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Market Value Analysis — Jomaux / GEM Energy Analytics</div>',
                unsafe_allow_html=True)
    section(f"Market Value vs {cfg['label']} Generation Output")
    desc("Prix spot moyen par bin de MW. Méthode : GEM Energy Analytics (Oct 2024).")
    _ec(chart_market_value_vs_penetration(hourly, cfg["prod_col"], cfg["color"],
                                           cfg["label"], partial_years),
        height="380px", key="market_value")

    st.markdown("---")

    # ── Duck / Canyon curve ───────────────────────────────────────────────────
    season_lbl = "Apr-Sep" if cfg["duck_months"]==list(range(4,10)) else "All months"
    section(f"Canyon Curve — {cfg['label']} ({season_lbl})")
    desc("Prix DA normalisés par heure du jour. Une courbe par année. Année la plus récente en avant-plan.")

    _yr_opts = [f"Last {n} years" for n in [3,5,7,10]] + ["All years"]
    _yr_sel  = st.radio("", _yr_opts, index=1, horizontal=True, key="canyon_filter")
    _n_years = {"Last 3 years":3,"Last 5 years":5,"Last 7 years":7,"Last 10 years":10}.get(_yr_sel, None)

    _ec(chart_duck_curve(hourly, cfg["color"], cfg["label"],
                          cfg["duck_months"], recent_years=_n_years),
        height="460px", key="duck_curve")
