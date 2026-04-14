"""
charts.py — PPA Dashboard
All Plotly chart functions. Each returns a go.Figure.
Jomaux charts: duck curve, canyon curve, market value vs penetration.
"""

import pandas as pd
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (C1, C2, C3, C4, C5, WHT, C2L, C3L, MONTH_NAMES)
from ui import plotly_base, rgba

# ── Colours ───────────────────────────────────────────────────────────────────
COL_DA      = C1        # dark navy
COL_IMB_POS = C2        # teal
COL_IMB_NEG = C5        # brick red
COL_AFRR    = "#9B59B6"  # purple
COL_MFRR    = "#E67E22"  # orange

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ══════════════════════════════════════════════════════════════════════════════

def chart_historical_cp(nat_ref, asset_ann, has_asset, asset_name,
                        tech_clr, tech_lbl, nat_cp_list, nat_eur_list,
                        partial_years):
    """Historical CP% bars + EUR/MWh line — 2 rows."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                        subplot_titles=["CP% (% of spot average)", "CP (EUR/MWh)"],
                        row_heights=[0.55, 0.45])

    ny  = nat_ref["year"].tolist()
    ns  = nat_ref["spot"].tolist()
    is_p= nat_ref["partial"].tolist() if "partial" in nat_ref.columns else [False] * len(ny)

    bar_colors   = ["rgba(255,215,0,0.55)" if p else rgba(tech_clr, 0.5) for p in is_p]
    bar_outlines = [C3 if p else tech_clr for p in is_p]
    bar_texts    = [f"<b>{v*100:.0f}%</b>" + (" YTD" if p else "")
                    for v, p in zip(nat_cp_list, is_p)]

    fig.add_trace(go.Bar(x=ny, y=nat_cp_list, name=f"M0 National {tech_lbl}",
                         marker_color=bar_colors, marker_line_color=bar_outlines, marker_line_width=2,
                         text=bar_texts, textposition="outside",
                         textfont=dict(size=11, color=C1, family="Calibri")), row=1, col=1)

    if has_asset:
        ay = asset_ann["Year"].tolist(); acp = asset_ann["cp_pct"].tolist(); ae = asset_ann["cp_eur"].tolist()
        fig.add_trace(go.Bar(x=ay, y=acp, name=asset_name,
                             marker_color=[rgba(C5, 0.6)] * len(ay),
                             marker_line_color=C5, marker_line_width=1.5,
                             text=[f"<b>{v*100:.0f}%</b>" for v in acp], textposition="outside",
                             textfont=dict(size=11, color=C5, family="Calibri")), row=1, col=1)
        fig.add_trace(go.Scatter(x=ay, y=ae, name=asset_name + " EUR",
                                 line=dict(color=C5, width=2.5), mode="lines+markers",
                                 marker=dict(size=8, color=C5, line=dict(width=1.5, color=WHT))), row=2, col=1)

    fig.add_trace(go.Scatter(x=ny, y=nat_cp_list,
                             line=dict(color=tech_clr, width=2.5, dash="dash"), mode="lines+markers",
                             marker=dict(size=7, color=tech_clr, symbol="square",
                                         line=dict(width=1.5, color=WHT)), showlegend=False), row=1, col=1)
    fig.add_hline(y=1.0, line=dict(color="#AAAAAA", width=1, dash="dot"), row=1, col=1)
    fig.add_vrect(x0=2021.5, x1=2022.5, fillcolor=C3, opacity=0.25, line_width=0, row=1, col=1)
    fig.add_vrect(x0=2021.5, x1=2022.5, fillcolor=C3, opacity=0.25, line_width=0, row=2, col=1)
    fig.add_annotation(x=2022, y=0.32, text="2022", showarrow=False,
                       font=dict(color=C3, size=13, family="Calibri"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ny, y=ns, name="National Spot",
                             line=dict(color="#555555", width=2, dash="dash"), mode="lines+markers",
                             marker=dict(size=6, color="#555555")), row=2, col=1)
    fig.add_trace(go.Scatter(x=ny, y=nat_eur_list, name=f"M0 {tech_lbl} EUR",
                             line=dict(color=tech_clr, width=2.5), mode="lines+markers",
                             marker=dict(size=7, color=tech_clr, symbol="square",
                                         line=dict(width=1.5, color=WHT))), row=2, col=1)

    fig.update_yaxes(tickformat=".0%", row=1, col=1)
    fig.update_layout(barmode="group")
    plotly_base(fig, h=640)
    return fig


def chart_projection(nat_ref, asset_ann, has_asset, proj,
                     nat_cp_list, nat_ref_complete, nat_cp_col,
                     tech_clr, tech_lbl, sl_u, ic_u, r2_u,
                     last_yr_proj, proj_n, ex22,
                     reg_basis="Asset", anchor_val=None):
    """
    CP% projection with P10-P90 uncertainty bands.
    reg_basis: "Asset" or "National"
    anchor_val: last observed asset CP% — P50 anchored here, slope applied from it
    """
    fig = go.Figure()

    if has_asset:
        fig.add_trace(go.Scatter(
            x=asset_ann["Year"].tolist(), y=asset_ann["cp_pct"].tolist(),
            name="Asset (historical)", mode="lines+markers+text",
            line=dict(color=C5, width=3),
            marker=dict(size=10, color=C5, line=dict(width=2, color=WHT)),
            text=[f"<b>{v*100:.0f}%</b>" for v in asset_ann["cp_pct"]],
            textposition="top center",
            textfont=dict(size=11, color=C5, family="Calibri")))

    fig.add_trace(go.Scatter(
        x=nat_ref["year"].tolist(), y=nat_cp_list,
        name=f"M0 National {tech_lbl}", mode="lines+markers",
        line=dict(color=tech_clr, width=2.5, dash="dash"),
        marker=dict(size=8, color=tech_clr, symbol="square",
                    line=dict(width=1.5, color=WHT))))

    tx = list(range(2014, last_yr_proj + proj_n + 1))
    fig.add_trace(go.Scatter(
        x=tx, y=[1 - (ic_u + sl_u * yr) for yr in tx],
        name="Trend", line=dict(color="#AAAAAA", width=2, dash="dot"),
        mode="lines", opacity=0.8))

    py_ = proj["year"].tolist()
    fig.add_trace(go.Scatter(
        x=py_ + py_[::-1],
        y=proj["p90"].tolist() + proj["p10"].tolist()[::-1],
        fill="toself", fillcolor="rgba(255,215,0,0.20)",
        line=dict(color="rgba(0,0,0,0)"), name="P10-P90"))
    fig.add_trace(go.Scatter(
        x=py_ + py_[::-1],
        y=proj["p75"].tolist() + proj["p25"].tolist()[::-1],
        fill="toself", fillcolor="rgba(247,220,111,0.35)",
        line=dict(color="rgba(0,0,0,0)"), name="P25-P75"))

    if anchor_val is not None:
        hl = anchor_val
    elif has_asset:
        hl = asset_ann["cp_pct"].iloc[-1]
    elif nat_cp_col in nat_ref_complete.columns and not nat_ref_complete[nat_cp_col].isna().all():
        hl = nat_ref_complete[nat_cp_col].iloc[-1]
    else:
        hl = nat_ref_complete["cp_nat_pct"].iloc[-1]

    fig.add_trace(go.Scatter(
        x=[last_yr_proj] + py_, y=[hl] + proj["p50"].tolist(),
        name="P50 (central scenario)", mode="lines+markers",
        line=dict(color=C1, width=3),
        marker=dict(size=8, color=C1, line=dict(width=2, color=WHT))))

    for _, row in proj.iterrows():
        fig.add_annotation(
            x=row["year"], y=row["p50"],
            text=f"<b>P50:{row['p50']*100:.0f}%</b><br>P10:{row['p10']*100:.0f}%",
            showarrow=True, arrowhead=2, arrowcolor=C1, arrowwidth=1.5,
            font=dict(size=11, color=C1, family="Calibri"),
            bgcolor="rgba(255,255,255,0.9)", bordercolor=C3, borderwidth=1,
            ax=32, ay=-40)

    fig.add_vline(x=last_yr_proj + 0.5, line=dict(color="#BBBBBB", width=1.5, dash="dot"))
    fig.add_vrect(x0=2021.5, x1=2022.5, fillcolor=C3, opacity=0.15, line_width=0)
    fig.update_yaxes(tickformat=".0%")
    plotly_base(fig, h=640)
    fig.update_layout(
        title=dict(
            text=(f"Slope: {-sl_u*100:.2f}%/yr  R\u00b2: {r2_u:.3f} "
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
                         marker_color=[rgba(C2, 0.7)] * len(fwd_df),
                         marker_line_color=C2, marker_line_width=2,
                         text=[f"<b>{v:.1f}</b>" for v in fwd_df["forward"]],
                         textposition="outside",
                         textfont=dict(size=14, color=C1, family="Calibri"),
                         name="EEX Forward"))
    fig.update_yaxes(title_text="EUR/MWh")
    fig.update_xaxes(tickmode="array", tickvals=fwd_df["year"].tolist())
    plotly_base(fig, h=280, show_legend=False)
    fig.update_layout(title=dict(text="<b>Forward Price Curve</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Market Dynamics
# ══════════════════════════════════════════════════════════════════════════════

def chart_neg_hours(hourly: pd.DataFrame, partial_years: list,
                    tech_clr: str) -> go.Figure:
    neg = hourly[hourly["Spot"] < 0].groupby("Year").size().reset_index(name="neg_hours")
    all_yrs = pd.DataFrame({"Year": sorted(hourly["Year"].unique())})
    neg = all_yrs.merge(neg, on="Year", how="left").fillna(0)
    neg["neg_hours"] = neg["neg_hours"].astype(int)

    bar_c = [C3 if yr in partial_years else (C5 if v > 300 else (C4 if v > 100 else tech_clr))
             for v, yr in zip(neg["neg_hours"], neg["Year"])]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=neg["Year"], y=neg["neg_hours"],
                         marker_color=bar_c, marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v}</b>" + (" YTD" if yr in partial_years else "")
                               for v, yr in zip(neg["neg_hours"], neg["Year"])],
                         textposition="outside",
                         textfont=dict(size=12, color=C1, family="Calibri"),
                         name="Negative Price Hours"))

    neg_c = neg[~neg["Year"].isin(partial_years)]
    if len(neg_c) >= 3:
        xn = neg_c["Year"].values.astype(float); yn = neg_c["neg_hours"].values.astype(float)
        sln, icn, *_ = stats.linregress(xn, yn)
        fut = list(range(int(xn.min()), int(xn.max()) + 4))
        fig.add_trace(go.Scatter(x=fut, y=[max(0, icn + sln * yr) for yr in fut],
                                 mode="lines", line=dict(color=C5, width=2.5, dash="dash"),
                                 name=f"Trend ({sln:+.0f}h/yr)"))

    fig.add_hline(y=15, line=dict(color=C2, width=1.5, dash="dot"),
                  annotation_text="CRE Threshold (15h)",
                  annotation_font=dict(color=C2, size=12, family="Calibri"))
    plotly_base(fig, h=380)
    fig.update_layout(title=dict(text="<b>Negative Price Hours by Year</b>"))
    return fig


def chart_monthly_profile(hourly: pd.DataFrame, prod_col: str,
                           tech_clr: str, tech_lbl: str):
    """Monthly avg shape discount + returns agg df for heatmap reuse."""
    monthly = hourly.copy()
    monthly["Rev_tech"] = monthly[prod_col] * monthly["Spot"]
    monthly_agg = monthly[monthly["Spot"] > 0].groupby(["Year","Month"]).agg(
        spot_avg  = ("Spot",      "mean"),
        prod_tech = (prod_col,    "sum"),
        rev_tech  = ("Rev_tech",  "sum"),
    ).reset_index()
    monthly_agg["m0"]   = monthly_agg["rev_tech"] / monthly_agg["prod_tech"].replace(0, np.nan)
    monthly_agg["sd_m"] = 1 - monthly_agg["m0"] / monthly_agg["spot_avg"]
    month_avg = monthly_agg.groupby("Month")["sd_m"].agg(["mean","std"]).reset_index()

    bar_c_m = [C5 if v > 0.15 else (C4 if v > 0.08 else tech_clr) for v in month_avg["mean"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=MONTH_NAMES, y=month_avg["mean"],
                         error_y=dict(type="data", array=month_avg["std"].tolist(),
                                      visible=True, color="#AAAAAA", thickness=2, width=5),
                         marker_color=bar_c_m, marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v*100:.1f}%</b>" for v in month_avg["mean"]],
                         textposition="outside",
                         textfont=dict(size=11, color=C1, family="Calibri")))
    fig.add_hline(y=0, line=dict(color="#AAAAAA", width=1))
    fig.update_yaxes(tickformat=".0%", title_text="Average Shape Discount")
    plotly_base(fig, h=380, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Monthly Cannibalization Profile — {tech_lbl}</b>"))
    return fig, monthly_agg


def chart_scatter_cp_vs_capacity(nat_ref: pd.DataFrame, hourly: pd.DataFrame,
                                  prod_col: str, nat_cp_col: str, tech_clr: str,
                                  tech_lbl: str, partial_years: list,
                                  is_solar: bool) -> go.Figure:
    nat_mw = hourly.groupby("Year")[prod_col].mean().reset_index()
    nat_mw.columns = ["year", "TechMW"]
    sc = nat_ref.merge(nat_mw, on="year", how="inner")
    sc = sc[sc["TechMW"] > 0].copy()
    sc["cp_plot"] = sc[nat_cp_col].fillna(sc["cp_nat_pct"])

    pt_col = [C3 if r.get("partial", False) else
              (C5 if r["year"] >= 2024 else (C3 if r["year"] == 2022 else tech_clr))
              for _, r in sc.iterrows()]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sc["TechMW"], y=sc["cp_plot"], mode="markers+text",
                             marker=dict(size=16, color=pt_col, line=dict(width=2, color=WHT)),
                             text=[f"<b>{int(y)}</b>" for y in sc["year"]],
                             textposition="top center",
                             textfont=dict(size=11, color=C1, family="Calibri"),
                             name=f"M0 National {tech_lbl}"))

    sc_c = sc[~sc["year"].isin(partial_years)]
    if len(sc_c) >= 3:
        x = sc_c["TechMW"].values
        y = sc_c["cp_plot"].values

        mask = x > 0
        x = x[mask]
        y = y[mask]

        if len(x) >= 3:
            coeffs = np.polyfit(np.log(x), y, 1)
            y_pred = np.polyval(coeffs, np.log(x))
            r2 = 1 - np.sum((y - y_pred)**2) / np.sum((y - np.mean(y))**2)

            xl = np.linspace(x.min(), x.max(), 200)
            yl = np.polyval(coeffs, np.log(xl))

            fig.add_trace(go.Scatter(
                x=xl,
                y=yl,
                mode="lines",
                name=f"log fit (R²={r2:.2f})"
            ))

    if is_solar:
        for gw, lbl, col in [(48000, "PPE3 2030", C4), (65000, "PPE3 2035", C5)]:
            fig.add_vline(x=gw, line=dict(color=col, width=2, dash="dot"))
            fig.add_annotation(x=gw, y=sc["cp_plot"].min() * 0.94, text=f"<b>{lbl}</b>",
                               font=dict(color=col, size=11, family="Calibri"),
                               showarrow=False, xanchor="left")

    fig.update_yaxes(tickformat=".0%", title_text="Captured Price (% of spot)")
    fig.update_xaxes(title_text=f"National {tech_lbl} Avg MW")
    plotly_base(fig, h=380)
    fig.update_layout(title=dict(text=f"<b>CP% vs {tech_lbl} Capacity</b>"))
    return fig


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
    fig.add_hline(y=0, line=dict(color="#AAAAAA", width=1.5))
    fig.update_yaxes(tickformat=".1%", title_text="Delta Shape Discount (pp)")
    plotly_base(fig, h=340, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Annual Shape Discount Change — {tech_lbl}</b>"))
    return fig


def chart_heatmap(monthly_agg: pd.DataFrame,
                  tech_clr: str, tech_lbl: str) -> go.Figure:
    pivot = monthly_agg.pivot(index="Year", columns="Month", values="sd_m")
    pivot.columns = [MONTH_NAMES[c - 1] for c in pivot.columns]
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values * 100, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=[[0, tech_clr], [0.5, C3], [1, C5]],
        text=[[f"<b>{v:.1f}%</b>" for v in row] for row in pivot.values * 100],
        texttemplate="%{text}", textfont=dict(size=11, color=C1, family="Calibri"),
        colorbar=dict(title=dict(text="Shape Disc (%)", font=dict(size=12, color=C1)),
                      tickfont=dict(size=11, color=C1), thickness=14)))
    fig.update_xaxes(title_text="Month"); fig.update_yaxes(title_text="Year")
    plotly_base(fig, h=400, show_legend=False)
    fig.update_layout(title=dict(text=f"<b>Monthly Shape Discount Heatmap — {tech_lbl}</b>"))
    return fig


# ── Jomaux Charts ─────────────────────────────────────────────────────────────

def chart_market_value_vs_penetration(hourly: pd.DataFrame,
                                       prod_col: str,
                                       tech_clr: str,
                                       tech_lbl: str,
                                       partial_years: list,
                                       n_bins: int = 20) -> go.Figure:
    """
    Jomaux — Market value vs generation output.
    For each MW bin of instantaneous tech generation,
    compute the average spot price (= market value for that MW level).
    Inspired by: GEM Energy Analytics "The decreasing market value of renewables".
    """
    h = hourly[hourly[prod_col] > 0].copy()
    if len(h) < 100:
        return go.Figure()

    # Exclude partial year for cleaner trend
    h = h[~h["Year"].isin(partial_years)]

    bins = pd.cut(h[prod_col], bins=n_bins)
    agg  = h.groupby(bins, observed=True).agg(
        avg_spot     = ("Spot",    "mean"),
        avg_mw       = (prod_col,  "mean"),
        count        = (prod_col,  "count"),
        avg_cp_pct   = ("Spot",    "mean"),
    ).reset_index()
    agg = agg[agg["count"] > 20]

    max_mw = agg["avg_mw"].max()
    colors = [rgba(tech_clr, 0.4 + 0.5 * (v / max_mw)) for v in agg["avg_mw"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=agg["avg_mw"], y=agg["avg_spot"],
        mode="markers",
        marker=dict(size=agg["count"].apply(lambda c: min(8 + c / 200, 22)),
                    color=colors, line=dict(width=1, color=WHT)),
        name="Avg Spot per MW bin",
        hovertemplate="<b>Avg MW: %{x:.0f}</b><br>Avg Spot: %{y:.1f} EUR/MWh<extra></extra>",
    ))

    if len(agg) >= 4:
        sl, ic, r, _, _ = stats.linregress(agg["avg_mw"], agg["avg_spot"])
        xl = np.linspace(agg["avg_mw"].min(), agg["avg_mw"].max(), 100)
        fig.add_trace(go.Scatter(x=xl, y=ic + sl * xl, mode="lines",
                                 line=dict(color=C1, width=2, dash="dash"),
                                 name=f"Trend (R²={r**2:.2f})"))

    fig.update_xaxes(title_text=f"{tech_lbl} Generation (MW)")
    fig.update_yaxes(title_text="Average Spot Price (EUR/MWh)")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(
        text=f"<b>Market Value vs {tech_lbl} Generation Output</b>"))
    return fig


def chart_duck_curve(hourly: pd.DataFrame,
                     tech_clr: str,
                     tech_lbl: str,
                     duck_months: list) -> go.Figure:
    """
    Jomaux — Duck/Canyon curve: normalised day-ahead prices by hour.
    Normalisation: each data point / monthly average (all hours).
    Filtered on duck_months (Apr-Sep for solar, all months for wind).
    One line per year — year-over-year comparison independent of absolute price level.
    Method: GEM Energy Analytics "The duck is growing" (2025).
    """
    h = hourly[hourly["Month"].isin(duck_months)].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour

    monthly_avg = h.groupby(["Year","Month"])["Spot"].transform("mean")
    h["norm_spot"] = h["Spot"] / monthly_avg.replace(0, np.nan)

    hourly_avg = h.groupby(["Year","Hour"])["norm_spot"].mean().reset_index()

    years = sorted(hourly_avg["Year"].unique())
    n = max(len(years), 1)
    year_colors = [rgba(tech_clr, 0.25 + 0.75 * i / (n - 1)) if n > 1 else tech_clr
                   for i, _ in enumerate(years)]

    fig = go.Figure()
    for yr, col in zip(years, year_colors):
        d = hourly_avg[hourly_avg["Year"] == yr].sort_values("Hour")
        width = 3.0 if yr == years[-1] else 1.2
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d["norm_spot"],
            mode="lines",
            line=dict(color=col, width=width),
            name=str(yr),
            legendgroup=str(yr),
            showlegend=True,
            hovertemplate=f"<b>{yr}</b> — Hour %{{x}}h: %{{y:.2f}}x avg<extra></extra>",
        ))

    fig.add_hline(y=1.0, line=dict(color="#BBBBBB", width=1.5, dash="dot"),
                  annotation_text="Monthly avg = 1.0",
                  annotation_font=dict(color="#999999", size=11, family="Calibri"),
                  annotation_position="top left")

    if 4 in duck_months or 5 in duck_months:
        fig.add_vrect(x0=9.5, x1=15.5,
                      fillcolor=rgba(tech_clr, 0.07), line_width=0,
                      annotation_text="Solar peak",
                      annotation_position="top left",
                      annotation_font=dict(color=tech_clr, size=10, family="Calibri"))

    season_lbl = "Apr-Sep" if duck_months == list(range(4, 10)) else "All months"
    fig.update_xaxes(title_text="Hour of Day", tickmode="array",
                     tickvals=list(range(0, 24, 2)),
                     ticktext=[f"{h}h" for h in range(0, 24, 2)])
    fig.update_yaxes(title_text="Normalised Price (monthly avg = 1)")
    plotly_base(fig, h=460)
    fig.update_layout(title=dict(
        text=f"<b>Duck/Canyon Curve — Normalised Day-Ahead Prices by Hour ({tech_lbl}, {season_lbl})</b>"))
    return fig


def chart_canyon_curve(hourly: pd.DataFrame,
                       tech_clr: str,
                       tech_lbl: str,
                       duck_months: list,
                       recent_years: int = 4) -> go.Figure:
    """
    Jomaux — Canyon curve: same as duck curve but aggregated over ALL years
    in a single line, with one line per recent year to show the evolution.
    Shows how the duck progressively deepens into a canyon.
    Method: GEM Energy Analytics "The duck is growing" (2025).
    """
    h = hourly[hourly["Month"].isin(duck_months)].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour

    monthly_avg = h.groupby(["Year","Month"])["Spot"].transform("mean")
    h["norm_spot"] = h["Spot"] / monthly_avg.replace(0, np.nan)

    all_complete_years = sorted(h[~h["Year"].isin([pd.Timestamp.now().year])]["Year"].unique())
    selected_years = all_complete_years[-recent_years:] if len(all_complete_years) >= recent_years else all_complete_years

    hourly_avg = h[h["Year"].isin(selected_years)].groupby(["Year","Hour"])["norm_spot"].mean().reset_index()

    n = max(len(selected_years), 1)
    year_colors = ["#AAAAAA"] * (n - 1) + [tech_clr]

    fig = go.Figure()
    for yr, col in zip(selected_years, year_colors):
        d = hourly_avg[hourly_avg["Year"] == yr].sort_values("Hour")
        width = 3.0 if yr == selected_years[-1] else 1.5
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d["norm_spot"], mode="lines",
            line=dict(color=col, width=width),
            name=str(yr),
            hovertemplate=f"<b>{yr}</b> — Hour %{{x}}h: %{{y:.2f}}x avg<extra></extra>",
        ))

    fig.add_hline(y=1.0, line=dict(color="#BBBBBB", width=1.5, dash="dot"),
                  annotation_text="Monthly avg = 1.0",
                  annotation_font=dict(color="#999999", size=11, family="Calibri"),
                  annotation_position="top left")

    season_lbl = "Apr-Sep" if duck_months == list(range(4, 10)) else "All months"
    fig.update_xaxes(title_text="Hour of Day", tickmode="array",
                     tickvals=list(range(0, 24, 2)),
                     ticktext=[f"{h}h" for h in range(0, 24, 2)])
    fig.update_yaxes(title_text="Normalised Price (monthly avg = 1)")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(
        text=f"<b>Canyon Curve — Last {recent_years} Years ({tech_lbl}, {season_lbl})</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Sensitivity & Scenarios
# ══════════════════════════════════════════════════════════════════════════════

def chart_pnl_percentile(pcts, pnl_v, cp_vals, ppa, vol_mwh,
                          chosen_pct, vol_stress, be, tech_lbl):
    fig = go.Figure()
    px_ = [p for p, v in zip(pcts, pnl_v) if v >= 0]
    py_ = [v for v in pnl_v if v >= 0]
    nx_ = [p for p, v in zip(pcts, pnl_v) if v < 0]
    ny_ = [v for v in pnl_v if v < 0]

    if px_:
        fig.add_trace(go.Scatter(x=px_, y=py_, fill="tozeroy",
                                 fillcolor="rgba(42,157,143,0.15)",
                                 line=dict(color="rgba(0,0,0,0)"), showlegend=False))
    if nx_:
        fig.add_trace(go.Scatter(x=nx_, y=ny_, fill="tozeroy",
                                 fillcolor="rgba(231,111,81,0.15)",
                                 line=dict(color="rgba(0,0,0,0)"), showlegend=False))

    fig.add_trace(go.Scatter(x=pcts, y=pnl_v, name="P&L (k EUR/yr)",
                             mode="lines", line=dict(color=C1, width=3)))
    pc_ = pnl_v[chosen_pct - 1]
    fig.add_trace(go.Scatter(x=[chosen_pct], y=[pc_], mode="markers+text",
                             marker=dict(size=16, color=C2 if pc_ >= 0 else C5,
                                         line=dict(width=2.5, color=WHT)),
                             text=[f"<b>P{chosen_pct}: {pc_:.0f}k</b>"],
                             textposition="top right",
                             name=f"P{chosen_pct} Selected",
                             textfont=dict(size=12, color=C1, family="Calibri")))

    pu  = [vol_mwh * (1 + vol_stress/100) * (c - ppa) / 1000 for c in cp_vals]
    pd_ = [vol_mwh * (1 - vol_stress/100) * (c - ppa) / 1000 for c in cp_vals]
    fig.add_trace(go.Scatter(x=pcts + pcts[::-1], y=pu + pd_[::-1],
                             fill="toself", fillcolor="rgba(255,215,0,0.25)",
                             line=dict(color="rgba(0,0,0,0)"),
                             name=f"+/-{vol_stress}% Volume"))

    fig.add_hline(y=0, line=dict(color="#AAAAAA", width=2))
    if be:
        fig.add_vline(x=be, line=dict(color=C5, width=2, dash="dot"),
                      annotation_text=f"<b>Break-even P{be}</b>",
                      annotation_font=dict(color=C5, size=12, family="Calibri"))

    fig.update_layout(xaxis_title="Shape Discount Percentile",
                      yaxis_title="Annual P&L (k EUR)")
    plotly_base(fig, h=450)
    fig.update_layout(title=dict(
        text=f"<b>P&L Distribution by Cannibalization Percentile — {tech_lbl}</b>"))
    return fig


def chart_scenarios(scenarios: list, proj_n: int, tech_lbl: str) -> go.Figure:
    sn   = [s["Scenario"] for s in scenarios]
    sv50 = [s["p50"] for s in scenarios]
    sv10 = [s["p10"] for s in scenarios]
    sv90 = [s["p90"] for s in scenarios]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="P50", x=sn, y=sv50,
                         marker_color=["rgba(42,157,143,0.80)" if v >= 0
                                        else "rgba(231,111,81,0.80)" for v in sv50],
                         marker_line_color=WHT, marker_line_width=1,
                         text=[f"<b>{v:+.0f}k</b>" for v in sv50],
                         textposition="outside",
                         textfont=dict(size=12, color=C1, family="Calibri")))
    fig.add_trace(go.Scatter(name="P10", x=sn, y=sv10, mode="markers",
                             marker=dict(symbol="triangle-down", size=14, color=C5,
                                         line=dict(width=2, color=WHT))))
    fig.add_trace(go.Scatter(name="P90", x=sn, y=sv90, mode="markers",
                             marker=dict(symbol="triangle-up", size=14, color=C2,
                                         line=dict(width=2, color=WHT))))
    fig.add_hline(y=0, line=dict(color="#AAAAAA", width=2))
    fig.update_layout(xaxis_title="Scenario",
                      yaxis_title=f"Cumulative P&L {proj_n}yr (k EUR)",
                      bargap=0.35)
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(
        text=f"<b>Stress Scenarios — {proj_n} Year P&L — {tech_lbl}</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Price Waterfall
# ══════════════════════════════════════════════════════════════════════════════

def chart_waterfall(ref_fwd: float, sd_ch: float, imb_eur: float, tech_lbl: str,
                    vol_risk_pct: float = 0.0,
                    price_risk_pct: float = 0.0,
                    cannib_risk_pct: float = 0.0,
                    goo_value: float = 1.0,
                    add_disc: float = 0.0,
                    margin: float = 1.0) -> go.Figure:

    shape_disc_eur  = ref_fwd * sd_ch
    add_disc_eur    = ref_fwd * add_disc
    vol_risk_eur    = ref_fwd * vol_risk_pct
    price_risk_eur  = ref_fwd * price_risk_pct
    ppa_final       = (ref_fwd
                       - shape_disc_eur - add_disc_eur
                       - vol_risk_eur   - price_risk_eur
                       - imb_eur
                       + goo_value + margin)

    wf = [
        ("Baseload Forward", ref_fwd,          "absolute"),
        ("Shape Discount",   -shape_disc_eur,  "relative"),
        ("Add. Discount",    -add_disc_eur,    "relative"),
        ("Volume Risk",      -vol_risk_eur,    "relative"),
        ("Price Risk",       -price_risk_eur,  "relative"),
        ("Balancing Cost",   -imb_eur,         "relative"),
        ("GoO Value",         goo_value,       "relative"),
        ("Margin",            margin,          "relative"),
        ("PPA Price",         0,               "total"),
    ]

    wf = [row for row in wf if row[2] in ("absolute","total") or abs(row[1]) > 0.001]

    fig = go.Figure(go.Waterfall(
        name="", orientation="v",
        measure=[d[2] for d in wf],
        x=[d[0] for d in wf],
        y=[d[1] for d in wf],
        text=[f"{d[1]:+.2f}" if d[2] == "relative"
              else f"{d[1]:.2f}" if d[2] == "absolute"
              else f"<b>{ppa_final:.2f}</b>" for d in wf],
        textposition="outside",
        textfont=dict(size=13, color=C1, family="Calibri"),
        connector=dict(line=dict(color="#AAAAAA", width=1.5)),
        decreasing=dict(marker=dict(color=C5, line=dict(color=WHT, width=1))),
        increasing=dict(marker=dict(color=C2, line=dict(color=WHT, width=1))),
        totals=dict(marker=dict(color=C3, line=dict(color=WHT, width=2))),
    ))
    fig.update_xaxes(tickangle=-30)
    plotly_base(fig, h=520, show_legend=False)
    fig.update_layout(
        title=dict(text=f"<b>PPA Price Waterfall — {tech_lbl} — {ppa_final:.2f} EUR/MWh</b>"),
        yaxis_title="EUR/MWh")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Market Evolution (Rolling M0)
# ══════════════════════════════════════════════════════════════════════════════

def chart_rolling_cp(roll: pd.DataFrame, nat_ref_complete: pd.DataFrame,
                     nat_ref: pd.DataFrame, nat_cp_col: str, nat_cp_list_complete: list,
                     tech_clr: str, tech_lbl: str, partial_years: list) -> go.Figure:
    W_COLOR = {30: tech_clr, 90: C3, 365: C1}
    W_DASH  = {30: "dot",    90: "dash", 365: "solid"}
    W_WIDTH = {30: 1.5,      90: 2.0,   365: 2.5}
    ann_x   = [pd.Timestamp(f"{int(y)}-07-01") for y in nat_ref_complete["year"]]

    fig = go.Figure()
    fig.add_hline(y=1.0, line=dict(color="#CCCCCC", width=1.5, dash="dot"),
                  annotation_text="100% — no cannibalization",
                  annotation_font=dict(color="#999999", size=11, family="Calibri"),
                  annotation_position="top left")

    for w in [365, 90, 30]:
        col = f"cp_{w}d"; d = roll.dropna(subset=[col])
        if len(d) == 0:
            continue
        fig.add_trace(go.Scatter(x=d["Date"], y=d[col], name=f"{w}d rolling", mode="lines",
                                 line=dict(color=W_COLOR[w], width=W_WIDTH[w], dash=W_DASH[w])))

    fig.add_trace(go.Scatter(x=ann_x, y=nat_cp_list_complete,
                             name=f"Annual M0 {tech_lbl}", mode="markers",
                             marker=dict(size=11, color=C5, symbol="diamond",
                                         line=dict(width=2, color=WHT))))

    for _, ytd_row in nat_ref[nat_ref["partial"] == True].iterrows():
        cp_ytd = (ytd_row[nat_cp_col]
                  if nat_cp_col in ytd_row.index and not pd.isna(ytd_row[nat_cp_col])
                  else ytd_row["cp_nat_pct"])
        fig.add_trace(go.Scatter(
            x=[pd.Timestamp(f"{int(ytd_row['year'])}-04-01")], y=[cp_ytd],
            name=f"{int(ytd_row['year'])} YTD", mode="markers+text",
            marker=dict(size=13, color=C3, symbol="star", line=dict(width=2, color=C1)),
            text=[f"<b>{int(ytd_row['year'])} YTD: {cp_ytd*100:.0f}%</b>"],
            textposition="top right",
            textfont=dict(size=11, color=C1, family="Calibri")))

    fig.update_yaxes(tickformat=".0%", title_text="Capture Rate M0 / Baseload")
    fig.update_xaxes(title_text="Date")
    plotly_base(fig, h=500)
    fig.update_layout(title=dict(
        text=f"<b>Rolling Capture Rate — WAP / Baseload (%) — {tech_lbl}</b>"))
    return fig


def chart_rolling_eur(roll: pd.DataFrame, nat_ref_complete: pd.DataFrame,
                      nat_eur_list_complete: list,
                      tech_clr: str, tech_lbl: str) -> go.Figure:
    W_COLOR = {30: tech_clr, 90: C3, 365: C1}
    W_DASH  = {30: "dot",    90: "dash", 365: "solid"}
    W_WIDTH = {30: 1.5,      90: 2.0,   365: 2.5}
    ann_x   = [pd.Timestamp(f"{int(y)}-07-01") for y in nat_ref_complete["year"]]

    fig = go.Figure()
    bl = roll.dropna(subset=["bl_365d"])
    if len(bl) > 0:
        fig.add_trace(go.Scatter(x=bl["Date"], y=bl["bl_365d"],
                                 name="Baseload 365d (ref)", mode="lines",
                                 line=dict(color="#AAAAAA", width=2, dash="dash")))

    for w in [365, 90, 30]:
        col = f"m0_{w}d"; d = roll.dropna(subset=[col])
        if len(d) == 0:
            continue
        fig.add_trace(go.Scatter(x=d["Date"], y=d[col], name=f"M0 {w}d", mode="lines",
                                 line=dict(color=W_COLOR[w], width=W_WIDTH[w], dash=W_DASH[w])))

    fig.add_trace(go.Scatter(x=ann_x, y=nat_eur_list_complete,
                             name=f"Annual M0 {tech_lbl}", mode="markers",
                             marker=dict(size=11, color=C5, symbol="diamond",
                                         line=dict(width=2, color=WHT))))

    fig.update_yaxes(title_text="EUR/MWh")
    fig.update_xaxes(title_text="Date")
    plotly_base(fig, h=500)
    fig.update_layout(title=dict(
        text=f"<b>Rolling Captured Price M0 (EUR/MWh) — {tech_lbl}</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Asset Production Profile
# ══════════════════════════════════════════════════════════════════════════════

def chart_daily_profile_national(hourly, prod_col, tech_clr, tech_lbl):
    """Average MW by hour of day, one line per month — national data."""
    h = hourly[hourly[prod_col] > 0].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour
    month_avg = h.groupby(["Month","Hour"])[prod_col].mean().reset_index()
    colors = [
        "#1D3A4A","#2A9D8F","#E9C46A","#F4A261","#E76F51","#5B8DEF",
        "#8ECAE6","#219EBC","#023047","#FFB703","#FB8500","#6A994E"
    ]
    fig = go.Figure()
    for m in range(1, 13):
        d = month_avg[month_avg["Month"] == m].sort_values("Hour")
        if len(d) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d[prod_col],
            mode="lines", name=MONTH_NAMES[m-1],
            line=dict(color=colors[m-1], width=2),
        ))
    fig.update_xaxes(title_text="Hour", tickmode="array",
                     tickvals=list(range(0, 24, 2)),
                     ticktext=[f"{h}h" for h in range(0, 24, 2)])
    fig.update_yaxes(title_text="Avg MW")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(text=f"<b>Daily Profile — National {tech_lbl}</b>"))
    return fig


def chart_daily_profile_asset(asset_raw, tech_clr, asset_name):
    """Average MW by hour of day, one line per month — asset upload."""
    a = asset_raw.copy()
    a["Date"]  = pd.to_datetime(a["Date"])
    a["Hour"]  = a["Date"].dt.hour
    a["Month"] = a["Date"].dt.month
    a = a[a["Prod_MWh"] > 0]
    month_avg = a.groupby(["Month","Hour"])["Prod_MWh"].mean().reset_index()
    colors = [
        "#1D3A4A","#2A9D8F","#E9C46A","#F4A261","#E76F51","#5B8DEF",
        "#8ECAE6","#219EBC","#023047","#FFB703","#FB8500","#6A994E"
    ]
    fig = go.Figure()
    for m in range(1, 13):
        d = month_avg[month_avg["Month"] == m].sort_values("Hour")
        if len(d) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=d["Hour"], y=d["Prod_MWh"],
            mode="lines", name=MONTH_NAMES[m-1],
            line=dict(color=colors[m-1], width=2, dash="dot"),
        ))
    fig.update_xaxes(title_text="Hour", tickmode="array",
                     tickvals=list(range(0, 24, 2)),
                     ticktext=[f"{h}h" for h in range(0, 24, 2)])
    fig.update_yaxes(title_text="Avg MW")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(text=f"<b>Daily Profile — {asset_name}</b>"))
    return fig


def chart_monthly_production(hourly, asset_raw, prod_col,
                              tech_clr, asset_name, has_asset):
    """Monthly production: bars = asset GWh, point = national avg MW."""
    fig = go.Figure()
    nat = hourly[hourly[prod_col] > 0].copy()
    nat_avg = nat.groupby("Month")[prod_col].mean().reset_index()
    fig.add_trace(go.Scatter(
        x=[MONTH_NAMES[m-1] for m in nat_avg["Month"]],
        y=nat_avg[prod_col],
        mode="markers", name="National avg MW",
        marker=dict(size=12, color=C1, symbol="circle",
                    line=dict(width=2, color=WHT)),
        yaxis="y2",
    ))
    if has_asset and asset_raw is not None:
        a = asset_raw.copy()
        a["Date"]  = pd.to_datetime(a["Date"])
        a["Month"] = a["Date"].dt.month
        asset_mo   = a.groupby("Month")["Prod_MWh"].sum().reset_index()
        n_years    = a["Date"].dt.year.nunique()
        asset_mo["GWh"] = asset_mo["Prod_MWh"] / 1000 / max(n_years, 1)
        fig.add_trace(go.Bar(
            x=[MONTH_NAMES[m-1] for m in asset_mo["Month"]],
            y=asset_mo["GWh"],
            name=f"{asset_name} (GWh)",
            marker_color=rgba(tech_clr, 0.7),
            marker_line_color=tech_clr, marker_line_width=1.5,
            text=[f"<b>{v:.0f}</b>" for v in asset_mo["GWh"]],
            textposition="outside",
            textfont=dict(size=11, color=C1, family="Calibri"),
        ))
    fig.update_layout(
        yaxis=dict(title="Avg GWh/month", side="left"),
        yaxis2=dict(title="National avg MW", side="right",
                    overlaying="y", showgrid=False),
        barmode="group",
    )
    fig.update_xaxes(title_text="Month")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(text="<b>Monthly Production Profile</b>"))
    return fig


def chart_annual_production(hourly, asset_ann, prod_col,
                             tech_clr, asset_name, has_asset, partial_years):
    """Annual production: bars = asset GWh only."""
    fig = go.Figure()
    if has_asset and asset_ann is not None:
        fig.add_trace(go.Bar(
            x=asset_ann["Year"], y=asset_ann["prod_gwh"],
            name=f"{asset_name} (GWh)",
            marker_color=rgba(tech_clr, 0.7),
            marker_line_color=tech_clr, marker_line_width=1.5,
            text=[f"<b>{v:.0f}</b>" for v in asset_ann["prod_gwh"]],
            textposition="outside",
            textfont=dict(size=11, color=C1, family="Calibri"),
        ))
    fig.update_xaxes(title_text="Year")
    fig.update_yaxes(title_text="GWh")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(text="<b>Annual Production</b>"))
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — Charts Markets (DA, IMB, Reserves)
# ══════════════════════════════════════════════════════════════════════════════

def _monthly_avg(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Return monthly average of a column."""
    d = df[df[col].notna()].copy()
    d["YM"] = pd.to_datetime(d["Date"].astype(str).str[:7])
    return d.groupby("YM")[col].mean().reset_index()


def chart_da_history(bal: pd.DataFrame) -> go.Figure:
    """Monthly average DA price — history."""
    m = _monthly_avg(bal, "DA")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m["YM"], y=m["DA"],
        mode="lines", name="DA monthly avg",
        line=dict(color=COL_DA, width=2),
        fill="tozeroy", fillcolor=rgba(COL_DA, 0.08),
    ))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=380, show_legend=False)
    fig.update_layout(title=dict(text="<b>Day-Ahead Price — Monthly Average (France)</b>"))
    return fig


def chart_imbalance_history(bal: pd.DataFrame) -> go.Figure:
    """Monthly average imbalance prices pos/neg."""
    mp = _monthly_avg(bal, "Imb_Pos")
    mn = _monthly_avg(bal, "Imb_Neg")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mp["YM"], y=mp["Imb_Pos"],
        mode="lines", name="Imbalance Positive",
        line=dict(color=COL_IMB_POS, width=2)))
    fig.add_trace(go.Scatter(
        x=mn["YM"], y=mn["Imb_Neg"],
        mode="lines", name="Imbalance Negative",
        line=dict(color=COL_IMB_NEG, width=2)))
    fig.add_hline(y=0, line=dict(color="#AAAAAA", width=1))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=380)
    fig.update_layout(title=dict(text="<b>Imbalance Prices — Monthly Average (France)</b>"))
    return fig


def chart_balancing_services(bal: pd.DataFrame) -> go.Figure:
    """Monthly average aFRR and mFRR prices."""
    ma = _monthly_avg(bal, "aFRR")
    mm = _monthly_avg(bal, "mFRR")
    fig = go.Figure()
    if len(ma) > 0 and ma["aFRR"].notna().any():
        fig.add_trace(go.Scatter(
            x=ma["YM"], y=ma["aFRR"],
            mode="lines", name="aFRR activated",
            line=dict(color=COL_AFRR, width=2)))
    if len(mm) > 0 and mm["mFRR"].notna().any():
        fig.add_trace(go.Scatter(
            x=mm["YM"], y=mm["mFRR"],
            mode="lines", name="mFRR activated",
            line=dict(color=COL_MFRR, width=2)))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=380)
    fig.update_layout(title=dict(text="<b>Balancing Services — aFRR & mFRR Activated Prices (France)</b>"))
    return fig


def chart_price_comparison(bal: pd.DataFrame) -> go.Figure:
    """DA vs Imbalance spread — monthly, all on same chart."""
    da  = _monthly_avg(bal, "DA")
    imp = _monthly_avg(bal, "Imb_Pos")
    imn = _monthly_avg(bal, "Imb_Neg")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=da["YM"], y=da["DA"],
        mode="lines", name="DA price",
        line=dict(color=COL_DA, width=2.5)))
    fig.add_trace(go.Scatter(
        x=imp["YM"], y=imp["Imb_Pos"],
        mode="lines", name="Imbalance Pos",
        line=dict(color=COL_IMB_POS, width=1.5, dash="dash")))
    fig.add_trace(go.Scatter(
        x=imn["YM"], y=imn["Imb_Neg"],
        mode="lines", name="Imbalance Neg",
        line=dict(color=COL_IMB_NEG, width=1.5, dash="dash")))
    fig.add_hline(y=0, line=dict(color="#AAAAAA", width=1))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=420)
    fig.update_layout(title=dict(text="<b>DA vs Imbalance Prices — Monthly Average (France)</b>"))
    return fig


def chart_da_heatmap(bal: pd.DataFrame) -> go.Figure:
    """DA price heatmap by hour of day and month."""
    h = bal[bal["DA"].notna()].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour
    pivot = h.groupby(["Month","Hour"])["DA"].mean().reset_index()
    p = pivot.pivot(index="Month", columns="Hour", values="DA")
    p.index = [MONTH_NAMES[i-1] for i in p.index]

    fig = go.Figure(data=go.Heatmap(
        z=p.values, x=[f"{h}h" for h in p.columns], y=p.index.tolist(),
        colorscale=[[0, C2],[0.5, C3],[1, C5]],
        text=[[f"<b>{v:.0f}</b>" for v in row] for row in p.values],
        texttemplate="%{text}",
        textfont=dict(size=10, color=C1, family="Calibri"),
        colorbar=dict(title=dict(text="EUR/MWh", font=dict(size=12, color=C1)),
                      tickfont=dict(size=11, color=C1), thickness=14),
    ))
    fig.update_xaxes(title_text="Hour of Day")
    fig.update_yaxes(title_text="Month")
    plotly_base(fig, h=420, show_legend=False)
    fig.update_layout(title=dict(text="<b>DA Price Heatmap — Average by Hour and Month (France)</b>"))
    return fig


def chart_imbalance_spread(bal: pd.DataFrame) -> go.Figure:
    """Monthly spread between imbalance positive and negative."""
    mp = _monthly_avg(bal, "Imb_Pos")
    mn = _monthly_avg(bal, "Imb_Neg")
    merged = mp.merge(mn, on="YM", how="inner")
    merged["spread"] = merged["Imb_Pos"] - merged["Imb_Neg"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=merged["YM"], y=merged["spread"],
        marker_color=[rgba(C5, 0.7) if v > 100 else rgba(C2, 0.7) for v in merged["spread"]],
        marker_line_color=WHT, marker_line_width=0.5,
        name="Imbalance Spread (Pos - Neg)",
    ))
    fig.update_yaxes(title_text="EUR/MWh")
    plotly_base(fig, h=360, show_legend=False)
    fig.update_layout(title=dict(text="<b>Imbalance Spread — Positive minus Negative (EUR/MWh)</b>"))
    return fig


def summary_stats(bal: pd.DataFrame) -> dict:
    """Key stats for the recent period (last 12 months)."""
    cutoff = pd.to_datetime(bal["Date"]).max() - pd.DateOffset(months=12)
    recent = bal[pd.to_datetime(bal["Date"]) >= cutoff]
    stats = {}
    for col, label in [("DA","DA"), ("Imb_Pos","Imb Pos"), ("Imb_Neg","Imb Neg"),
                       ("aFRR","aFRR"), ("mFRR","mFRR")]:
        if col in recent.columns and recent[col].notna().any():
            stats[label] = {
                "mean": recent[col].mean(),
                "min":  recent[col].min(),
                "max":  recent[col].max(),
                "std":  recent[col].std(),
            }
    return stats
