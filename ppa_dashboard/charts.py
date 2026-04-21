"""
charts.py — KAL-EL PPA Dashboard
All Plotly chart functions. Each returns a go.Figure.
"""

import pandas as pd
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (C1, C2, C3, C4, C5, WHT, C2L, C3L, MONTH_NAMES)
from theme import (
    TEXT_DARK, TEXT_MUTED, TEXT_FAINT, ACCENT_PRIMARY, ACCENT_WARN, ACCENT_NEG,
    BG_WHITE, BG_PAGE, GRID_LINE, BORDER_MED, BORDER_FAINT,
    REF_LINE, REF_LINE_L, REF_LINE_LL,
    COL_AFRR, COL_MFRR, COL_WIND, CHART_PALETTE,
    CHART_H_XS, CHART_H_SM, CHART_H_MD, CHART_H_LG, CHART_H_XL, CHART_H_TBL,
    rgba, with_alpha, transparent, band_colors, pos_neg_colors,
)
from ui import plotly_base

COL_DA      = TEXT_DARK
COL_IMB_POS = ACCENT_PRIMARY
COL_IMB_NEG = ACCENT_NEG

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ══════════════════════════════════════════════════════════════════════════════

def chart_historical_cp(nat_ref, asset_ann, has_asset, asset_name,
                        tech_clr, tech_lbl, nat_cp_list, nat_eur_list, partial_years):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                        subplot_titles=["CP% (% of spot average)", "CP (EUR/MWh)"],
                        row_heights=[0.55, 0.45])
    ny   = nat_ref["year"].tolist()
    ns   = nat_ref["spot"].tolist()
    is_p = nat_ref["partial"].tolist() if "partial" in nat_ref.columns else [False]*len(ny)
    bar_colors   = [rgba(ACCENT_WARN, 0.55) if p else rgba(tech_clr, 0.5) for p in is_p]
    bar_outlines = [C3 if p else tech_clr for p in is_p]
    bar_texts    = [f"<b>{v*100:.0f}%</b>" + (" YTD" if p else "") for v, p in zip(nat_cp_list, is_p)]
    fig.add_trace(go.Bar(x=ny, y=nat_cp_list, name=f"M0 National {tech_lbl}",
                         marker_color=bar_colors, marker_line_color=bar_outlines, marker_line_width=2,
                         text=bar_texts, textposition="outside",
                         textfont=dict(size=13, color=C1, family="Calibri")), row=1, col=1)
    if has_asset:
        ay = asset_ann["Year"].tolist(); acp = asset_ann["cp_pct"].tolist(); ae = asset_ann["cp_eur"].tolist()
        fig.add_trace(go.Bar(x=ay, y=acp, name=asset_name,
                             marker_color=[rgba(C5, 0.6)]*len(ay),
                             marker_line_color=C5, marker_line_width=1.5,
                             text=[f"<b>{v*100:.0f}%</b>" for v in acp], textposition="outside",
                             textfont=dict(size=11, color=C5, family="Calibri")), row=1, col=1)
        fig.add_trace(go.Scatter(x=ay, y=ae, name=asset_name+" EUR",
                                 line=dict(color=C5, width=2.5), mode="lines+markers",
                                 marker=dict(size=8, color=C5, line=dict(width=1.5, color=WHT))), row=2, col=1)
    fig.add_trace(go.Scatter(x=ny, y=nat_cp_list,
                             line=dict(color=tech_clr, width=2.5, dash="dash"), mode="lines+markers",
                             marker=dict(size=7, color=tech_clr, symbol="square",
                                         line=dict(width=1.5, color=WHT)), showlegend=False), row=1, col=1)
    fig.add_hline(y=1.0, line=dict(color=REF_LINE, width=1, dash="dot"), row=1, col=1)
    fig.add_vrect(x0=2021.5, x1=2022.5, fillcolor=C3, opacity=0.25, line_width=0, row=1, col=1)
    fig.add_vrect(x0=2021.5, x1=2022.5, fillcolor=C3, opacity=0.25, line_width=0, row=2, col=1)
    fig.add_annotation(x=2022, y=0.32, text="2022", showarrow=False,
                       font=dict(color=C3, size=13, family="Calibri"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ny, y=ns, name="National Spot",
                             line=dict(color=TEXT_MUTED, width=2, dash="dash"), mode="lines+markers",
                             marker=dict(size=6, color=TEXT_MUTED)), row=2, col=1)
    fig.add_trace(go.Scatter(x=ny, y=nat_eur_list, name=f"M0 {tech_lbl} EUR",
                             line=dict(color=tech_clr, width=2.5), mode="lines+markers",
                             marker=dict(size=7, color=tech_clr, symbol="square",
                                         line=dict(width=1.5, color=WHT))), row=2, col=1)
    fig.update_yaxes(tickformat=".0%", row=1, col=1)
    fig.update_layout(
        barmode="group",
        title=dict(text=f"<b>Historical Captured Price — {tech_lbl}</b>"))
    # Always show all years on x-axis
    fig.update_xaxes(tickmode="array", tickvals=nat_ref["year"].tolist() if hasattr(nat_ref,"__len__") else [], row=1, col=1)
    plotly_base(fig, h=CHART_H_XL)
    return fig


def chart_projection(nat_ref, asset_ann, has_asset, proj,
                     nat_cp_list, nat_ref_complete, nat_cp_col,
                     tech_clr, tech_lbl, sl_u, ic_u, r2_u,
                     last_yr_proj, proj_n, ex22,
                     reg_basis="Asset", anchor_val=None, proj_targets=None):
    fig = go.Figure()
    if has_asset:
        fig.add_trace(go.Scatter(x=asset_ann["Year"].tolist(), y=asset_ann["cp_pct"].tolist(),
                                 name="Asset (historical)", mode="lines+markers+text",
                                 line=dict(color=C5, width=3),
                                 marker=dict(size=10, color=C5, line=dict(width=2, color=WHT)),
                                 text=[f"<b>{v*100:.0f}%</b>" for v in asset_ann["cp_pct"]],
                                 textposition="top center",
                                 textfont=dict(size=11, color=C5, family="Calibri")))
    fig.add_trace(go.Scatter(x=nat_ref["year"].tolist(), y=nat_cp_list,
                             name=f"M0 National {tech_lbl}", mode="lines+markers",
                             line=dict(color=tech_clr, width=2.5, dash="dash"),
                             marker=dict(size=8, color=tech_clr, symbol="square",
                                         line=dict(width=1.5, color=WHT))))
    tx = list(range(2014, last_yr_proj + proj_n + 1))
    fig.add_trace(go.Scatter(x=tx, y=[1-(ic_u+sl_u*yr) for yr in tx],
                             name="Trend", line=dict(color=REF_LINE, width=2, dash="dot"),
                             mode="lines", opacity=0.8))
    py_ = proj["year"].tolist()
    fig.add_trace(go.Scatter(x=py_+py_[::-1],
                             y=proj["p90"].tolist()+proj["p10"].tolist()[::-1],
                             fill="toself", fillcolor=rgba(ACCENT_WARN, 0.20),
                             line=dict(color=transparent()), name="P10-P90"))
    fig.add_trace(go.Scatter(x=py_+py_[::-1],
                             y=proj["p75"].tolist()+proj["p25"].tolist()[::-1],
                             fill="toself", fillcolor=rgba(ACCENT_WARN, 0.35),
                             line=dict(color=transparent()), name="P25-P75"))
    if anchor_val is not None:
        hl = anchor_val
    elif has_asset:
        hl = asset_ann["cp_pct"].iloc[-1]
    elif nat_cp_col in nat_ref_complete.columns and not nat_ref_complete[nat_cp_col].isna().all():
        hl = nat_ref_complete[nat_cp_col].iloc[-1]
    else:
        hl = nat_ref_complete["cp_nat_pct"].iloc[-1]
    fig.add_trace(go.Scatter(x=[last_yr_proj]+py_, y=[hl]+proj["p50"].tolist(),
                             name="P50 (central scenario)", mode="lines+markers",
                             line=dict(color=C1, width=3),
                             marker=dict(size=8, color=C1, line=dict(width=2, color=WHT))))
    for _, row in proj.iterrows():
        fig.add_annotation(x=row["year"], y=row["p50"],
                           text=f"<b>P50:{row['p50']*100:.0f}%</b><br>P10:{row['p10']*100:.0f}%",
                           showarrow=True, arrowhead=2, arrowcolor=C1, arrowwidth=1.5,
                           font=dict(size=11, color=C1, family="Calibri"),
                           bgcolor="rgba(255,255,255,0.9)", bordercolor=C3, borderwidth=1,
                           ax=32, ay=-40)
    if proj_targets:
        for t in proj_targets:
            fig.add_trace(go.Scatter(x=[t["year"]], y=[t["cp"]], mode="markers+text",
                                     marker=dict(size=10, color="black", line=dict(width=1.5, color=WHT)),
                                     text=[f"<b>{t['year']}</b><br>{t['cp']*100:.0f}%"],
                                     textposition="top center",
                                     textfont=dict(size=11, color="black", family="Calibri"),
                                     name=f"{t['year']} capacity-based"))
    fig.add_vline(x=last_yr_proj+0.5, line=dict(color=REF_LINE_L, width=1.5, dash="dot"))
    fig.add_vrect(x0=2021.5, x1=2022.5, fillcolor=C3, opacity=0.15, line_width=0)
    fig.update_yaxes(tickformat=".0%")
    plotly_base(fig, h=CHART_H_XL)
    fig.update_layout(
        title=dict(text=(f"Slope: {-sl_u*100:.2f}%/yr  R\u00b2: {r2_u:.3f} "
                         f"({'excl.2022 ' if ex22 else ''}| {reg_basis} regression) | excl. YTD"),
                   font=dict(size=13, color=C2, family="Calibri"), x=0.5),
        yaxis=dict(range=[0.15, 1.22]))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Forward Curve
# ══════════════════════════════════════════════════════════════════════════════

def chart_forward(fwd_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=fwd_df["year"], y=fwd_df["forward"],
                         marker_color=[rgba(C2, 0.7)]*len(fwd_df),
                         marker_line_color=C2, marker_line_width=2,
                         text=[f"<b>{v:.1f}</b>" for v in fwd_df["forward"]],
                         textposition="outside",
                         textfont=dict(size=14, color=C1, family="Calibri"),
                         name="EEX Forward"))
    fig.update_yaxes(title_text="EUR/MWh")
    fig.update_xaxes(tickmode="array", tickvals=fwd_df["year"].tolist())
    plotly_base(fig, h=CHART_H_XS, show_legend=False)
    fig.update_layout(title=dict(text="<b>Forward Price Curve</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Market Dynamics
# ══════════════════════════════════════════════════════════════════════════════

def chart_neg_hours(hourly: pd.DataFrame, partial_years: list, tech_clr: str) -> go.Figure:
    neg = hourly[hourly["Spot"] < 0].groupby("Year").size().reset_index(name="neg_hours")
    all_yrs = pd.DataFrame({"Year": sorted(hourly["Year"].unique())})
    neg = all_yrs.merge(neg, on="Year", how="left").fillna(0)
    neg["neg_hours"] = neg["neg_hours"].astype(int)
    bar_c = [C3 if yr in partial_years else (C5 if v > 300 else (C4 if v > 100 else tech_clr))
             for v, yr in zip(neg["neg_hours"], neg["Year"])]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=neg["Year"], y=neg["neg_hours"],
                         marker_color=bar_c, marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v}</b>"+(" YTD" if yr in partial_years else "")
                               for v, yr in zip(neg["neg_hours"], neg["Year"])],
                         textposition="outside",
                         textfont=dict(size=12, color=C1, family="Calibri"),
                         name="Negative Price Hours"))
    neg_c = neg[~neg["Year"].isin(partial_years)]
    if len(neg_c) >= 3:
        xn = neg_c["Year"].values.astype(float); yn = neg_c["neg_hours"].values.astype(float)
        sln, icn, *_ = stats.linregress(xn, yn)
        fut = list(range(int(xn.min()), int(xn.max())+4))
        fig.add_trace(go.Scatter(x=fut, y=[max(0, icn+sln*yr) for yr in fut],
                                 mode="lines", line=dict(color=C5, width=2.5, dash="dash"),
                                 name=f"Trend ({sln:+.0f}h/yr)"))
    fig.add_hline(y=15, line=dict(color=C2, width=1.5, dash="dot"),
                  annotation_text="CRE Threshold (15h)",
                  annotation_font=dict(color=C2, size=12, family="Calibri"))
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(text="<b>Negative Price Hours by Year</b>"))
    return fig


def chart_monthly_profile(hourly: pd.DataFrame, prod_col: str, tech_clr: str, tech_lbl: str):
    monthly = hourly.copy()
    monthly["Rev_tech"] = monthly[prod_col] * monthly["Spot"]
    monthly_agg = monthly[monthly["Spot"] > 0].groupby(["Year","Month"]).agg(
        spot_avg=("Spot","mean"), prod_tech=(prod_col,"sum"), rev_tech=("Rev_tech","sum"),
    ).reset_index()
    monthly_agg["m0"]   = monthly_agg["rev_tech"] / monthly_agg["prod_tech"].replace(0, np.nan)
    monthly_agg["sd_m"] = 1 - monthly_agg["m0"] / monthly_agg["spot_avg"]
    month_avg = monthly_agg.groupby("Month")["sd_m"].agg(["mean","std"]).reset_index()
    bar_c_m = [C5 if v > 0.15 else (C4 if v > 0.08 else tech_clr) for v in month_avg["mean"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=MONTH_NAMES, y=month_avg["mean"],
                         error_y=dict(type="data", array=month_avg["std"].tolist(),
                                      visible=True, color=REF_LINE, thickness=2, width=5),
                         marker_color=bar_c_m, marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v*100:.1f}%</b>" for v in month_avg["mean"]],
                         textposition="outside",
                         textfont=dict(size=11, color=C1, family="Calibri")))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=1))
    fig.update_yaxes(tickformat=".0%", title_text="Average Shape Discount")
    plotly_base(fig, h=CHART_H_MD, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Monthly Cannibalization Profile — {tech_lbl}</b>"))
    return fig, monthly_agg


def chart_scatter_cp_vs_capacity(nat_ref: pd.DataFrame, hourly: pd.DataFrame,
                                  prod_col: str, nat_cp_col: str, tech_clr: str,
                                  tech_lbl: str, partial_years: list,
                                  is_solar: bool, ex22: bool = False):
    # X axis: installed capacity (GW) if available in nat_ref, else avg MW
    cap_col = "cap_solar_gw" if is_solar else "cap_wind_gw"
    use_gw  = cap_col in nat_ref.columns and nat_ref[cap_col].notna().any()
    x_label = f"{tech_lbl} Installed Capacity (GW)" if use_gw else f"National {tech_lbl} Avg MW"

    if use_gw:
        sc = nat_ref[["year", nat_cp_col, cap_col, "partial"]].copy()
        sc = sc.rename(columns={nat_cp_col: "cp_plot", cap_col: "TechX"})
        sc["cp_plot"] = sc["cp_plot"].fillna(nat_ref["cp_nat_pct"])
        sc = sc[sc["TechX"].notna() & (sc["TechX"] > 0)]
    else:
        nat_mw = hourly.groupby("Year")[prod_col].mean().reset_index()
        nat_mw.columns = ["year","TechX"]
        sc = nat_ref.merge(nat_mw, on="year", how="inner")
        sc = sc[sc["TechX"] > 0].copy()
        sc["cp_plot"] = sc[nat_cp_col].fillna(sc["cp_nat_pct"])

    pt_col = [rgba(ACCENT_WARN, 0.8) if r.get("partial", False) else tech_clr
              for _, r in sc.iterrows()]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sc["TechX"], y=sc["cp_plot"], mode="markers+text",
        marker=dict(size=16, color=pt_col, line=dict(width=2, color=WHT)),
        text=[f"<b>{int(y)}</b>" for y in sc["year"]],
        textposition="top center",
        textfont=dict(size=11, color=C1, family="Calibri"),
        name=f"M0 National {tech_lbl}"))

    sc_c = sc[~sc["year"].isin(partial_years)].copy()
    if ex22:
        sc_c = sc_c[sc_c["year"] != 2022]

    proj_targets = []
    if len(sc_c) >= 3:
        x = sc_c["TechX"].values.astype(float)
        y_arr = sc_c["cp_plot"].values.astype(float)
        mask = x > 0; x = x[mask]; y_arr = y_arr[mask]
        if len(x) >= 3:
            coeffs = np.polyfit(np.log(x), y_arr, 1)
            y_pred = np.polyval(coeffs, np.log(x))
            r2 = 1 - np.sum((y_arr-y_pred)**2) / np.sum((y_arr-np.mean(y_arr))**2)

            if use_gw:
                PPE3 = {
                    "Solar": {2030: 48.0, 2035: 67.5},
                    "Wind":  {2030: 31.0, 2035: 37.5},
                }
            else:
                PPE3 = {
                    "Solar": {2030: 6240, 2035: 8775},
                    "Wind":  {2030: 7440, 2035: 9000},
                }

            tech_key = "Solar" if is_solar else "Wind"
            x_end = x.max()
            for target_year, cap_target in PPE3[tech_key].items():
                cp_target = np.polyval(coeffs, np.log(cap_target))
                proj_targets.append({"year": target_year, "capacity": cap_target, "cp": cp_target})
            if proj_targets:
                x_end = max(x_end, max(t["capacity"] for t in proj_targets))

            xl = np.linspace(x.min(), x_end, 300)
            yl = np.polyval(coeffs, np.log(xl))
            fig.add_trace(go.Scatter(x=xl, y=yl, mode="lines",
                                     line=dict(color="black", width=2),
                                     name=f"log fit (R²={r2:.2f})"))
            unit = "GW" if use_gw else "MW"
            for t in proj_targets:
                fig.add_vline(x=t["capacity"], line=dict(color="black", width=1, dash="dot"))
                fig.add_trace(go.Scatter(
                    x=[t["capacity"]], y=[t["cp"]], mode="markers+text",
                    marker=dict(size=12, color="black", line=dict(width=1.5, color=WHT)),
                    text=[f"<b>PPE3 {t['year']}<br>{t['capacity']:.0f}{unit} to {t['cp']*100:.0f}%</b>"],
                    textposition="top center",
                    textfont=dict(size=10, color=C1, family="Calibri"),
                    name=f"PPE3 {t['year']}"))

    fig.update_yaxes(tickformat=".0%", title_text="Captured Price (% of spot)")
    fig.update_xaxes(title_text=x_label)
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(
        text=f"<b>CP% vs {tech_lbl} ({'Installed Capacity (GW)' if use_gw else 'Avg MW'})</b>"))
    return fig, proj_targets

def chart_shape_disc_delta(nat_ref: pd.DataFrame, nat_sd_col: str,
                            tech_clr: str, tech_lbl: str) -> go.Figure:
    sd = nat_ref[["year"]].copy()
    sd["shape_disc"] = nat_ref[nat_sd_col].fillna(nat_ref["shape_disc"])
    sd = sd.dropna().sort_values("year")
    sd["delta"] = sd["shape_disc"].diff()
    sd = sd.dropna(subset=["delta"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=sd["year"], y=sd["delta"],
                         marker_color=[C5 if v > 0 else tech_clr for v in sd["delta"]],
                         marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v*100:+.1f}pp</b>" for v in sd["delta"]],
                         textposition="outside",
                         textfont=dict(size=12, color=C1, family="Calibri")))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=1.5))
    fig.update_yaxes(tickformat=".1%", title_text="Delta Shape Discount (pp)")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Annual Shape Discount Change — {tech_lbl}</b>"))
    return fig


def chart_heatmap(monthly_agg: pd.DataFrame, tech_clr: str, tech_lbl: str) -> go.Figure:
    pivot = monthly_agg.pivot(index="Year", columns="Month", values="sd_m")
    pivot.columns = [MONTH_NAMES[c-1] for c in pivot.columns]
    z_vals = pivot.values * 100
    # White text on dark cells, dark text on light cells
    text_colors = [["#FFFFFF" if v > 20 else "#000000" for v in row] for row in z_vals]
    fig = go.Figure(data=go.Heatmap(
        z=z_vals, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=[[0,"#FFFFFF"],[0.3,tech_clr],[0.65,C3],[1,C5]],
        zmid=15,
        text=[[f"{v:.1f}%" for v in row] for row in z_vals],
        texttemplate="%{text}",
        textfont=dict(size=12, family="Calibri"),
        colorbar=dict(
            title=dict(text="Shape Disc (%)", font=dict(size=12, color=C1)),
            tickfont=dict(size=11, color=C1), thickness=14,
            ticksuffix="%"
        )))
    fig.update_xaxes(title_text="Month"); fig.update_yaxes(title_text="Year")
    plotly_base(fig, h=CHART_H_MD, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Monthly Shape Discount Heatmap — {tech_lbl}</b>"))
    return fig


def chart_market_value_vs_penetration(hourly: pd.DataFrame, prod_col: str,
                                       tech_clr: str, tech_lbl: str,
                                       partial_years: list, n_bins: int=20) -> go.Figure:
    h = hourly[hourly[prod_col] > 0].copy()
    if len(h) < 100:
        return go.Figure()
    h = h[~h["Year"].isin(partial_years)]
    bins = pd.cut(h[prod_col], bins=n_bins)
    agg = h.groupby(bins, observed=True).agg(
        avg_spot=("Spot","mean"), avg_mw=(prod_col,"mean"), count=(prod_col,"count"),
        avg_cp_pct=("Spot","mean")).reset_index()
    agg = agg[agg["count"] > 20]
    max_mw = agg["avg_mw"].max()
    colors = [rgba(tech_clr, 0.4+0.5*(v/max_mw)) for v in agg["avg_mw"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg["avg_mw"], y=agg["avg_spot"], mode="markers",
                             marker=dict(size=agg["count"].apply(lambda c: min(8+c/200,22)),
                                         color=colors, line=dict(width=1, color=WHT)),
                             name="Avg Spot per MW bin",
                             hovertemplate="<b>Avg MW: %{x:.0f}</b><br>Avg Spot: %{y:.1f} EUR/MWh<extra></extra>"))
    if len(agg) >= 4:
        sl, ic, r, _, _ = stats.linregress(agg["avg_mw"], agg["avg_spot"])
        xl = np.linspace(agg["avg_mw"].min(), agg["avg_mw"].max(), 100)
        fig.add_trace(go.Scatter(x=xl, y=ic+sl*xl, mode="lines",
                                 line=dict(color=C1, width=2, dash="dash"),
                                 name=f"Trend (R\u00b2={r**2:.2f})"))
    fig.update_xaxes(title_text=f"{tech_lbl} Generation (MW)")
    fig.update_yaxes(title_text="Average Spot Price (EUR/MWh)")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(text=f"<b>Market Value vs {tech_lbl} Generation Output</b>"))
    return fig


def chart_duck_curve(hourly: pd.DataFrame, tech_clr: str, tech_lbl: str, duck_months: list,
                      recent_years: int = None) -> go.Figure:
    h = hourly[hourly["Month"].isin(duck_months)].copy()
    h["Date"] = pd.to_datetime(h["Date"]); h["Hour"] = h["Date"].dt.hour
    monthly_avg = h.groupby(["Year","Month"])["Spot"].transform("mean")
    h["norm_spot"] = h["Spot"] / monthly_avg.replace(0, np.nan)
    hourly_avg = h.groupby(["Year","Hour"])["norm_spot"].mean().reset_index()
    all_years = sorted(hourly_avg["Year"].unique())
    years = all_years[-recent_years:] if recent_years and len(all_years) >= recent_years else all_years
    hourly_avg = hourly_avg[hourly_avg["Year"].isin(years)]
    n = max(len(years),1)
    year_colors = [rgba(tech_clr, 0.25+0.75*i/(n-1)) if n>1 else tech_clr for i,_ in enumerate(years)]
    fig = go.Figure()
    for yr, col in zip(years, year_colors):
        d = hourly_avg[hourly_avg["Year"]==yr].sort_values("Hour")
        fig.add_trace(go.Scatter(x=d["Hour"], y=d["norm_spot"], mode="lines",
                                 line=dict(color=col, width=3.0 if yr==years[-1] else 1.2),
                                 name=str(yr), legendgroup=str(yr), showlegend=True,
                                 hovertemplate=f"<b>{yr}</b> — Hour %{{x}}h: %{{y:.2f}}x avg<extra></extra>"))
    fig.add_hline(y=1.0, line=dict(color=REF_LINE_L, width=1.5, dash="dot"),
                  annotation_text="Monthly avg = 1.0",
                  annotation_font=dict(color=TEXT_FAINT, size=11, family="Calibri"),
                  annotation_position="top left")
    if 4 in duck_months or 5 in duck_months:
        fig.add_vrect(x0=9.5, x1=15.5, fillcolor=rgba(tech_clr,0.07), line_width=0,
                      annotation_text="Solar peak", annotation_position="top left",
                      annotation_font=dict(color=tech_clr, size=10, family="Calibri"))
    season_lbl = "Apr-Sep" if duck_months==list(range(4,10)) else "All months"
    fig.update_xaxes(title_text="Hour of Day", tickmode="array",
                     tickvals=list(range(0,24,2)), ticktext=[f"{h}h" for h in range(0,24,2)])
    fig.update_yaxes(title_text="Normalised Price (monthly avg = 1)")
    plotly_base(fig, h=CHART_H_LG)
    fig.update_layout(title=dict(text=f"<b>Duck/Canyon Curve — Normalised Day-Ahead Prices ({tech_lbl}, {season_lbl})</b>"))
    return fig


def chart_canyon_curve(hourly: pd.DataFrame, tech_clr: str, tech_lbl: str,
                        duck_months: list, recent_years: int=4) -> go.Figure:
    h = hourly[hourly["Month"].isin(duck_months)].copy()
    h["Date"] = pd.to_datetime(h["Date"]); h["Hour"] = h["Date"].dt.hour
    monthly_avg = h.groupby(["Year","Month"])["Spot"].transform("mean")
    h["norm_spot"] = h["Spot"] / monthly_avg.replace(0, np.nan)
    all_complete = sorted(h[~h["Year"].isin([pd.Timestamp.now().year])]["Year"].unique())
    sel = all_complete[-recent_years:] if len(all_complete)>=recent_years else all_complete
    hourly_avg = h[h["Year"].isin(sel)].groupby(["Year","Hour"])["norm_spot"].mean().reset_index()
    n = max(len(sel),1); year_colors = [REF_LINE]*(n-1)+[tech_clr]
    fig = go.Figure()
    for yr, col in zip(sel, year_colors):
        d = hourly_avg[hourly_avg["Year"]==yr].sort_values("Hour")
        fig.add_trace(go.Scatter(x=d["Hour"], y=d["norm_spot"], mode="lines",
                                 line=dict(color=col, width=3.0 if yr==sel[-1] else 1.5),
                                 name=str(yr),
                                 hovertemplate=f"<b>{yr}</b> — Hour %{{x}}h: %{{y:.2f}}x avg<extra></extra>"))
    fig.add_hline(y=1.0, line=dict(color=REF_LINE_L, width=1.5, dash="dot"),
                  annotation_text="Monthly avg = 1.0",
                  annotation_font=dict(color=TEXT_FAINT, size=11, family="Calibri"),
                  annotation_position="top left")
    season_lbl = "Apr-Sep" if duck_months==list(range(4,10)) else "All months"
    fig.update_xaxes(title_text="Hour of Day", tickmode="array",
                     tickvals=list(range(0,24,2)), ticktext=[f"{h}h" for h in range(0,24,2)])
    fig.update_yaxes(title_text="Normalised Price (monthly avg = 1)")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(text=f"<b>Canyon Curve — Last {recent_years} Years ({tech_lbl}, {season_lbl})</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Sensitivity & Scenarios
# ══════════════════════════════════════════════════════════════════════════════

def chart_pnl_percentile(pcts, pnl_v, cp_vals, ppa, vol_mwh,
                          chosen_pct, vol_stress, be, tech_lbl):
    fig = go.Figure()
    px_ = [p for p,v in zip(pcts,pnl_v) if v>=0]; py_ = [v for v in pnl_v if v>=0]
    nx_ = [p for p,v in zip(pcts,pnl_v) if v<0];  ny_ = [v for v in pnl_v if v<0]
    if px_: fig.add_trace(go.Scatter(x=px_, y=py_, fill="tozeroy",
                                      fillcolor=rgba(ACCENT_PRIMARY, 0.15),
                                      line=dict(color=transparent()), showlegend=False))
    if nx_: fig.add_trace(go.Scatter(x=nx_, y=ny_, fill="tozeroy",
                                      fillcolor=rgba(ACCENT_NEG, 0.15),
                                      line=dict(color=transparent()), showlegend=False))
    fig.add_trace(go.Scatter(x=pcts, y=pnl_v, name="P&L (k EUR/yr)",
                             mode="lines", line=dict(color=C1, width=3)))
    pc_ = pnl_v[chosen_pct-1]
    fig.add_trace(go.Scatter(x=[chosen_pct], y=[pc_], mode="markers+text",
                             marker=dict(size=16, color=C2 if pc_>=0 else C5,
                                         line=dict(width=2.5, color=WHT)),
                             text=[f"<b>P{chosen_pct}: {pc_:.0f}k</b>"],
                             textposition="top right", name=f"P{chosen_pct} Selected",
                             textfont=dict(size=12, color=C1, family="Calibri")))
    pu  = [vol_mwh*(1+vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    pd_ = [vol_mwh*(1-vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    fig.add_trace(go.Scatter(x=pcts+pcts[::-1], y=pu+pd_[::-1],
                             fill="toself", fillcolor=rgba(ACCENT_WARN, 0.25),
                             line=dict(color=transparent()), name=f"+/-{vol_stress}% Volume"))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=2))
    if be:
        fig.add_vline(x=be, line=dict(color=C5, width=2, dash="dot"),
                      annotation_text=f"<b>Break-even P{be}</b>",
                      annotation_font=dict(color=C5, size=12, family="Calibri"))
    fig.update_layout(xaxis_title="Shape Discount Percentile", yaxis_title="Annual P&L (k EUR)")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(text=f"<b>P&L Distribution by Cannibalization Percentile — {tech_lbl}</b>"))
    return fig


def chart_scenarios(scenarios: list, proj_n: int, tech_lbl: str) -> go.Figure:
    sn=[s["Scenario"] for s in scenarios]; sv50=[s["p50"] for s in scenarios]
    sv10=[s["p10"] for s in scenarios];   sv90=[s["p90"] for s in scenarios]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="P50", x=sn, y=sv50,
                         marker_color=[rgba(ACCENT_PRIMARY, 0.80) if v>=0 else rgba(ACCENT_NEG, 0.80) for v in sv50],
                         marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v:+.0f}k</b>" for v in sv50], textposition="outside",
                         textfont=dict(size=12, color=C1, family="Calibri")))
    fig.add_trace(go.Scatter(name="P10", x=sn, y=sv10, mode="markers",
                             marker=dict(symbol="triangle-down", size=14, color=C5, line=dict(width=2, color=WHT))))
    fig.add_trace(go.Scatter(name="P90", x=sn, y=sv90, mode="markers",
                             marker=dict(symbol="triangle-up", size=14, color=C2, line=dict(width=2, color=WHT))))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=2))
    fig.update_layout(xaxis_title="Scenario", yaxis_title=f"Cumulative P&L {proj_n}yr (k EUR)", bargap=0.35)
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(text=f"<b>Stress Scenarios — {proj_n} Year P&L — {tech_lbl}</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Price Waterfall
# ══════════════════════════════════════════════════════════════════════════════

def chart_waterfall(ref_fwd: float, sd_ch: float, imb_eur: float, tech_lbl: str,
                    vol_risk_pct: float=0.0, price_risk_pct: float=0.0,
                    cannib_risk_pct: float=0.0, goo_value: float=1.0,
                    add_disc: float=0.0, margin: float=1.0) -> go.Figure:
    shape_disc_eur  = ref_fwd * sd_ch
    add_disc_eur    = ref_fwd * add_disc
    vol_risk_eur    = ref_fwd * vol_risk_pct
    price_risk_eur  = ref_fwd * price_risk_pct
    ppa_final = ref_fwd - shape_disc_eur - add_disc_eur - vol_risk_eur - price_risk_eur - imb_eur + goo_value + margin
    wf = [
        ("Baseload Forward", ref_fwd,          "absolute"),
        ("Shape Discount",   -shape_disc_eur,  "relative"),
        ("Add. Discount",    -add_disc_eur,     "relative"),
        ("Volume Risk",      -vol_risk_eur,     "relative"),
        ("Price Risk",       -price_risk_eur,   "relative"),
        ("Balancing Cost",   -imb_eur,          "relative"),
        ("GoO Value",         goo_value,        "relative"),
        ("Margin",            margin,           "relative"),
        ("PPA Price",         0,                "total"),
    ]
    wf = [row for row in wf if row[2] in ("absolute","total") or abs(row[1]) > 0.001]
    fig = go.Figure(go.Waterfall(
        name="", orientation="v",
        measure=[d[2] for d in wf], x=[d[0] for d in wf], y=[d[1] for d in wf],
        text=[f"{d[1]:+.2f}" if d[2]=="relative"
              else f"{d[1]:.2f}" if d[2]=="absolute"
              else f"<b>{ppa_final:.2f}</b>" for d in wf],
        textposition="outside", textfont=dict(size=13, color=C1, family="Calibri"),
        connector=dict(line=dict(color=REF_LINE, width=1.5)),
        decreasing=dict(marker=dict(color=C5, line=dict(color=WHT, width=1))),
        increasing=dict(marker=dict(color=C2, line=dict(color=WHT, width=1))),
        totals=dict(marker=dict(color=C3, line=dict(color=WHT, width=2))),
    ))
    fig.update_xaxes(tickangle=-30)
    plotly_base(fig, h=CHART_H_LG, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>PPA Price Waterfall — {tech_lbl} — {ppa_final:.2f} EUR/MWh</b>"),
                      yaxis_title="EUR/MWh")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Market Evolution (Rolling M0)
# ══════════════════════════════════════════════════════════════════════════════

def chart_rolling_cp(roll: pd.DataFrame, nat_ref_complete: pd.DataFrame,
                     nat_ref: pd.DataFrame, nat_cp_col: str, nat_cp_list_complete: list,
                     tech_clr: str, tech_lbl: str, partial_years: list) -> go.Figure:
    W_COLOR={30:tech_clr,90:C3,365:C1}; W_DASH={30:"dot",90:"dash",365:"solid"}
    W_WIDTH={30:1.5,90:2.0,365:2.5}
    ann_x = [pd.Timestamp(f"{int(y)}-07-01") for y in nat_ref_complete["year"]]
    fig = go.Figure()
    fig.add_hline(y=1.0, line=dict(color=REF_LINE_LL, width=1.5, dash="dot"),
                  annotation_text="100% — no cannibalization",
                  annotation_font=dict(color=TEXT_FAINT, size=11, family="Calibri"),
                  annotation_position="top left")
    for w in [365,90,30]:
        col = f"cp_{w}d"; d = roll.dropna(subset=[col])
        if len(d)==0: continue
        fig.add_trace(go.Scatter(x=d["Date"], y=d[col], name=f"{w}d rolling", mode="lines",
                                 line=dict(color=W_COLOR[w], width=W_WIDTH[w], dash=W_DASH[w])))
    fig.add_trace(go.Scatter(x=ann_x, y=nat_cp_list_complete,
                             name=f"Annual M0 {tech_lbl}", mode="markers",
                             marker=dict(size=11, color=C5, symbol="diamond", line=dict(width=2, color=WHT))))
    for _, ytd_row in nat_ref[nat_ref["partial"]==True].iterrows():
        cp_ytd = (ytd_row[nat_cp_col] if nat_cp_col in ytd_row.index and not pd.isna(ytd_row[nat_cp_col])
                  else ytd_row["cp_nat_pct"])
        fig.add_trace(go.Scatter(x=[pd.Timestamp(f"{int(ytd_row['year'])}-04-01")], y=[cp_ytd],
                                 name=f"{int(ytd_row['year'])} YTD", mode="markers+text",
                                 marker=dict(size=13, color=C3, symbol="star", line=dict(width=2, color=C1)),
                                 text=[f"<b>{int(ytd_row['year'])} YTD: {cp_ytd*100:.0f}%</b>"],
                                 textposition="top right",
                                 textfont=dict(size=11, color=C1, family="Calibri")))
    fig.update_yaxes(tickformat=".0%", title_text="Capture Rate M0 / Baseload")
    fig.update_xaxes(title_text="Date")
    plotly_base(fig, h=CHART_H_LG)
    fig.update_layout(title=dict(text=f"<b>Rolling Capture Rate — WAP / Baseload (%) — {tech_lbl}</b>"))
    return fig


def chart_rolling_eur(roll: pd.DataFrame, nat_ref_complete: pd.DataFrame,
                      nat_eur_list_complete: list, tech_clr: str, tech_lbl: str) -> go.Figure:
    W_COLOR={30:tech_clr,90:C3,365:C1}; W_DASH={30:"dot",90:"dash",365:"solid"}
    W_WIDTH={30:1.5,90:2.0,365:2.5}
    ann_x = [pd.Timestamp(f"{int(y)}-07-01") for y in nat_ref_complete["year"]]
    fig = go.Figure()
    bl = roll.dropna(subset=["bl_365d"])
    if len(bl)>0:
        fig.add_trace(go.Scatter(x=bl["Date"], y=bl["bl_365d"], name="Baseload 365d (ref)",
                                 mode="lines", line=dict(color=REF_LINE, width=2, dash="dash")))
    for w in [365,90,30]:
        col=f"m0_{w}d"; d=roll.dropna(subset=[col])
        if len(d)==0: continue
        fig.add_trace(go.Scatter(x=d["Date"], y=d[col], name=f"M0 {w}d", mode="lines",
                                 line=dict(color=W_COLOR[w], width=W_WIDTH[w], dash=W_DASH[w])))
    fig.add_trace(go.Scatter(x=ann_x, y=nat_eur_list_complete, name=f"Annual M0 {tech_lbl}",
                             mode="markers",
                             marker=dict(size=11, color=C5, symbol="diamond", line=dict(width=2, color=WHT))))
    fig.update_yaxes(title_text="EUR/MWh"); fig.update_xaxes(title_text="Date")
    plotly_base(fig, h=CHART_H_LG)
    fig.update_layout(title=dict(text=f"<b>Rolling Captured Price M0 (EUR/MWh) — {tech_lbl}</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Asset Production Profile
# ══════════════════════════════════════════════════════════════════════════════

def chart_daily_profile_national(hourly, prod_col, tech_clr, tech_lbl):
    h = hourly[hourly[prod_col] > 0].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour
    month_avg   = h.groupby(["Month", "Hour"])[prod_col].mean().reset_index()
    overall_avg = h.groupby("Hour")[prod_col].mean().reset_index()
 
    colors = ["#1D3A4A", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", COL_WIND,
              "#8ECAE6", "#219EBC", "#023047", "#FFB703", "#FB8500", CHART_PALETTE[5]]
    fig = go.Figure()
 
    # Monthly traces — slightly thinner and semi-transparent
    for m in range(1, 13):
        d = month_avg[month_avg["Month"] == m].sort_values("Hour")
        if len(d) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d[prod_col],
            mode="lines", name=MONTH_NAMES[m - 1],
            line=dict(color=colors[m - 1], width=1.5),
            opacity=0.7,
        ))
 
    # Average curve — white halo for contrast, then coloured line + markers on top
    fig.add_trace(go.Scatter(
        x=overall_avg["Hour"], y=overall_avg[prod_col],
        mode="lines+markers", name="_halo",
        line=dict(color=WHT, width=5),
        marker=dict(size=10, color=WHT),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=overall_avg["Hour"], y=overall_avg[prod_col],
        mode="lines+markers", name="Annual average",
        line=dict(color=C1, width=3),
        marker=dict(size=9, color=C1, symbol="circle",
                    line=dict(width=2, color=WHT)),
        hovertemplate="<b>Hour %{x}h — Annual avg: %{y:.1f} MW</b><extra></extra>",
    ))
 
    fig.update_xaxes(
        title_text="Hour",
        title_standoff=10,
        tickmode="array",
        tickvals=list(range(0, 24, 2)),
        ticktext=[f"{h}h" for h in range(0, 24, 2)],
    )
    
    fig.update_yaxes(title_text="Avg MW")
    plotly_base(fig, h=CHART_H_LG)
    return fig
 
def chart_daily_profile_asset(asset_raw, tech_clr, asset_name):
    a = asset_raw.copy()
    a["Date"]  = pd.to_datetime(a["Date"])
    a["Hour"]  = a["Date"].dt.hour
    a["Month"] = a["Date"].dt.month
    a = a[a["Prod_MWh"] > 0]
 
    month_avg   = a.groupby(["Month", "Hour"])["Prod_MWh"].mean().reset_index()
    overall_avg = a.groupby("Hour")["Prod_MWh"].mean().reset_index()
 
    colors = ["#1D3A4A", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", COL_WIND,
              "#8ECAE6", "#219EBC", "#023047", "#FFB703", "#FB8500", CHART_PALETTE[5]]
    fig = go.Figure()
 
    # Monthly traces — dotted, slightly thinner and semi-transparent
    for m in range(1, 13):
        d = month_avg[month_avg["Month"] == m].sort_values("Hour")
        if len(d) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d["Prod_MWh"],
            mode="lines", name=MONTH_NAMES[m - 1],
            line=dict(color=colors[m - 1], width=1.5, dash="dot"),
            opacity=0.7,
        ))
 
    # Average curve — white halo for contrast, then tech_clr line + markers on top
    fig.add_trace(go.Scatter(
        x=overall_avg["Hour"], y=overall_avg["Prod_MWh"],
        mode="lines+markers", name="_halo",
        line=dict(color=WHT, width=5),
        marker=dict(size=10, color=WHT),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=overall_avg["Hour"], y=overall_avg["Prod_MWh"],
        mode="lines+markers", name="Annual average",
        line=dict(color=tech_clr, width=3),
        marker=dict(size=9, color=tech_clr, symbol="circle",
                    line=dict(width=2, color=WHT)),
        hovertemplate="<b>Hour %{x}h — Annual avg: %{y:.1f} MW</b><extra></extra>",
    ))
 
    
    fig.update_xaxes(
        title_text="Hour",
        title_standoff=10,
        tickmode="array",
        tickvals=list(range(0, 24, 2)),
        ticktext=[f"{h}h" for h in range(0, 24, 2)],
    )
    
    fig.update_yaxes(title_text="Avg MW")
    plotly_base(fig, h=CHART_H_LG)
    return fig  

def chart_monthly_production(hourly, asset_raw, prod_col, tech_clr, asset_name, has_asset):
    fig=go.Figure()
    nat=hourly[hourly[prod_col]>0].copy()
    nat_avg=nat.groupby("Month")[prod_col].mean().reset_index()
    fig.add_trace(go.Scatter(x=[MONTH_NAMES[m-1] for m in nat_avg["Month"]],y=nat_avg[prod_col],
                             mode="markers+lines",name="National avg MW",
                             line=dict(color=C1, width=1.5, dash="dot"),
                             marker=dict(size=10,color=C1,symbol="circle",line=dict(width=1.5,color=WHT))))
    if has_asset and asset_raw is not None:
        a=asset_raw.copy(); a["Date"]=pd.to_datetime(a["Date"]); a["Month"]=a["Date"].dt.month
        asset_mo=a.groupby("Month")["Prod_MWh"].sum().reset_index()
        n_years=a["Date"].dt.year.nunique()
        asset_mo["GWh"]=asset_mo["Prod_MWh"]/1000/max(n_years,1)
        fig.add_trace(go.Bar(x=[MONTH_NAMES[m-1] for m in asset_mo["Month"]],y=asset_mo["GWh"],
                             name=f"{asset_name} (GWh)", marker_color=rgba(tech_clr,0.7),
                             marker_line_color=tech_clr, marker_line_width=1.5,
                             text=[f"<b>{v:,.2f}</b>" for v in asset_mo["GWh"]],
                             textposition="outside",
                             textfont=dict(size=11,color=C1,family="Calibri")))
    fig.update_layout(yaxis=dict(title="GWh/month & National avg MW"), barmode="group")
    fig.update_xaxes(title_text="Month")
    plotly_base(fig,h=CHART_H_MD)
    fig.update_layout(title=dict(text="<b>Monthly Production Profile</b>"))
    return fig


def chart_annual_production(hourly, asset_ann, prod_col, tech_clr, asset_name, has_asset, partial_years):
    fig=go.Figure()
    if has_asset and asset_ann is not None:
        fig.add_trace(go.Bar(x=asset_ann["Year"],y=asset_ann["prod_gwh"],
                             name=f"{asset_name} (GWh)", marker_color=rgba(tech_clr,0.7),
                             marker_line_color=tech_clr, marker_line_width=1.5,
                             text=[f"<b>{v:.0f}</b>" for v in asset_ann["prod_gwh"]],
                             textposition="outside",
                             textfont=dict(size=11,color=C1,family="Calibri")))
    fig.update_xaxes(title_text="Year"); fig.update_yaxes(title_text="GWh")
    plotly_base(fig,h=CHART_H_MD)
    fig.update_layout(title=dict(text="<b>Annual Production</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — Market Prices (DA, Imbalance, Balancing Services)
# ══════════════════════════════════════════════════════════════════════════════

def _monthly_avg(df: pd.DataFrame, col: str) -> pd.DataFrame:
    d = df[df[col].notna()].copy()
    d["YM"] = pd.to_datetime(d["Date"].astype(str).str[:7])
    return d.groupby("YM")[col].mean().reset_index()


def _last_n_days(df: pd.DataFrame, n: int=7) -> pd.DataFrame:
    df = df.copy(); df["Date"] = pd.to_datetime(df["Date"])
    cutoff = df["Date"].max() - pd.Timedelta(days=n)
    return df[df["Date"] >= cutoff].sort_values("Date")


# Section 1 — Last 7 days

def chart_last_week(bal: pd.DataFrame) -> go.Figure:
    d = _last_n_days(bal, 7)
    fig = go.Figure()
    if "DA" in d.columns and d["DA"].notna().any():
        fig.add_trace(go.Scatter(x=d["Date"], y=d["DA"], mode="lines", name="Day-Ahead",
                                 line=dict(color=COL_DA, width=2.5)))
    if "Imb_Pos" in d.columns and d["Imb_Pos"].notna().any():
        fig.add_trace(go.Scatter(x=d["Date"], y=d["Imb_Pos"], mode="lines", name="Imbalance Positive",
                                 line=dict(color=COL_IMB_POS, width=1.5, dash="dash")))
    if "Imb_Neg" in d.columns and d["Imb_Neg"].notna().any():
        fig.add_trace(go.Scatter(x=d["Date"], y=d["Imb_Neg"], mode="lines", name="Imbalance Negative",
                                 line=dict(color=COL_IMB_NEG, width=1.5, dash="dash")))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=1))
    fig.update_yaxes(title_text="EUR/MWh"); fig.update_xaxes(title_text="Date")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(title=dict(text="<b>Last 7 Days — DA & Imbalance Prices (hourly)</b>"))
    return fig


# Section 2 — Monthly history + heatmap

def chart_da_monthly(bal: pd.DataFrame) -> go.Figure:
    m = _monthly_avg(bal, "DA")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=m["YM"], y=m["DA"], mode="lines", name="DA monthly avg",
                             line=dict(color=COL_DA, width=2),
                             fill="tozeroy", fillcolor=rgba(COL_DA, 0.08)))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(text="<b>Day-Ahead Price — Monthly Average (France)</b>"))
    return fig


def chart_da_heatmap(bal: pd.DataFrame) -> go.Figure:
    h = bal[bal["DA"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"]); h["Hour"] = h["Date"].dt.hour; h["Month"] = h["Date"].dt.month
    pivot = h.groupby(["Month","Hour"])["DA"].mean().reset_index()
    p = pivot.pivot(index="Month", columns="Hour", values="DA")
    p.index = [MONTH_NAMES[i-1] for i in p.index]
    fig = go.Figure(data=go.Heatmap(
        z=p.values, x=[f"{h}h" for h in p.columns], y=p.index.tolist(),
        colorscale=[[0,C2],[0.5,C3],[1,C5]],
        text=[[f"<b>{v:.0f}</b>" for v in row] for row in p.values],
        texttemplate="%{text}", textfont=dict(size=10, color=C1, family="Calibri"),
        colorbar=dict(title=dict(text="EUR/MWh", font=dict(size=12, color=C1)),
                      tickfont=dict(size=11, color=C1), thickness=14)))
    fig.update_xaxes(title_text="Hour of Day"); fig.update_yaxes(title_text="Month")
    plotly_base(fig, h=CHART_H_MD, show_legend=False)
    fig.update_layout(title=dict(text="<b>DA Price Heatmap — Average by Hour and Month</b>"))
    return fig


# Section 3 — Spreads

def chart_intraday_spread(bal: pd.DataFrame) -> go.Figure:
    h = bal[bal["DA"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"]); h["Day"] = h["Date"].dt.date
    daily = h.groupby("Day")["DA"].agg(lambda x: x.max()-x.min()).reset_index()
    daily.columns = ["Day","spread"]
    daily["YM"] = pd.to_datetime(daily["Day"].astype(str).str[:7])
    monthly = daily.groupby("YM")["spread"].mean().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly["YM"], y=monthly["spread"],
                         marker_color=[rgba(C5,0.7) if v>100 else rgba(C2,0.7) for v in monthly["spread"]],
                         marker_line_color=WHT, marker_line_width=0.5,
                         text=[f"<b>{v:.0f}</b>" for v in monthly["spread"]],
                         textposition="outside",
                         textfont=dict(size=10, color=C1, family="Calibri"),
                         name="Intraday spread"))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(text="<b>DA Intraday Spread — Monthly Avg (Max-Min, EUR/MWh)</b>"))
    return fig


def chart_imbalance_vs_da(bal: pd.DataFrame) -> go.Figure:
    da = _monthly_avg(bal, "DA"); imn = _monthly_avg(bal, "Imb_Neg")
    merged = da.merge(imn, on="YM", how="inner")
    merged["spread"] = merged["Imb_Neg"] - merged["DA"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=merged["YM"], y=merged["spread"],
                         marker_color=[rgba(C5,0.7) if v<0 else rgba(C2,0.7) for v in merged["spread"]],
                         marker_line_color=WHT, marker_line_width=0.5,
                         text=[f"<b>{v:+.0f}</b>" for v in merged["spread"]],
                         textposition="outside",
                         textfont=dict(size=10, color=C1, family="Calibri"),
                         name="Imb_Neg - DA"))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=1.5))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(
        text="<b>Imbalance Negative vs DA — Monthly Avg — Cost of Negative Imbalance</b>"))
    return fig


# Section 4 — Balancing services

def chart_balancing_services(bal: pd.DataFrame) -> go.Figure:
    ma = _monthly_avg(bal, "aFRR") if "aFRR" in bal.columns else pd.DataFrame()
    mm = _monthly_avg(bal, "mFRR") if "mFRR" in bal.columns else pd.DataFrame()
    fig = go.Figure()
    if len(ma)>0 and ma["aFRR"].notna().any():
        fig.add_trace(go.Scatter(x=ma["YM"], y=ma["aFRR"], mode="lines", name="aFRR activated",
                                 line=dict(color=COL_AFRR, width=2)))
    if len(mm)>0 and mm["mFRR"].notna().any():
        fig.add_trace(go.Scatter(x=mm["YM"], y=mm["mFRR"], mode="lines", name="mFRR activated",
                                 line=dict(color=COL_MFRR, width=2)))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(title=dict(
        text="<b>Balancing Services — aFRR & mFRR Activated Prices (France)</b>"))
    return fig


# Section 5 — KPI summary

def summary_stats(bal: pd.DataFrame) -> dict:
    cutoff = pd.to_datetime(bal["Date"]).max() - pd.DateOffset(months=12)
    recent = bal[pd.to_datetime(bal["Date"]) >= cutoff]
    result = {}
    for col, label in [("DA","DA"),("Imb_Pos","Imb Pos"),("Imb_Neg","Imb Neg"),("aFRR","aFRR"),("mFRR","mFRR")]:
        if col in recent.columns and recent[col].notna().any():
            result[label] = {"mean": recent[col].mean(), "min": recent[col].min(),
                             "max": recent[col].max(), "std": recent[col].std()}
    return result

# ══════════════════════════════════════════════════════════════════════════════
# APPEND TO BOTTOM OF charts.py — Market Overview helpers
# (Everything below the existing summary_stats function)
# ══════════════════════════════════════════════════════════════════════════════

# ── internal helpers ─────────────────────────────────────────────────────────

def _mo_last_n(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    cutoff = df["Date"].max() - pd.Timedelta(days=n)
    return df[df["Date"] >= cutoff].sort_values("Date")


def _mo_monthly(df: pd.DataFrame, col: str) -> pd.DataFrame:
    d = df[df[col].notna()].copy()
    d["YM"] = pd.to_datetime(d["Date"].astype(str).str[:7])
    return d.groupby("YM")[col].mean().reset_index()


def _mo_daily_avg(df: pd.DataFrame, col: str) -> pd.DataFrame:
    d = df[df[col].notna()].copy()
    d["Date"] = pd.to_datetime(d["Date"])
    d["Day"] = d["Date"].dt.normalize()
    return d.groupby("Day")[col].mean().reset_index().rename(columns={"Day": "Date"})


def _mo_stub(title: str, source_note: str) -> go.Figure:
    """Return a clean placeholder figure for data not yet in the pipeline."""
    fig = go.Figure()
    fig.add_annotation(
        text=(f"<b>{title}</b><br>"
              f"<span style='font-size:12px;color:#888'>Data not yet in pipeline — {source_note}</span>"),
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color=C1, family="Calibri, Arial"),
        align="center",
    )
    fig.update_layout(
        height=260, paper_bgcolor=WHT, plot_bgcolor=WHT,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


# ── KPI helper ────────────────────────────────────────────────────────────────

def mo_kpis(hourly: pd.DataFrame, bal) -> dict:
    """
    Returns dict of KPI values.
    Keys: da_7d, da_30d, spread_7d, spread_30d, solar_7d, wind_7d,
          afrr_7d, da_7d_prev
    """
    out = {}
    if bal is not None and len(bal) > 0 and "DA" in bal.columns:
        b = bal.copy(); b["Date"] = pd.to_datetime(b["Date"])
        b7  = _mo_last_n(b, 7)
        b30 = _mo_last_n(b, 30)
        b7p = _mo_last_n(b, 14)
        b7p = b7p[b7p["Date"] < b7["Date"].min()]

        out["da_7d"]      = b7["DA"].mean()  if b7["DA"].notna().any()  else float("nan")
        out["da_30d"]     = b30["DA"].mean() if b30["DA"].notna().any() else float("nan")
        out["da_7d_prev"] = b7p["DA"].mean() if len(b7p) > 0 and b7p["DA"].notna().any() else float("nan")

        b7["Day"]  = b7["Date"].dt.normalize()
        b30["Day"] = b30["Date"].dt.normalize()
        sp7  = b7.groupby("Day")["DA"].agg(lambda x: x.max() - x.min())
        sp30 = b30.groupby("Day")["DA"].agg(lambda x: x.max() - x.min())
        out["spread_7d"]  = sp7.mean()  if len(sp7)  > 0 else float("nan")
        out["spread_30d"] = sp30.mean() if len(sp30) > 0 else float("nan")

        if "aFRR" in b7.columns and b7["aFRR"].notna().any():
            out["afrr_7d"] = b7["aFRR"].mean()
        else:
            out["afrr_7d"] = float("nan")

    if hourly is not None and len(hourly) > 0:
        h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
        h7 = _mo_last_n(h, 7)
        out["solar_7d"] = h7["NatMW"].mean()  if "NatMW"  in h7.columns and h7["NatMW"].notna().any()  else float("nan")
        out["wind_7d"]  = h7["WindMW"].mean() if "WindMW" in h7.columns and h7["WindMW"].notna().any() else float("nan")

    return out


# ── Main spot chart ───────────────────────────────────────────────────────────

def mo_chart_spot_main(hourly: pd.DataFrame, zoom: str, mode: str) -> go.Figure:
    """
    FR DA spot — main chart.
    zoom: '7D'|'1M'|'3M'|'1Y'|'2Y'|'5Y'|'All'
    mode: 'Hourly'|'Daily average'
    """
    if hourly is None or len(hourly) == 0 or "Spot" not in hourly.columns:
        return _mo_stub("FR DA Spot Price", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "5Y": 1825, "All": None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]

    fig = go.Figure()

    if mode == "Hourly":
        fig.add_trace(go.Scatter(
            x=h["Date"], y=h["Spot"],
            mode="lines", name="FR DA Spot",
            line=dict(color=C1, width=1.0),
            fill="tozeroy", fillcolor=rgba(TEXT_DARK, 0.06),
            hovertemplate="<b>%{x|%d %b %H:%M}</b>: %{y:.1f} EUR/MWh<extra></extra>",
        ))
    else:
        daily = _mo_daily_avg(h, "Spot")
        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily["Spot"],
            mode="lines", name="Daily avg",
            line=dict(color=C1, width=1.2),
            fill="tozeroy", fillcolor=rgba(TEXT_DARK, 0.06),
            hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.1f} EUR/MWh<extra></extra>",
        ))
        if zoom in ("1M", "3M") and len(daily) >= 7:
            roll7 = daily["Spot"].rolling(7, min_periods=3).mean()
            fig.add_trace(go.Scatter(
                x=daily["Date"], y=roll7, mode="lines", name="7d rolling avg",
                line=dict(color=C2, width=2.2),
                hovertemplate="<b>7d avg</b>: %{y:.1f}<extra></extra>",
            ))
        elif zoom in ("1Y", "2Y", "5Y", "All") and len(daily) >= 30:
            roll30 = daily["Spot"].rolling(30, min_periods=10).mean()
            fig.add_trace(go.Scatter(
                x=daily["Date"], y=roll30, mode="lines", name="30d rolling avg",
                line=dict(color=C2, width=2.2),
                hovertemplate="<b>30d avg</b>: %{y:.1f}<extra></extra>",
            ))

    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>FR Day-Ahead Spot Price — {mode} — {zoom}</b>"),
        hovermode="x unified",
    )
    return fig


# ── Hourly overlay ────────────────────────────────────────────────────────────

def mo_chart_hourly_overlay(hourly: pd.DataFrame) -> go.Figure:
    """7 lines (one per day), x=hour, + 7-day average + min-max envelope."""
    if hourly is None or len(hourly) == 0 or "Spot" not in hourly.columns:
        return _mo_stub("Hourly DA Profile", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    h7 = _mo_last_n(h, 7)
    h7["Day"] = h7["Date"].dt.normalize()
    h7["Hour"] = h7["Date"].dt.hour
    days = sorted(h7["Day"].unique())

    ALPHAS = [0.30, 0.40, 0.50, 0.58, 0.66, 0.74, 1.0]
    fig = go.Figure()
    pivot = h7.groupby(["Day","Hour"])["Spot"].mean().reset_index()

    for i, day in enumerate(days):
        d = pivot[pivot["Day"] == day].sort_values("Hour")
        alpha = ALPHAS[i] if i < len(ALPHAS) else 0.5
        is_last = (i == len(days) - 1)
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d["Spot"],
            mode="lines", name=pd.Timestamp(day).strftime("%a %d %b"),
            line=dict(color=rgba(C1, alpha), width=2.5 if is_last else 1.2),
            hovertemplate=f"<b>{pd.Timestamp(day).strftime('%d %b')}</b> h%{{x}}: %{{y:.1f}}<extra></extra>",
        ))

    avg_by_hour = pivot.groupby("Hour")["Spot"].mean().reset_index()
    fig.add_trace(go.Scatter(
        x=avg_by_hour["Hour"], y=avg_by_hour["Spot"],
        mode="lines", name="7-day avg",
        line=dict(color=C2, width=3.0),
        hovertemplate="<b>7d avg</b> h%{x}: %{y:.1f}<extra></extra>",
    ))

    mn = pivot.groupby("Hour")["Spot"].min()
    mx = pivot.groupby("Hour")["Spot"].max()
    hrs = avg_by_hour["Hour"].tolist()
    fig.add_trace(go.Scatter(
        x=hrs + hrs[::-1], y=mx.tolist() + mn.tolist()[::-1],
        fill="toself", fillcolor=rgba(ACCENT_PRIMARY, 0.08),
        line=dict(color=transparent()), name="Min-Max range",
        hoverinfo="skip",
    ))

    fig.update_xaxes(title_text="Hour of Day", tickmode="array",
                     tickvals=list(range(0, 24, 2)),
                     ticktext=[f"{x}h" for x in range(0, 24, 2)])
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text="<b>Hourly DA Profile — Last 7 Days (one line per day)</b>"),
        hovermode="x unified",
    )
    return fig


# ── DA daily spread ───────────────────────────────────────────────────────────

def mo_chart_da_spread(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    """Daily spread = max hourly - min hourly, monthly avg."""
    if hourly is None or len(hourly) == 0 or "Spot" not in hourly.columns:
        return _mo_stub("DA Daily Spread", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "5Y": 1825, "All": None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]

    h["Day"] = h["Date"].dt.normalize()
    daily = h.groupby("Day")["Spot"].agg(lambda x: x.max() - x.min()).reset_index()
    daily.columns = ["Day","spread"]
    daily["YM"] = pd.to_datetime(daily["Day"].astype(str).str[:7])
    monthly = daily.groupby("YM")["spread"].mean().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly["YM"], y=monthly["spread"],
        marker_color=[rgba(C5, 0.75) if v > 100 else rgba(C2, 0.75) for v in monthly["spread"]],
        marker_line_color=WHT, marker_line_width=0.5,
        text=[f"<b>{v:.0f}</b>" for v in monthly["spread"]],
        textposition="outside",
        textfont=dict(size=10, color=C1, family="Calibri"),
        name="Daily Spread",
        hovertemplate="<b>%{x|%b %Y}</b>: %{y:.1f} EUR/MWh<extra></extra>",
    ))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(text="<b>FR DA Daily Spread — Monthly Avg (Max-Min, EUR/MWh)</b>"))
    return fig


# ── Negative price hours ──────────────────────────────────────────────────────

def mo_chart_neg_hours(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or len(hourly) == 0 or "Spot" not in hourly.columns:
        return _mo_stub("Negative DA Hours", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "5Y": 1825, "All": None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]

    neg = h[h["Spot"] < 0].copy()
    if len(neg) == 0:
        return _mo_stub("Negative DA Hours", "no negative price hours in selected window")

    neg["YM"] = neg["Date"].dt.to_period("M").dt.to_timestamp()
    monthly = neg.groupby("YM").size().reset_index(name="neg_hours")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly["YM"], y=monthly["neg_hours"],
        marker_color=[rgba(C5, 0.75) if v > 100 else rgba(C4, 0.75) for v in monthly["neg_hours"]],
        marker_line_color=WHT, marker_line_width=0.5,
        text=[f"<b>{v}</b>" for v in monthly["neg_hours"]],
        textposition="outside",
        textfont=dict(size=10, color=C1, family="Calibri"),
        name="Negative hours",
        hovertemplate="<b>%{x|%b %Y}</b>: %{y} hours<extra></extra>",
    ))
    fig.update_yaxes(title_text="Hours")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(text="<b>Negative DA Price Hours — Monthly Count</b>"))
    return fig


# ── Price distribution ────────────────────────────────────────────────────────

def mo_chart_distribution(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or len(hourly) == 0 or "Spot" not in hourly.columns:
        return _mo_stub("DA Price Distribution", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "5Y": 1825, "All": None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]

    q5 = h["Spot"].quantile(0.05); q95 = h["Spot"].quantile(0.95)
    med = h["Spot"].median(); mn = h["Spot"].mean()

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=h["Spot"], nbinsx=60,
        marker_color=rgba(C1, 0.65), marker_line_color=WHT, marker_line_width=0.5,
        name="DA Price",
        hovertemplate="Price: %{x:.0f} EUR/MWh<br>Count: %{y}<extra></extra>",
    ))
    for val, label, col in [(med, f"Median {med:.0f}", C2), (mn, f"Mean {mn:.0f}", C4)]:
        fig.add_vline(x=val, line=dict(color=col, width=2, dash="dash"),
                      annotation_text=f"<b>{label}</b>",
                      annotation_font=dict(color=col, size=11, family="Calibri"),
                      annotation_position="top right")
    fig.add_vrect(x0=q5, x1=q95, fillcolor=rgba(C3, 0.12), line_width=0,
                  annotation_text="P5-P95", annotation_position="top left",
                  annotation_font=dict(color=TEXT_FAINT, size=10, family="Calibri"))

    fig.update_xaxes(title_text="EUR/MWh"); fig.update_yaxes(title_text="Hours")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>DA Spot Price Distribution — {zoom}</b>"))
    return fig


# ── Renewable generation ──────────────────────────────────────────────────────

def mo_chart_renewables_7d(hourly: pd.DataFrame) -> go.Figure:
    if hourly is None or len(hourly) == 0:
        return _mo_stub("Renewable Generation", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    h7 = _mo_last_n(h, 7); h7["Day"] = h7["Date"].dt.normalize()
    daily = h7.groupby("Day").agg(SolarMW=("NatMW","mean"), WindMW=("WindMW","mean")).reset_index()

    fig = go.Figure()
    if "SolarMW" in daily.columns and daily["SolarMW"].sum() > 0:
        fig.add_trace(go.Bar(x=daily["Day"], y=daily["SolarMW"], name="Solar",
                             marker_color=rgba(C3, 0.85), marker_line_color=WHT, marker_line_width=0.5))
    if "WindMW" in daily.columns and daily["WindMW"].sum() > 0:
        fig.add_trace(go.Bar(x=daily["Day"], y=daily["WindMW"], name="Wind",
                             marker_color=rgba(C1, 0.70), marker_line_color=WHT, marker_line_width=0.5))

    fig.update_layout(barmode="stack")
    fig.update_xaxes(title_text="Date"); fig.update_yaxes(title_text="Avg MW")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(title=dict(text="<b>Renewable Generation — Last 7 Days (daily avg MW)</b>"))
    return fig


def mo_chart_renewables_profile(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or len(hourly) == 0:
        return _mo_stub("Renewable Hourly Profile", "check hourly_spot.csv")

    h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "5Y": 1825, "All": None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]
    h["Hour"] = h["Date"].dt.hour

    fig = go.Figure()
    if "NatMW" in h.columns and h["NatMW"].sum() > 0:
        sol = h.groupby("Hour")["NatMW"].mean().reset_index()
        fig.add_trace(go.Scatter(x=sol["Hour"], y=sol["NatMW"], mode="lines",
                                 name="Solar", line=dict(color=C3, width=2.5),
                                 fill="tozeroy", fillcolor=rgba(C3, 0.12)))
    if "WindMW" in h.columns and h["WindMW"].sum() > 0:
        win = h.groupby("Hour")["WindMW"].mean().reset_index()
        fig.add_trace(go.Scatter(x=win["Hour"], y=win["WindMW"], mode="lines",
                                 name="Wind", line=dict(color=C1, width=2.5),
                                 fill="tozeroy", fillcolor=rgba(C1, 0.08)))

    fig.update_xaxes(title_text="Hour", tickmode="array",
                     tickvals=list(range(0, 24, 2)),
                     ticktext=[f"{x}h" for x in range(0, 24, 2)])
    fig.update_yaxes(title_text="Avg MW")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(
        title=dict(text=f"<b>Renewable Hourly Profile — {zoom}</b>"),
        hovermode="x unified")
    return fig


# ── Imbalance charts ──────────────────────────────────────────────────────────

def mo_chart_imbalance_lines(bal: pd.DataFrame) -> go.Figure:
    if bal is None or len(bal) == 0:
        return _mo_stub("Imbalance Prices", "run ENTSO-E balancing script")

    fig = go.Figure()
    for col, label, col_clr in [("Imb_Pos","Imbalance Positive", COL_IMB_POS),
                                  ("Imb_Neg","Imbalance Negative", COL_IMB_NEG)]:
        if col not in bal.columns or not bal[col].notna().any():
            continue
        m = _mo_monthly(bal, col)
        fig.add_trace(go.Scatter(x=m["YM"], y=m[col], mode="lines", name=label,
                                 line=dict(color=col_clr, width=2)))

    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(title=dict(
        text="<b>Imbalance Prices — Positive vs Negative (monthly avg)</b>"))
    return fig


def mo_chart_imbalance_spread(bal: pd.DataFrame) -> go.Figure:
    if bal is None or len(bal) == 0 or "Imb_Pos" not in bal.columns or "Imb_Neg" not in bal.columns:
        return _mo_stub("Imbalance Spread", "Imb_Pos / Imb_Neg columns not found")

    mp = _mo_monthly(bal, "Imb_Pos"); mn_df = _mo_monthly(bal, "Imb_Neg")
    merged = mp.merge(mn_df, on="YM", how="inner")
    merged["spread"] = merged["Imb_Pos"] - merged["Imb_Neg"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=merged["YM"], y=merged["spread"],
        marker_color=[rgba(C5, 0.75) if v < 0 else rgba(C2, 0.75) for v in merged["spread"]],
        marker_line_color=WHT, marker_line_width=0.5,
        text=[f"<b>{v:+.0f}</b>" for v in merged["spread"]],
        textposition="outside",
        textfont=dict(size=10, color=C1, family="Calibri"),
        name="Imb Spread",
    ))
    fig.add_hline(y=0, line=dict(color=REF_LINE, width=1.5))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(title=dict(
        text="<b>Imbalance Spread (Imb_Pos - Imb_Neg) — Monthly Avg</b>"))
    return fig


def mo_chart_imbalance_vs_da_new(bal: pd.DataFrame) -> go.Figure:
    """Renamed to avoid collision with existing chart_imbalance_vs_da."""
    if bal is None or len(bal) == 0 or "DA" not in bal.columns:
        return _mo_stub("Imbalance vs DA", "run ENTSO-E balancing script")

    mda = _mo_monthly(bal, "DA")
    fig = go.Figure()
    for col, label, col_clr in [("Imb_Pos","Imb_Pos - DA", COL_IMB_POS),
                                  ("Imb_Neg","Imb_Neg - DA", COL_IMB_NEG)]:
        if col not in bal.columns or not bal[col].notna().any():
            continue
        m = _mo_monthly(bal, col)
        mg = mda.merge(m, on="YM", how="inner")
        mg["delta"] = mg[col] - mg["DA"]
        fig.add_trace(go.Scatter(x=mg["YM"], y=mg["delta"], mode="lines",
                                 name=label, line=dict(color=col_clr, width=2)))

    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1.5))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(title=dict(
        text="<b>Imbalance vs Day-Ahead — Monthly Avg Spread</b>"))
    return fig


def mo_chart_afrr(bal) -> go.Figure:
    if bal is None or len(bal) == 0:
        return _mo_stub("aFRR / mFRR", "run ENTSO-E balancing script")

    fig = go.Figure()
    for col, label, col_clr in [("aFRR","aFRR", COL_AFRR), ("mFRR","mFRR", COL_MFRR)]:
        if col not in bal.columns or not bal[col].notna().any():
            continue
        m = _mo_monthly(bal, col)
        fig.add_trace(go.Scatter(x=m["YM"], y=m[col], mode="lines", name=label,
                                 line=dict(color=col_clr, width=2)))

    if not fig.data:
        return _mo_stub("aFRR / mFRR", "aFRR/mFRR columns not found in balancing_prices.csv")

    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(title=dict(
        text="<b>Ancillary Services — aFRR & mFRR Monthly Avg (France)</b>"))
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# Charts for market_prices.csv (TTF, Brent, EUA)
# Append to bottom of charts.py, after the existing mo_chart_afrr function
# ══════════════════════════════════════════════════════════════════════════════

def mo_chart_eua(mkt: pd.DataFrame, zoom: str) -> go.Figure:
    """EUA carbon price — daily series."""
    if mkt is None or len(mkt) == 0 or "EUA_EUR_tCO2" not in mkt.columns:
        return _mo_stub("Carbon Price (EUA)", "run update_market_data.py")

    h = mkt[mkt["EUA_EUR_tCO2"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825,"All":None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]
    if len(h) == 0:
        return _mo_stub("Carbon Price (EUA)", "no data in selected window")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["Date"], y=h["EUA_EUR_tCO2"],
        mode="lines", name="EUA (€/tCO2)",
        line=dict(color=COL_WIND, width=2),
        fill="tozeroy", fillcolor=rgba(COL_WIND, 0.08),
        hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.2f} €/tCO2<extra></extra>",
    ))
    if len(h) >= 30:
        roll30 = h["EUA_EUR_tCO2"].rolling(30, min_periods=10).mean()
        fig.add_trace(go.Scatter(
            x=h["Date"], y=roll30, mode="lines", name="30d avg",
            line=dict(color=CHART_PALETTE[2], width=1.5, dash="dash"),
        ))
    fig.update_yaxes(title_text="€/tCO2")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(
        title=dict(text=f"<b>Carbon Price — EUA (€/tCO2) — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mo_chart_ttf(mkt: pd.DataFrame, zoom: str) -> go.Figure:
    """TTF gas futures price — daily series."""
    if mkt is None or len(mkt) == 0 or "TTF_EUR_MWh" not in mkt.columns:
        return _mo_stub("TTF Gas Price", "run update_market_data.py")

    h = mkt[mkt["TTF_EUR_MWh"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825,"All":None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]
    if len(h) == 0:
        return _mo_stub("TTF Gas Price", "no data in selected window")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["Date"], y=h["TTF_EUR_MWh"],
        mode="lines", name="TTF (€/MWh)",
        line=dict(color=C4, width=2),
        fill="tozeroy", fillcolor=rgba(C4, 0.08),
        hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.2f} €/MWh<extra></extra>",
    ))
    if len(h) >= 30:
        roll30 = h["TTF_EUR_MWh"].rolling(30, min_periods=10).mean()
        fig.add_trace(go.Scatter(
            x=h["Date"], y=roll30, mode="lines", name="30d avg",
            line=dict(color=C5, width=1.5, dash="dash"),
        ))
    fig.update_yaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(
        title=dict(text=f"<b>TTF Gas Price (€/MWh) — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mo_chart_brent(mkt: pd.DataFrame, zoom: str) -> go.Figure:
    """Brent crude oil price — daily series."""
    if mkt is None or len(mkt) == 0 or "Brent_USD_bbl" not in mkt.columns:
        return _mo_stub("Brent Oil Price", "run update_market_data.py")

    h = mkt[mkt["Brent_USD_bbl"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825,"All":None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]
    if len(h) == 0:
        return _mo_stub("Brent Oil Price", "no data in selected window")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["Date"], y=h["Brent_USD_bbl"],
        mode="lines", name="Brent ($/bbl)",
        line=dict(color=CHART_PALETTE[5], width=2),
        fill="tozeroy", fillcolor=rgba(CHART_PALETTE[5], 0.08),
        hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.2f} $/bbl<extra></extra>",
    ))
    if len(h) >= 30:
        roll30 = h["Brent_USD_bbl"].rolling(30, min_periods=10).mean()
        fig.add_trace(go.Scatter(
            x=h["Date"], y=roll30, mode="lines", name="30d avg",
            line=dict(color="#386641", width=1.5, dash="dash"),
        ))
    fig.update_yaxes(title_text="$/bbl")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(
        title=dict(text=f"<b>Brent Crude Oil ($/bbl) — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mo_chart_commodity_kpis(mkt: pd.DataFrame) -> dict:
    """
    Returns dict of last values for KPI display.
    Keys: ttf_last, ttf_chg, brent_last, brent_chg, eua_last, eua_chg
    """
    out = {}
    if mkt is None or len(mkt) == 0:
        return out
    mkt = mkt.copy(); mkt["Date"] = pd.to_datetime(mkt["Date"])
    for col, key in [("TTF_EUR_MWh","ttf"), ("Brent_USD_bbl","brent"), ("EUA_EUR_tCO2","eua")]:
        if col in mkt.columns and mkt[col].notna().any():
            s = mkt[mkt[col].notna()][col]
            out[f"{key}_last"] = s.iloc[-1]
            out[f"{key}_chg"]  = s.iloc[-1] - s.iloc[-2] if len(s) >= 2 else float("nan")
    return out

# ══════════════════════════════════════════════════════════════════════════════
# Charts for xborder_da_prices.csv and fcr_prices.csv
# Append to bottom of charts.py (after mo_chart_afrr / commodity charts)
# ══════════════════════════════════════════════════════════════════════════════

# Country display config
_XBORDER_COUNTRIES = {
    "DE": {"label": "Germany",     "color": CHART_PALETTE[2]},
    "BE": {"label": "Belgium",     "color": "#2A9D8F"},
    "ES": {"label": "Spain",       "color": "#E9C46A"},
    "IT": {"label": "Italy",       "color": "#F4A261"},
    "NL": {"label": "Netherlands", "color": "#E76F51"},
}


def _xb_last_n(df: pd.DataFrame, n: int) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    cutoff = df["Date"].max() - pd.Timedelta(days=n)
    return df[df["Date"] >= cutoff]


def _xb_daily_avg(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Resample hourly DA to daily average."""
    d = df[df[col].notna()].copy()
    d["Date"] = pd.to_datetime(d["Date"])
    d["Day"] = d["Date"].dt.normalize()
    return d.groupby("Day")[col].mean().reset_index().rename(columns={"Day": "Date"})


# ── Country ranking bar (avg last 7 days) ─────────────────────────────────────

def mo_chart_country_ranking(xb: pd.DataFrame, fr_hourly: pd.DataFrame) -> go.Figure:
    """
    Average DA spot price last 7 days — FR + DE/BE/ES/IT/NL.
    Bar chart ranked low to high.
    """
    if (xb is None or len(xb) == 0) and (fr_hourly is None or len(fr_hourly) == 0):
        return _mo_stub("Country DA Ranking", "run update_entsoe_xborder.py")

    rows = []

    # FR from hourly_spot.csv
    if fr_hourly is not None and len(fr_hourly) > 0 and "Spot" in fr_hourly.columns:
        h = fr_hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
        h7 = _mo_last_n(h, 7)
        if h7["Spot"].notna().any():
            rows.append({"Country": "FR", "Label": "France",
                         "Avg": h7["Spot"].mean(), "Color": C1})

    # Other countries from xborder_da_prices.csv
    if xb is not None and len(xb) > 0:
        xb7 = _xb_last_n(xb, 7)
        for code, cfg in _XBORDER_COUNTRIES.items():
            if code in xb7.columns and xb7[code].notna().any():
                rows.append({"Country": code, "Label": cfg["label"],
                             "Avg": xb7[code].mean(), "Color": cfg["color"]})

    if not rows:
        return _mo_stub("Country DA Ranking", "no data yet — run full refresh")

    df_rank = pd.DataFrame(rows).sort_values("Avg")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_rank["Avg"],
        y=df_rank["Label"],
        orientation="h",
        marker_color=df_rank["Color"].tolist(),
        marker_line_color=WHT, marker_line_width=1,
        text=[f"<b>{v:.1f}</b>" for v in df_rank["Avg"]],
        textposition="outside",
        textfont=dict(size=12, color=C1, family="Calibri"),
        hovertemplate="<b>%{y}</b>: %{x:.1f} EUR/MWh<extra></extra>",
    ))
    fig.update_xaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(
        title=dict(text="<b>DA Spot Price by Country — Avg Last 7 Days (EUR/MWh)</b>"),
        margin=dict(l=100, r=60, t=40, b=40),
    )
    return fig


# ── Spread vs France ──────────────────────────────────────────────────────────

def mo_chart_spread_vs_fr(xb: pd.DataFrame, fr_hourly: pd.DataFrame,
                           zoom: str) -> go.Figure:
    """
    Country DA minus France DA — monthly average.
    Positive = country more expensive than FR.
    """
    if xb is None or len(xb) == 0:
        return _mo_stub("Spread vs France", "run update_entsoe_xborder.py")

    # Build daily FR average
    if fr_hourly is None or len(fr_hourly) == 0 or "Spot" not in fr_hourly.columns:
        return _mo_stub("Spread vs France", "no FR spot data in hourly_spot.csv")

    h = fr_hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])

    # Apply zoom
    zoom_days = {"7D":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825,"All":None}
    n = zoom_days.get(zoom)
    if n:
        cutoff = h["Date"].max() - pd.Timedelta(days=n)
        h = h[h["Date"] >= cutoff]
        xb = _xb_last_n(xb, n)

    # FR daily avg
    h["Day"] = h["Date"].dt.normalize()
    fr_daily = h.groupby("Day")["Spot"].mean().reset_index()
    fr_daily.columns = ["Date", "FR"]
    fr_daily["Date"] = pd.to_datetime(fr_daily["Date"])

    # Merge with xborder
    xb2 = xb.copy(); xb2["Date"] = pd.to_datetime(xb2["Date"]).dt.normalize()
    # xborder is already hourly — resample to daily
    xb_daily = xb2.copy()
    xb_daily["Date"] = pd.to_datetime(xb_daily["Date"]).dt.normalize()
    num_cols = [c for c in _XBORDER_COUNTRIES.keys() if c in xb_daily.columns]
    xb_daily = xb_daily.groupby("Date")[num_cols].mean().reset_index()

    merged = fr_daily.merge(xb_daily, on="Date", how="inner")

    # Monthly average of spread
    merged["YM"] = pd.to_datetime(merged["Date"].astype(str).str[:7])

    fig = go.Figure()
    has_data = False
    for code, cfg in _XBORDER_COUNTRIES.items():
        if code not in merged.columns:
            continue
        merged[f"spread_{code}"] = merged[code] - merged["FR"]
        monthly = merged.groupby("YM")[f"spread_{code}"].mean().reset_index()
        if monthly[f"spread_{code}"].notna().any():
            fig.add_trace(go.Scatter(
                x=monthly["YM"], y=monthly[f"spread_{code}"],
                mode="lines", name=cfg["label"],
                line=dict(color=cfg["color"], width=2),
                hovertemplate=f"<b>{cfg['label']}</b> %{{x|%b %Y}}: %{{y:+.1f}} EUR/MWh<extra></extra>",
            ))
            has_data = True

    if not has_data:
        return _mo_stub("Spread vs France", "no xborder data yet — run full refresh")

    fig.add_hline(y=0, line=dict(color=REF_LINE, width=1.5, dash="dot"),
                  annotation_text="= France price",
                  annotation_font=dict(color=TEXT_FAINT, size=11, family="Calibri"),
                  annotation_position="top left")
    fig.update_yaxes(title_text="EUR/MWh (vs FR)")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(
        title=dict(text=f"<b>DA Spread vs France — Monthly Avg — {zoom}</b>"),
        hovermode="x unified",
    )
    return fig


# ── Multi-country DA historical lines ─────────────────────────────────────────

def mo_chart_country_da_history(xb: pd.DataFrame, fr_hourly: pd.DataFrame,
                                 zoom: str) -> go.Figure:
    """
    Historical DA price lines for all countries — daily avg, same chart.
    """
    if xb is None or len(xb) == 0:
        return _mo_stub("Country DA History", "run update_entsoe_xborder.py")

    zoom_days = {"7D":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825,"All":None}
    n = zoom_days.get(zoom)

    fig = go.Figure()

    # FR
    if fr_hourly is not None and "Spot" in fr_hourly.columns:
        h = fr_hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
        if n:
            h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]
        fr_d = _xb_daily_avg(h.rename(columns={"Spot":"FR"}), "FR")
        if len(fr_d) > 0:
            fig.add_trace(go.Scatter(
                x=fr_d["Date"], y=fr_d["FR"], mode="lines",
                name="France", line=dict(color=C1, width=2.5),
                hovertemplate="<b>France</b> %{x|%d %b}: %{y:.1f}<extra></extra>",
            ))

    # Other countries
    xb2 = xb.copy(); xb2["Date"] = pd.to_datetime(xb2["Date"])
    if n:
        xb2 = xb2[xb2["Date"] >= xb2["Date"].max() - pd.Timedelta(days=n)]

    for code, cfg in _XBORDER_COUNTRIES.items():
        if code not in xb2.columns or not xb2[code].notna().any():
            continue
        d = _xb_daily_avg(xb2, code)
        fig.add_trace(go.Scatter(
            x=d["Date"], y=d[code], mode="lines",
            name=cfg["label"], line=dict(color=cfg["color"], width=1.5),
            hovertemplate=f"<b>{cfg['label']}</b> %{{x|%d %b}}: %{{y:.1f}}<extra></extra>",
        ))

    if not fig.data:
        return _mo_stub("Country DA History", "no data yet")

    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>DA Spot Price — France vs Neighbours — {zoom}</b>"),
        hovermode="x unified",
    )
    return fig


# ── FCR price chart ───────────────────────────────────────────────────────────

def mo_chart_fcr(fcr: pd.DataFrame, zoom: str) -> go.Figure:
    """FCR contracted reserve price — France — daily series (EUR/MW/day)."""
    if fcr is None or len(fcr) == 0 or "FCR_EUR_MW_day" not in fcr.columns:
        return _mo_stub("FCR Price (France)", "run update_entsoe_xborder.py --fcr-only")

    h = fcr[fcr["FCR_EUR_MW_day"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    zoom_days = {"7D":7,"1M":30,"3M":90,"1Y":365,"2Y":730,"5Y":1825,"All":None}
    n = zoom_days.get(zoom)
    if n:
        h = h[h["Date"] >= h["Date"].max() - pd.Timedelta(days=n)]
    if len(h) == 0:
        return _mo_stub("FCR Price (France)", "no data in selected window")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["Date"], y=h["FCR_EUR_MW_day"],
        mode="lines", name="FCR FR (€/MW/day)",
        line=dict(color=COL_AFRR, width=2),
        fill="tozeroy", fillcolor=rgba(COL_AFRR, 0.08),
        hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.1f} €/MW/day<extra></extra>",
    ))
    if len(h) >= 30:
        roll30 = h["FCR_EUR_MW_day"].rolling(30, min_periods=10).mean()
        fig.add_trace(go.Scatter(
            x=h["Date"], y=roll30, mode="lines", name="30d avg",
            line=dict(color=rgba(COL_AFRR, 1.0), width=1.5, dash="dash"),
        ))

    fig.update_yaxes(title_text="€/MW/day")
    plotly_base(fig, h=CHART_H_SM)
    fig.update_layout(
        title=dict(text=f"<b>FCR Contracted Reserve Price — France (€/MW/day) — {zoom}</b>"),
        hovermode="x unified",
    )
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# charts_tab6_v2.py — KAL-EL Market Overview v2
# All functions prefixed mk_ to avoid conflicts with existing mo_* functions.
# APPEND this entire file to the bottom of charts.py
# ══════════════════════════════════════════════════════════════════════════════

# ── Constants ─────────────────────────────────────────────────────────────────
MK_ZOOM_OPTS  = ["7D", "1M", "3M", "1Y", "2Y", "5Y", "All"]
MK_ZOOM_DAYS  = {"7D": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "5Y": 1825, "All": None}
MK_BLUE       = "#5B8DEF"   # wind blue — COL_WIND
MK_GREEN      = "#6A994E"   # chart palette green
MK_PURPLE     = "#9B59B6"   # aFRR purple — COL_AFRR

# ── Internal helpers ───────────────────────────────────────────────────────────

def _mk_clip(df: pd.DataFrame, zoom: str) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    n = MK_ZOOM_DAYS.get(zoom)
    if n:
        df = df[df["Date"] >= df["Date"].max() - pd.Timedelta(days=n)]
    return df


def _mk_daily(df: pd.DataFrame, col: str) -> pd.DataFrame:
    d = df[df[col].notna()].copy()
    d["Day"] = pd.to_datetime(d["Date"]).dt.normalize()
    return d.groupby("Day")[col].mean().reset_index().rename(columns={"Day": "Date"})


def _mk_monthly(df: pd.DataFrame, col: str) -> pd.DataFrame:
    d = df[df[col].notna()].copy()
    d["YM"] = pd.to_datetime(d["Date"]).dt.to_period("M").dt.to_timestamp()
    return d.groupby("YM")[col].mean().reset_index()


def _mk_stub(title: str, note: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=f"<b>{title}</b><br><span style='font-size:12px;color:#888'>{note}</span>",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color=C1, family="Calibri, Arial"), align="center",
    )
    fig.update_layout(height=300, paper_bgcolor=WHT, plot_bgcolor=WHT,
                      margin=dict(l=20, r=20, t=20, b=20),
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def _mk_table(rows: list, headers: list) -> go.Figure:
    """Compact table figure to place beside a chart."""
    cols = list(zip(*rows)) if rows else [[] for _ in headers]
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=[f"<b>{h}</b>" for h in headers],
            fill_color=C1, font=dict(color=WHT, size=12, family="Calibri"),
            align="left", height=28,
        ),
        cells=dict(
            values=list(cols),
            fill_color=[[WHT if i % 2 == 0 else BG_PAGE for i in range(len(rows))]
                        for _ in headers],
            font=dict(color=C1, size=12, family="Calibri"),
            align="left", height=26,
        ),
    )])
    fig.update_layout(height=max(120, 28 + len(rows) * 26 + 20),
                      margin=dict(l=0, r=0, t=0, b=0),
                      paper_bgcolor=WHT)
    return fig


def _mk_spot_line(fig, x, y, name, color, width=1.5, fill=True):
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines", name=name,
        line=dict(color=color, width=width),
        fill="tozeroy" if fill else None,
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.07)" if fill else None,
        hovertemplate=f"<b>{name}</b>: %{{y:.1f}}<extra></extra>",
    ))


# ── KPIs ─────────────────────────────────────────────────────────────────────

def mk_kpis(hourly: pd.DataFrame, bal, mkt) -> dict:
    out = {}
    # DA from balancing
    if bal is not None and len(bal) > 0 and "DA" in bal.columns:
        b = bal.copy(); b["Date"] = pd.to_datetime(b["Date"])
        b7  = _mk_clip(b, "7D")
        b30 = _mk_clip(b, "1M")
        b7p = b[(b["Date"] < b7["Date"].min()) &
                (b["Date"] >= b7["Date"].min() - pd.Timedelta(days=7))]
        out["da_7d"]      = b7["DA"].mean()  if b7["DA"].notna().any()  else float("nan")
        out["da_30d"]     = b30["DA"].mean() if b30["DA"].notna().any() else float("nan")
        out["da_7d_prev"] = b7p["DA"].mean() if len(b7p) > 0 and b7p["DA"].notna().any() else float("nan")
        b7["Day"] = b7["Date"].dt.normalize()
        sp = b7.groupby("Day")["DA"].agg(lambda x: x.max() - x.min())
        out["spread_7d"] = sp.mean() if len(sp) > 0 else float("nan")
        if "aFRR" in b7.columns and b7["aFRR"].notna().any():
            out["afrr_7d"] = b7["aFRR"].mean()
    # Solar / Wind
    if hourly is not None and len(hourly) > 0:
        h = hourly.copy(); h["Date"] = pd.to_datetime(h["Date"])
        h7  = _mk_clip(h, "7D")
        h7p = h[(h["Date"] < h7["Date"].min()) &
                (h["Date"] >= h7["Date"].min() - pd.Timedelta(days=7))]
        for col, key in [("NatMW", "solar"), ("WindMW", "wind")]:
            if col in h7.columns:
                out[f"{key}_7d"]      = h7[col].mean()  if h7[col].notna().any()  else float("nan")
                out[f"{key}_7d_prev"] = h7p[col].mean() if len(h7p) > 0 and h7p[col].notna().any() else float("nan")
    # Commodities
    if mkt is not None and len(mkt) > 0:
        m = mkt.copy(); m["Date"] = pd.to_datetime(m["Date"])
        m7  = _mk_clip(m, "7D")
        m7p = m[(m["Date"] < m7["Date"].min()) &
                (m["Date"] >= m7["Date"].min() - pd.Timedelta(days=7))]
        for col, key in [("TTF_EUR_MWh","ttf"), ("Brent_USD_bbl","brent"), ("EUA_EUR_tCO2","eua")]:
            if col in m.columns and m[col].notna().any():
                s   = m[m[col].notna()][col]
                sp  = m7[col].dropna()  if col in m7.columns  else pd.Series()
                spp = m7p[col].dropna() if col in m7p.columns else pd.Series()
                out[f"{key}_last"]     = s.iloc[-1]
                out[f"{key}_7d"]       = sp.mean()  if len(sp)  > 0 else float("nan")
                out[f"{key}_7d_prev"]  = spp.mean() if len(spp) > 0 else float("nan")
    return out


# ── FR DA Spot ────────────────────────────────────────────────────────────────

def mk_chart_spot(hourly: pd.DataFrame, zoom: str, mode: str) -> go.Figure:
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("FR DA Spot", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    fig = go.Figure()
    if mode == "Hourly":
        fig.add_trace(go.Scatter(
            x=h["Date"], y=h["Spot"], mode="lines", name="Hourly DA",
            line=dict(color=C1, width=0.8),
            fill="tozeroy", fillcolor=rgba(TEXT_DARK, 0.06),
            hovertemplate="<b>%{x|%d %b %H:%M}</b>: %{y:.1f} €/MWh<extra></extra>",
        ))
    else:
        d = _mk_daily(h, "Spot")
        fig.add_trace(go.Scatter(
            x=d["Date"], y=d["Spot"], mode="lines", name="Daily avg",
            line=dict(color=C1, width=1.2),
            fill="tozeroy", fillcolor=rgba(TEXT_DARK, 0.06),
            hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.1f} €/MWh<extra></extra>",
        ))
        if len(d) >= 7:
            fig.add_trace(go.Scatter(
                x=d["Date"], y=d["Spot"].rolling(7, min_periods=3).mean(),
                mode="lines", name="7D avg", line=dict(color=C2, width=2),
                hovertemplate="7D avg: %{y:.1f}<extra></extra>"))
        if len(d) >= 30:
            fig.add_trace(go.Scatter(
                x=d["Date"], y=d["Spot"].rolling(30, min_periods=10).mean(),
                mode="lines", name="30D avg", line=dict(color=C4, width=2),
                hovertemplate="30D avg: %{y:.1f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1))
    fig.update_yaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_LG)
    fig.update_layout(
        title=dict(text=f"<b>FR Day-Ahead Spot Price — {mode} — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_table_spot(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    s = h["Spot"].dropna()
    if len(s) == 0:
        return _mk_stub("", "no data")
    d7  = _mk_clip(hourly.copy(), "7D")["Spot"].dropna()
    d30 = _mk_clip(hourly.copy(), "1M")["Spot"].dropna()
    rows = [
        ("Last value",   f"{s.iloc[-1]:.1f} €/MWh"),
        ("Avg (window)", f"{s.mean():.1f} €/MWh"),
        ("Avg 7D",       f"{d7.mean():.1f} €/MWh"  if len(d7)  > 0 else "N/A"),
        ("Avg 30D",      f"{d30.mean():.1f} €/MWh" if len(d30) > 0 else "N/A"),
        ("Min",          f"{s.min():.1f} €/MWh"),
        ("Max",          f"{s.max():.1f} €/MWh"),
        ("Std dev",      f"{s.std():.1f} €/MWh"),
        ("Neg hours",    f"{(h['Spot'] < 0).sum():,}"),
    ]
    return _mk_table(rows, ["Metric", "Value"])


# ── DA Spread ─────────────────────────────────────────────────────────────────

def mk_chart_spread(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("DA Spread", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    h["Day"] = pd.to_datetime(h["Date"]).dt.normalize()
    daily = h.groupby("Day")["Spot"].agg(lambda x: x.max() - x.min()).reset_index()
    daily.columns = ["Date", "spread"]
    roll30 = daily["spread"].rolling(30, min_periods=5).mean()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["Date"], y=daily["spread"], name="Daily spread",
        marker_color=[rgba(C5, 0.7) if v > 100 else rgba(C2, 0.5) for v in daily["spread"]],
        marker_line_width=0,
        hovertemplate="<b>%{x|%d %b}</b>: %{y:.1f} €/MWh<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["Date"], y=roll30, mode="lines", name="30D rolling avg",
        line=dict(color=C1, width=2.5),
        hovertemplate="30D avg: %{y:.1f}<extra></extra>",
    ))
    fig.update_yaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>DA Daily Spread (Max−Min) + 30D Rolling Avg — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_table_spread(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    h["Day"] = pd.to_datetime(h["Date"]).dt.normalize()
    daily = h.groupby("Day")["Spot"].agg(lambda x: x.max() - x.min())
    if len(daily) == 0:
        return _mk_stub("", "no data")
    rows = [
        ("Avg spread",    f"{daily.mean():.1f} €/MWh"),
        ("Max spread",    f"{daily.max():.1f} €/MWh"),
        ("Min spread",    f"{daily.min():.1f} €/MWh"),
        ("Days > 100€",   f"{(daily > 100).sum()}"),
        ("Days > 200€",   f"{(daily > 200).sum()}"),
    ]
    return _mk_table(rows, ["Metric", "Value"])


# ── Negative price hours ──────────────────────────────────────────────────────

def mk_chart_neg_bars(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("Negative Hours", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    neg = h[h["Spot"] < 0].copy()
    if len(neg) == 0:
        return _mk_stub("Negative Hours", "no negative prices in window")
    neg["Day"] = pd.to_datetime(neg["Date"]).dt.normalize()
    daily = neg.groupby("Day").size().reset_index(name="n")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["Day"], y=daily["n"],
        marker_color=[rgba(C5, 0.8) if v >= 8 else rgba(C4, 0.7) if v >= 3 else rgba(C3, 0.7)
                      for v in daily["n"]],
        marker_line_width=0,
        hovertemplate="<b>%{x|%d %b %Y}</b>: %{y}h negative<extra></extra>",
    ))
    fig.update_yaxes(title_text="Hours")
    plotly_base(fig, h=CHART_H_MD, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Daily Negative DA Price Hours — {zoom}</b>"))
    return fig


def mk_chart_neg_calendar(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    """Calendar heatmap — each cell = one day, color = negative hours count."""
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("Negative Hours Calendar", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    h["Date"] = pd.to_datetime(h["Date"])
    h["Day"]  = h["Date"].dt.normalize()
    neg = h[h["Spot"] < 0].groupby("Day").size().reset_index(name="n")
    # Build full date range
    all_days = pd.DataFrame({"Day": pd.date_range(h["Day"].min(), h["Day"].max(), freq="D")})
    neg = all_days.merge(neg, on="Day", how="left").fillna(0)
    neg["week"]    = neg["Day"].dt.isocalendar().week.astype(int)
    neg["year"]    = neg["Day"].dt.isocalendar().year.astype(int)
    neg["weekday"] = neg["Day"].dt.weekday  # 0=Mon
    neg["yw"]      = neg["year"].astype(str) + "-W" + neg["week"].astype(str).str.zfill(2)
    weeks   = sorted(neg["yw"].unique())
    dow_lbl = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    z  = np.full((7, len(weeks)), np.nan)
    tt = [["" for _ in weeks] for _ in range(7)]
    for _, row in neg.iterrows():
        wi = weeks.index(row["yw"])
        di = int(row["weekday"])
        z[di][wi]  = row["n"]
        tt[di][wi] = f"{row['Day'].strftime('%d %b %Y')}: {int(row['n'])}h"
    fig = go.Figure(data=go.Heatmap(
        z=z, x=weeks, y=dow_lbl,
        colorscale=[[0,"#2A9D8F"],[0.01,"#E9C46A"],[0.4,"#F4A261"],[1,"#E76F51"]],
        zmin=0, zmax=max(neg["n"].max(), 1),
        text=tt, hovertemplate="%{text}<extra></extra>",
        showscale=True,
        colorbar=dict(title=dict(text="Hours", font=dict(size=11, color=C1)),
                      tickfont=dict(size=10, color=C1), thickness=12),
    ))
    # Show only month labels on x axis
    tick_vals, tick_txt = [], []
    for i, w in enumerate(weeks):
        yr, wn = int(w.split("-W")[0]), int(w.split("-W")[1])
        d = pd.Timestamp.fromisocalendar(yr, wn, 1)
        if d.day <= 7:
            tick_vals.append(w)
            tick_txt.append(d.strftime("%b %Y"))
    fig.update_xaxes(tickvals=tick_vals, ticktext=tick_txt,
                     tickfont=dict(size=11, color=C1, family="Calibri"))
    fig.update_yaxes(tickfont=dict(size=11, color=C1, family="Calibri"))
    plotly_base(fig, h=CHART_H_XS, show_legend=False)
    fig.update_layout(
        title=dict(text=f"<b>Negative Price Hours — Calendar Heatmap — {zoom}</b>"),
        margin=dict(l=50, r=80, t=40, b=40))
    return fig


# ── Distribution ──────────────────────────────────────────────────────────────

def mk_chart_distribution(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    if hourly is None or "Spot" not in hourly.columns:
        return _mk_stub("Distribution", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    s = h["Spot"].dropna()
    if len(s) == 0:
        return _mk_stub("Distribution", "no data")
    med = float(s.median()); mn = float(s.mean())
    q5  = float(s.quantile(0.05)); q95 = float(s.quantile(0.95))
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=s, nbinsx=60,
        marker_color=rgba(C1, 0.6), marker_line_color=WHT, marker_line_width=0.5,
        name="DA Price",
        hovertemplate="Price: %{x:.0f} €/MWh — Count: %{y}<extra></extra>",
    ))
    fig.add_vrect(x0=q5, x1=q95, fillcolor=rgba(C3, 0.10), line_width=0,
                  annotation_text="P5–P95", annotation_position="top left",
                  annotation_font=dict(color=TEXT_FAINT, size=10, family="Calibri"))
    # Median and mean on separate y positions to avoid overlap
    ymax = float(np.histogram(s, bins=60)[0].max())
    for val, label, col, ypos in [
        (med, f"Median: {med:.1f} €/MWh", C2, ymax * 0.95),
        (mn,  f"Mean: {mn:.1f} €/MWh",    C4, ymax * 0.80),
    ]:
        fig.add_vline(x=val, line=dict(color=col, width=2, dash="dash"))
        fig.add_annotation(x=val, y=ypos, text=f"<b>{label}</b>",
                           showarrow=False, xanchor="left", xshift=6,
                           font=dict(color=col, size=11, family="Calibri"),
                           bgcolor="rgba(255,255,255,0.85)", bordercolor=col, borderwidth=1)
    fig.update_xaxes(title_text="€/MWh")
    fig.update_yaxes(title_text="Hours")
    plotly_base(fig, h=CHART_H_MD, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>DA Spot Price Distribution — {zoom}</b>"))
    return fig


# ── Market drivers (one per chart) ────────────────────────────────────────────

def _mk_commodity_chart(mkt, col, label, unit, color, zoom, title) -> go.Figure:
    if mkt is None or len(mkt) == 0 or col not in mkt.columns:
        return _mk_stub(title, "run update_market_data.py")
    h = _mk_clip(mkt[mkt[col].notna()].copy(), zoom)
    if len(h) == 0:
        return _mk_stub(title, "no data in window")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["Date"], y=h[col], mode="lines", name=label,
        line=dict(color=color, width=1.2),
        fill="tozeroy", fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.07)",
        hovertemplate=f"<b>%{{x|%d %b %Y}}</b>: %{{y:.2f}} {unit}<extra></extra>",
    ))
    if len(h) >= 30:
        fig.add_trace(go.Scatter(
            x=h["Date"], y=h[col].rolling(30, min_periods=10).mean(),
            mode="lines", name="30D avg", line=dict(color=C1, width=2),
            hovertemplate=f"30D avg: %{{y:.2f}} {unit}<extra></extra>"))
    if len(h) >= 7:
        fig.add_trace(go.Scatter(
            x=h["Date"], y=h[col].rolling(7, min_periods=3).mean(),
            mode="lines", name="7D avg", line=dict(color=color, width=2, dash="dash"),
            hovertemplate=f"7D avg: %{{y:.2f}} {unit}<extra></extra>"))
    fig.update_yaxes(title_text=unit)
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>{title} — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_chart_eua(mkt, zoom) -> go.Figure:
    return _mk_commodity_chart(mkt, "EUA_EUR_tCO2", "EUA", "€/tCO2",
                               MK_BLUE, zoom, "Carbon Price (EUA)")


def mk_chart_ttf(mkt, zoom) -> go.Figure:
    return _mk_commodity_chart(mkt, "TTF_EUR_MWh", "TTF", "€/MWh",
                               C4, zoom, "TTF Gas Price")


def mk_chart_brent(mkt, zoom) -> go.Figure:
    return _mk_commodity_chart(mkt, "Brent_USD_bbl", "Brent", "$/bbl",
                               MK_GREEN, zoom, "Brent Crude Oil")


def mk_table_commodity(mkt, col, unit) -> go.Figure:
    if mkt is None or len(mkt) == 0 or col not in mkt.columns:
        return _mk_stub("", "no data")
    s = mkt[mkt[col].notna()][col]
    if len(s) == 0:
        return _mk_stub("", "no data")
    m = mkt.copy(); m["Date"] = pd.to_datetime(m["Date"])
    d7  = _mk_clip(m[m[col].notna()], "7D")[col]
    d30 = _mk_clip(m[m[col].notna()], "1M")[col]
    chg_1d = float(s.iloc[-1] - s.iloc[-2]) if len(s) >= 2 else float("nan")
    rows = [
        ("Last",     f"{s.iloc[-1]:.2f} {unit}"),
        ("D-1 chg",  f"{chg_1d:+.2f} {unit}" if chg_1d == chg_1d else "N/A"),
        ("Avg 7D",   f"{d7.mean():.2f} {unit}"  if len(d7)  > 0 else "N/A"),
        ("Avg 30D",  f"{d30.mean():.2f} {unit}" if len(d30) > 0 else "N/A"),
        ("52W High", f"{s.tail(365).max():.2f} {unit}"),
        ("52W Low",  f"{s.tail(365).min():.2f} {unit}"),
    ]
    return _mk_table(rows, ["Metric", "Value"])


# ── Renewable generation ──────────────────────────────────────────────────────

def mk_chart_renewables_lines(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    """Wind + Solar as separate lines with rolling avg."""
    if hourly is None or len(hourly) == 0:
        return _mk_stub("Renewables", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    d = _mk_daily(h.rename(columns={"Spot": "Spot"}), "Spot") if "Spot" in h.columns else pd.DataFrame()
    fig = go.Figure()
    for col, label, color in [("NatMW", "Solar", C3), ("WindMW", "Wind", C2)]:
        if col not in h.columns or h[col].sum() == 0:
            continue
        dd = _mk_daily(h, col)
        fig.add_trace(go.Scatter(
            x=dd["Date"], y=dd[col], mode="lines", name=label,
            line=dict(color=color, width=1.5),
            hovertemplate=f"<b>{label}</b> %{{x|%d %b}}: %{{y:.0f}} MW<extra></extra>",
        ))
        if len(dd) >= 7:
            fig.add_trace(go.Scatter(
                x=dd["Date"], y=dd[col].rolling(7, min_periods=3).mean(),
                mode="lines", name=f"{label} 7D avg",
                line=dict(color=color, width=2.5, dash="dash"),
                hovertemplate=f"{label} 7D avg: %{{y:.0f}} MW<extra></extra>",
            ))
    if not fig.data:
        return _mk_stub("Renewables", "NatMW / WindMW not in hourly_spot.csv")
    fig.update_yaxes(title_text="MW")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>Wind & Solar Generation (Daily Avg + 7D Rolling) — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_chart_renewables_mix(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    """Stacked area — Wind + Solar mix."""
    if hourly is None or len(hourly) == 0:
        return _mk_stub("Renewable Mix", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    # Resample to 6h for readability when zoomed out
    h["Date"] = pd.to_datetime(h["Date"])
    freq = "1h" if MK_ZOOM_DAYS.get(zoom, 999) and MK_ZOOM_DAYS.get(zoom, 999) <= 30 else "6h"
    h2 = h.set_index("Date").resample(freq).mean(numeric_only=True).reset_index()
    fig = go.Figure()
    for col, label, color in [("NatMW", "Solar", C3), ("WindMW", "Wind", C2)]:
        if col not in h2.columns or h2[col].sum() == 0:
            continue
        fig.add_trace(go.Scatter(
            x=h2["Date"], y=h2[col], mode="lines", name=label,
            stackgroup="one",
            line=dict(color=color, width=0.5),
            fillcolor=rgba(color, 0.7),
            hovertemplate=f"<b>{label}</b>: %{{y:.0f}} MW<extra></extra>",
        ))
    if not fig.data:
        return _mk_stub("Renewable Mix", "no generation data")
    fig.update_yaxes(title_text="MW")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>Renewable Generation Mix — Stacked Area — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_chart_renewables_hourly(hourly: pd.DataFrame, zoom: str) -> go.Figure:
    """Raw hourly data — Wind + Solar — no averaging."""
    if hourly is None or len(hourly) == 0:
        return _mk_stub("Hourly Generation", "no data")
    h = _mk_clip(hourly.copy(), zoom)
    h["Date"] = pd.to_datetime(h["Date"])
    fig = go.Figure()
    for col, label, color in [("NatMW", "Solar", C3), ("WindMW", "Wind", C2)]:
        if col not in h.columns or h[col].sum() == 0:
            continue
        fig.add_trace(go.Scatter(
            x=h["Date"], y=h[col], mode="lines", name=label,
            line=dict(color=color, width=0.8),
            hovertemplate=f"<b>{label}</b> %{{x|%d %b %H:%M}}: %{{y:.0f}} MW<extra></extra>",
        ))
    if not fig.data:
        return _mk_stub("Hourly Generation", "no generation data")
    fig.update_yaxes(title_text="MW")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>Renewable Generation — Raw Hourly — {zoom}</b>"),
        hovermode="x unified")
    return fig


# ── Imbalance ─────────────────────────────────────────────────────────────────

def _mk_imb_chart(bal, col_a, col_b, label_a, label_b, color_a, color_b,
                  zoom, title, ytitle="€/MWh") -> go.Figure:
    if bal is None or len(bal) == 0:
        return _mk_stub(title, "run ENTSO-E balancing script")
    h = _mk_clip(bal.copy(), zoom)
    fig = go.Figure()
    for col, label, color in [(col_a, label_a, color_a), (col_b, label_b, color_b)]:
        if col not in h.columns or not h[col].notna().any():
            continue
        d = _mk_daily(h, col)
        fig.add_trace(go.Scatter(
            x=d["Date"], y=d[col], mode="lines", name=label,
            line=dict(color=color, width=1.5),
            hovertemplate=f"<b>{label}</b> %{{x|%d %b}}: %{{y:.1f}} {ytitle}<extra></extra>",
        ))
    if not fig.data:
        return _mk_stub(title, "no data")
    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1))
    fig.update_yaxes(title_text=ytitle)
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>{title} — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_chart_imb_pos_neg(bal, zoom) -> go.Figure:
    return _mk_imb_chart(bal, "Imb_Pos", "Imb_Neg",
                         "Imbalance Positive", "Imbalance Negative",
                         C2, C5, zoom, "Imbalance Prices — Positive vs Negative")


def mk_chart_imb_spread(bal, zoom) -> go.Figure:
    if bal is None or len(bal) == 0:
        return _mk_stub("Imbalance Spread", "no data")
    h = _mk_clip(bal.copy(), zoom)
    if "Imb_Pos" not in h.columns or "Imb_Neg" not in h.columns:
        return _mk_stub("Imbalance Spread", "columns missing")
    h = h.dropna(subset=["Imb_Pos", "Imb_Neg"])
    h["spread"] = h["Imb_Pos"] - h["Imb_Neg"]
    d = _mk_daily(h, "spread")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d["Date"], y=d["spread"], mode="lines", name="Imb Spread",
        line=dict(color=C4, width=1.5),
        fill="tozeroy", fillcolor=rgba(C4, 0.07),
        hovertemplate="<b>Spread</b> %{x|%d %b}: %{y:.1f} €/MWh<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1))
    fig.update_yaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>Imbalance Spread (Pos − Neg) — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_chart_imb_vs_da(bal, zoom) -> go.Figure:
    if bal is None or len(bal) == 0 or "DA" not in bal.columns:
        return _mk_stub("Imbalance vs DA", "no data")
    h = _mk_clip(bal.copy(), zoom)
    fig = go.Figure()
    for col, label, color in [("Imb_Pos","Imb Pos − DA", C2), ("Imb_Neg","Imb Neg − DA", C5)]:
        if col not in h.columns or not h[col].notna().any():
            continue
        tmp = h.dropna(subset=[col, "DA"]).copy()
        tmp["delta"] = tmp[col] - tmp["DA"]
        d = _mk_daily(tmp, "delta")
        fig.add_trace(go.Scatter(
            x=d["Date"], y=d["delta"], mode="lines", name=label,
            line=dict(color=color, width=1.5),
            hovertemplate=f"<b>{label}</b> %{{x|%d %b}}: %{{y:+.1f}} €/MWh<extra></extra>",
        ))
    fig.add_hline(y=0, line=dict(color=REF_LINE_LL, width=1.5, dash="dot"),
                  annotation_text="= DA price",
                  annotation_font=dict(color=TEXT_FAINT, size=10, family="Calibri"))
    fig.update_yaxes(title_text="€/MWh vs DA")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>Imbalance vs Day-Ahead — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_table_imbalance(bal, zoom) -> go.Figure:
    if bal is None or len(bal) == 0:
        return _mk_stub("", "no data")
    h = _mk_clip(bal.copy(), zoom)
    rows = []
    for col, label in [("DA","DA"), ("Imb_Pos","Imb Pos"), ("Imb_Neg","Imb Neg")]:
        if col in h.columns and h[col].notna().any():
            s = h[col].dropna()
            rows.append((label, f"{s.mean():.1f}", f"{s.min():.1f}", f"{s.max():.1f}"))
    if not rows:
        return _mk_stub("", "no data")
    return _mk_table(rows, ["Series", "Avg", "Min", "Max"])


# ── FCR ───────────────────────────────────────────────────────────────────────

def mk_chart_fcr(fcr, zoom) -> go.Figure:
    if fcr is None or len(fcr) == 0 or "FCR_EUR_MW_day" not in fcr.columns:
        return _mk_stub("FCR Price", "run update_entsoe_xborder.py")
    h = _mk_clip(fcr[fcr["FCR_EUR_MW_day"].notna()].copy(), zoom)
    if len(h) == 0:
        return _mk_stub("FCR Price", "no data in window")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["Date"], y=h["FCR_EUR_MW_day"], mode="lines", name="FCR FR",
        line=dict(color=MK_PURPLE, width=1.5),
        fill="tozeroy", fillcolor=rgba(COL_AFRR, 0.07),
        hovertemplate="<b>%{x|%d %b %Y}</b>: %{y:.1f} €/MW/day<extra></extra>",
    ))
    if len(h) >= 30:
        fig.add_trace(go.Scatter(
            x=h["Date"], y=h["FCR_EUR_MW_day"].rolling(30, min_periods=10).mean(),
            mode="lines", name="30D avg", line=dict(color=C1, width=2),
            hovertemplate="30D avg: %{y:.1f}<extra></extra>"))
    fig.update_yaxes(title_text="€/MW/day")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>FCR Contracted Reserve Price — France — {zoom}</b>"),
        hovermode="x unified")
    return fig


def mk_chart_afrr(bal, zoom) -> go.Figure:
    if bal is None or len(bal) == 0:
        return _mk_stub("aFRR / mFRR", "run ENTSO-E balancing script")
    h = _mk_clip(bal.copy(), zoom)
    fig = go.Figure()
    for col, label, color in [("aFRR","aFRR", MK_PURPLE), ("mFRR","mFRR", C4)]:
        if col not in h.columns or not h[col].notna().any():
            continue
        d = _mk_daily(h, col)
        fig.add_trace(go.Scatter(
            x=d["Date"], y=d[col], mode="lines", name=label,
            line=dict(color=color, width=1.5),
            hovertemplate=f"<b>{label}</b> %{{x|%d %b}}: %{{y:.1f}} €/MWh<extra></extra>",
        ))
    if not fig.data:
        return _mk_stub("aFRR / mFRR", "columns not found")
    fig.update_yaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_MD)
    fig.update_layout(
        title=dict(text=f"<b>aFRR & mFRR Activated Prices — France — {zoom}</b>"),
        hovermode="x unified")
    return fig


# ── Europe map ────────────────────────────────────────────────────────────────

def mk_chart_europe_map(xb, hourly, zoom) -> go.Figure:
    """Bar chart ranked by DA price — replaces choropleth (geo not supported)."""
    prices = {}
    if hourly is not None and "Spot" in hourly.columns:
        h = _mk_clip(hourly.copy(), zoom)
        v = h["Spot"].mean()
        if v == v:
            prices["France"] = v
    if xb is not None and len(xb) > 0:
        x = _mk_clip(xb.copy(), zoom)
        for code, label in [("DE","Germany"),("BE","Belgium"),
                             ("ES","Spain"),("NL","Netherlands"),("IT","Italy")]:
            if code in x.columns and x[code].notna().any():
                prices[label] = x[code].mean()
    if not prices:
        return _mk_stub("Europe DA Prices", "run update_entsoe_xborder.py")

    df = pd.DataFrame(list(prices.items()), columns=["Country","Price"]).sort_values("Price")
    mn, mx = df["Price"].min(), df["Price"].max()
    def _color(v):
        t = (v - mn) / (mx - mn) if mx > mn else 0.5
        r = int(42  + t * (231 - 42))
        g = int(157 - t * (157 - 111))
        b = int(143 - t * (143 - 81))
        return f"rgb({r},{g},{b})"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Price"], y=df["Country"], orientation="h",
        marker_color=[_color(v) for v in df["Price"]],
        marker_line_width=0,
        text=[f"<b>{v:.1f} €/MWh</b>" for v in df["Price"]],
        textposition="outside",
        textfont=dict(size=12, color=C1, family="Calibri"),
        hovertemplate="<b>%{y}</b>: %{x:.1f} €/MWh<extra></extra>",
    ))
    fig.update_xaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_SM, show_legend=False)
    fig.update_layout(
        title=dict(text=f"<b>DA Spot Price by Country — Avg {zoom} (Green=Low / Red=High)</b>"),
        margin=dict(l=110, r=80, t=40, b=40),
    )
    return fig

# ── Multi-country historical ──────────────────────────────────────────────────

def mk_chart_country_history(xb, hourly, zoom) -> go.Figure:
    COLORS = {"FR": C1, "DE": CHART_PALETTE[2], "BE": C2, "ES": C3, "NL": C5, "IT": C4}
    if xb is None and hourly is None:
        return _mk_stub("Country DA History", "no data")
    fig = go.Figure()
    # FR
    if hourly is not None and "Spot" in hourly.columns:
        h = _mk_clip(hourly.copy(), zoom)
        d = _mk_daily(h, "Spot")
        if len(d) > 0:
            fig.add_trace(go.Scatter(
                x=d["Date"], y=d["Spot"], mode="lines", name="France",
                line=dict(color=COLORS["FR"], width=2.5),
                hovertemplate="<b>France</b> %{x|%d %b}: %{y:.1f} €/MWh<extra></extra>",
            ))
    # Others
    if xb is not None and len(xb) > 0:
        x = _mk_clip(xb.copy(), zoom)
        for code, label in [("DE","Germany"),("BE","Belgium"),("ES","Spain"),
                             ("NL","Netherlands"),("IT","Italy")]:
            if code not in x.columns or not x[code].notna().any():
                continue
            d = _mk_daily(x, code)
            fig.add_trace(go.Scatter(
                x=d["Date"], y=d[code], mode="lines", name=label,
                line=dict(color=COLORS.get(code, TEXT_FAINT), width=1.5),
                hovertemplate=f"<b>{label}</b> %{{x|%d %b}}: %{{y:.1f}} €/MWh<extra></extra>",
            ))
    if not fig.data:
        return _mk_stub("Country DA History", "no data")
    fig.update_yaxes(title_text="€/MWh")
    plotly_base(fig, h=CHART_H_LG)
    fig.update_layout(
        title=dict(text=f"<b>DA Spot Price — France vs Neighbours — {zoom}</b>"),
        hovermode="x unified")
    return fig
