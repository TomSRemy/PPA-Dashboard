"""
charts_overview_dynamics.py — KAL-EL PPA Dashboard
ECharts chart functions for tab_overview (Tab 1) and tab_market_dynamics (Tab 3).
Each function returns an ECharts options dict or (dict, data) tuple.
"""

import pandas as pd
import numpy as np
from scipy import stats

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Palette ───────────────────────────────────────────────────────────────────
C1   = "#001219"
C2   = "#0A9396"
C3   = "#EE9B00"
C4   = "#E9D8A6"
C5   = "#BB3E03"
WHT  = "#FFFFFF"
TEAL = "#005F73"
AQUA = "#94D2BD"
REF  = "#C0C0C0"

MONTH_COLORS = [
    "#1D3A4A","#2A9D8F","#E9C46A","#F4A261","#E76F51","#005F73",
    "#8ECAE6","#219EBC","#023047","#FFB703","#FB8500","#94D2BD",
]

# ── Shared style tokens ───────────────────────────────────────────────────────
_AX  = {"color": TEAL, "fontSize": 11, "fontFamily": "Calibri, Arial"}
_GL  = {"lineStyle": {"color": "rgba(0,95,115,0.10)", "width": 1}}
_AL  = {"show": False}
_AT  = {"show": False}
_TT  = {
    "backgroundColor": WHT, "borderColor": AQUA, "borderWidth": 1,
    "textStyle": {"color": C1, "fontSize": 12, "fontFamily": "Calibri, Arial"},
    "extraCssText": "border-radius:6px;box-shadow:0 2px 8px rgba(0,95,115,0.12);",
}
_LG  = {
    "bottom": 0, "left": "center",
    "textStyle": {"color": TEAL, "fontSize": 11, "fontFamily": "Calibri, Arial"},
    "itemWidth": 12, "itemHeight": 8, "icon": "roundRect",
}
_GR  = {"top": 32, "bottom": 52, "left": 52, "right": 16}

def _tt_fmt(unit=""):
    suffix = f" {unit}" if unit else ""
    return f"(v) => v !== null && v !== undefined ? v.toFixed(1) + '{suffix}' : '-'"

def _hex_rgba(h, a):
    h = h.lstrip("#")
    r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"rgba({r},{g},{b},{a})"

def _stub(msg):
    return {"graphic":[{"type":"text","left":"center","top":"middle",
                        "style":{"text":msg,"fill":TEAL,"fontSize":13,
                                 "fontFamily":"Calibri, Arial"}}]}

def _xcat(data):
    return {"type":"category","data":data,"axisLine":_AL,"axisTick":_AT,
            "axisLabel":_AX,"splitLine":_GL}

def _yval(fmt="{value}",name="",pos="left",mn=None,mx=None):
    y = {"type":"value","name":name,"nameTextStyle":{"color":TEAL,"fontSize":10},
         "axisLabel":{**_AX,"formatter":fmt},"splitLine":_GL,
         "axisLine":_AL,"axisTick":_AT,"position":pos}
    if mn is not None: y["min"] = mn
    if mx is not None: y["max"] = mx
    return y

def _ytime():
    return {"type":"time","axisLine":_AL,"axisTick":_AT,
            "axisLabel":{**_AX,"formatter":"{MMM} {yyyy}"},"splitLine":_GL}


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ══════════════════════════════════════════════════════════════════════════════

def chart_historical_cp(nat_ref, asset_ann, has_asset, asset_name,
                        tech_clr, tech_lbl, nat_cp_list, nat_eur_list, partial_years):
    ny   = nat_ref["year"].tolist()
    ns   = nat_ref["spot"].tolist()
    is_p = nat_ref["partial"].tolist() if "partial" in nat_ref.columns else [False]*len(ny)

    bar_nat = []
    for i, (v, p) in enumerate(zip(nat_cp_list, is_p)):
        color = _hex_rgba(C3, 0.65) if p else _hex_rgba(tech_clr, 0.65)
        bar_nat.append({
            "value": round(float(v)*100, 1),
            "itemStyle": {"color": color, "borderRadius": [4,4,0,0]},
            "label": {"show": True, "position": "top",
                      "formatter": f"{round(float(v)*100):.0f}%{'  YTD' if p else ''}",
                      "color": C1, "fontSize": 11},
        })

    series_top = [
        {"name": f"M0 National {tech_lbl}", "type": "bar",
         "data": bar_nat, "barGap": "15%", "barCategoryGap": "35%"},
    ]

    if has_asset:
        asset_cp_map = dict(zip(asset_ann["Year"].tolist(), asset_ann["cp_pct"].tolist()))
        bar_asset = []
        for yr in ny:
            v = asset_cp_map.get(yr)
            if v is None:
                bar_asset.append({"value": None})
            else:
                bar_asset.append({
                    "value": round(float(v) * 100, 1),
                    "itemStyle": {"color": _hex_rgba(C5, 0.60), "borderRadius": [4, 4, 0, 0]},
                    "label": {"show": True, "position": "top",
                               "formatter": f"{round(float(v)*100):.0f}%",
                               "color": C5, "fontSize": 10},
                })
        series_top.append({"name": asset_name, "type": "bar", "data": bar_asset})

    series_top.append({
        "name": "_trend", "type": "line",
        "data": [[str(y), round(float(v)*100, 1)] for y,v in zip(ny,nat_cp_list)],
        "symbol": "square", "symbolSize": 7,
        "lineStyle": {"color": tech_clr, "width": 1.8, "type": "dashed"},
        "itemStyle": {"color": tech_clr, "borderColor": WHT, "borderWidth": 1},
        "showInLegend": False,
    })

    opt_top = {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("%")},
        "legend": {**_LG, "show": True},
        "grid": {**_GR, "bottom": 52},
        "xAxis": _xcat([str(y) for y in ny]),
        "yAxis": _yval("{value}%", "CP%", mn=0, mx=120),
        "markLine": {"data": [{"yAxis": 100, "name": "100%",
                               "lineStyle": {"color": REF, "type": "dotted", "width": 1},
                               "label": {"formatter": "100%", "color": TEAL, "fontSize": 10}}],
                     "symbol": "none"},
        "series": series_top,
    }

    series_bot = [
        {"name": "National Spot", "type": "line",
         "data": [[str(y), round(float(v),2)] for y,v in zip(ny,ns)],
         "symbol": "circle", "symbolSize": 6,
         "lineStyle": {"color": AQUA, "width": 1.5, "type": "dashed"},
         "itemStyle": {"color": AQUA}},
        {"name": f"M0 {tech_lbl} EUR", "type": "line",
         "data": [[str(y), round(float(v),2)] for y,v in zip(ny,nat_eur_list)],
         "symbol": "square", "symbolSize": 7,
         "lineStyle": {"color": tech_clr, "width": 1.8},
         "itemStyle": {"color": tech_clr, "borderColor": WHT, "borderWidth": 1}},
    ]
    if has_asset:
        series_bot.append({
            "name": f"{asset_name} EUR", "type": "line",
            "data": [[str(y), round(float(v),2)]
                     for y,v in zip(asset_ann["Year"].tolist(), asset_ann["cp_eur"].tolist())],
            "symbol": "circle", "symbolSize": 7,
            "lineStyle": {"color": C5, "width": 1.8},
            "itemStyle": {"color": C5, "borderColor": WHT, "borderWidth": 1},
        })

    opt_bot = {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("€/MWh")},
        "legend": {**_LG, "show": True},
        "grid": {**_GR, "bottom": 52},
        "xAxis": _xcat([str(y) for y in ny]),
        "yAxis": _yval("{value} €", "€/MWh"),
        "series": series_bot,
    }

    return opt_top, opt_bot


def chart_projection(nat_ref, asset_ann, has_asset, proj,
                     nat_cp_list, nat_ref_complete, nat_cp_col,
                     tech_clr, tech_lbl, sl_u, ic_u, r2_u,
                     last_yr_proj, proj_n, ex22,
                     reg_basis="Asset", anchor_val=None, proj_targets=None):
    ny = nat_ref["year"].tolist()
    py = proj["year"].tolist()

    p10 = proj["p10"].tolist(); p90 = proj["p90"].tolist()
    p25 = proj["p25"].tolist(); p75 = proj["p75"].tolist()
    p50 = proj["p50"].tolist()

    if anchor_val is not None:
        hl = anchor_val
    elif has_asset:
        hl = float(asset_ann["cp_pct"].iloc[-1])
    elif nat_cp_col in nat_ref_complete.columns and not nat_ref_complete[nat_cp_col].isna().all():
        hl = float(nat_ref_complete[nat_cp_col].iloc[-1])
    else:
        hl = float(nat_ref_complete["cp_nat_pct"].iloc[-1])

    tx = list(range(2014, last_yr_proj + proj_n + 1))
    trend_y = [round((1 - (ic_u + sl_u * yr)) * 100, 2) for yr in tx]

    series = []

    series.append({
        "name": "P10–P90", "type": "line",
        "data": [[str(y), round(v * 100, 2)] for y, v in zip(py, p90)],
        "symbol": "none", "lineStyle": {"color": "transparent", "width": 0},
        "areaStyle": {"color": _hex_rgba(C3, 0.20), "origin": "start"},
        "showInLegend": True, "z": 1,
    })
    series.append({
        "name": "_p10_mask", "type": "line",
        "data": [[str(y), round(v * 100, 2)] for y, v in zip(py, p10)],
        "symbol": "none", "lineStyle": {"color": "transparent", "width": 0},
        "areaStyle": {"color": "#F7F4F0", "origin": "start", "opacity": 1},
        "showInLegend": False, "z": 2,
    })
    series.append({
        "name": "P25–P75", "type": "line",
        "data": [[str(y), round(v * 100, 2)] for y, v in zip(py, p75)],
        "symbol": "none", "lineStyle": {"color": "transparent", "width": 0},
        "areaStyle": {"color": _hex_rgba(C3, 0.38), "origin": "start"},
        "showInLegend": True, "z": 3,
    })
    series.append({
        "name": "_p25_mask", "type": "line",
        "data": [[str(y), round(v * 100, 2)] for y, v in zip(py, p25)],
        "symbol": "none", "lineStyle": {"color": "transparent", "width": 0},
        "areaStyle": {"color": "#F7F4F0", "origin": "start", "opacity": 1},
        "showInLegend": False, "z": 4,
    })
    series.append({
        "name": "Régression", "type": "line",
        "data": [[str(y), round(v, 2)] for y, v in zip(tx, trend_y)],
        "symbol": "none",
        "lineStyle": {"color": REF, "width": 1.6, "type": "dotted"},
        "z": 5,
    })
    series.append({
        "name": f"M0 National {tech_lbl}", "type": "line",
        "data": [[str(y), round(float(v) * 100, 2)] for y, v in zip(ny, nat_cp_list)],
        "symbol": "rect", "symbolSize": 8,
        "lineStyle": {"color": tech_clr, "width": 2, "type": "dashed"},
        "itemStyle": {"color": tech_clr, "borderColor": WHT, "borderWidth": 1},
        "z": 6,
    })

    if has_asset:
        series.append({
            "name": "Asset (historique)", "type": "line",
            "data": [[str(y), round(float(v) * 100, 2)]
                     for y, v in zip(asset_ann["Year"].tolist(), asset_ann["cp_pct"].tolist())],
            "symbol": "circle", "symbolSize": 9,
            "lineStyle": {"color": C5, "width": 2.2},
            "itemStyle": {"color": C5, "borderColor": WHT, "borderWidth": 2},
            "label": {"show": True, "position": "top", "formatter": "{c}%",
                      "color": C5, "fontSize": 11,
                      "backgroundColor": "rgba(255,255,255,0.75)",
                      "padding": [2, 4], "borderRadius": 3},
            "z": 8,
        })

    p50_data = ([[str(last_yr_proj), round(hl * 100, 2)]] +
                [[str(y), round(float(v) * 100, 2)] for y, v in zip(py, p50)])
    series.append({
        "name": "P50 (central)", "type": "line",
        "data": p50_data,
        "symbol": "circle", "symbolSize": 8, "smooth": False,
        "lineStyle": {"color": C1, "width": 2.5},
        "itemStyle": {"color": C1, "borderColor": WHT, "borderWidth": 2},
        "label": {"show": True, "position": "top", "formatter": "{c}%",
                  "color": C1, "fontSize": 11,
                  "backgroundColor": "rgba(255,255,255,0.75)",
                  "padding": [2, 4], "borderRadius": 3},
        "z": 9,
    })

    if proj_targets:
        for t in proj_targets:
            series.append({
                "name": f"PPE3 {t['year']}", "type": "scatter",
                "data": [[str(t["year"]), round(float(t["cp"]) * 100, 2)]],
                "symbol": "diamond", "symbolSize": 16,
                "itemStyle": {"color": TEAL},
                "label": {"show": True, "position": "right",
                          "formatter": f"PPE3 {t['year']}\n{round(float(t['cp'])*100):.0f}%",
                          "color": TEAL, "fontSize": 10},
                "z": 10,
            })

    all_years = sorted(set([str(y) for y in ny + tx + py]))

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("%")},
        "legend": {**_LG, "show": True},
        "grid": {**_GR, "bottom": 56},
        "xAxis": _xcat(all_years),
        "yAxis": _yval("{value}%", "CP%", mn=15, mx=115),
        "series": series,
        "title": {"text": f"Pente: {-sl_u*100:.2f}%/an  R²: {r2_u:.3f} | {reg_basis}",
                  "textStyle": {"color": TEAL, "fontSize": 11}, "left": "center"},
    }


def chart_daily_profile_national(hourly, prod_col, tech_clr, tech_lbl):
    h = hourly[hourly[prod_col] > 0].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour
    month_avg   = h.groupby(["Month","Hour"])[prod_col].mean().reset_index()
    overall_avg = h.groupby("Hour")[prod_col].mean().reset_index()

    hours = [f"{i}h" for i in range(24)]
    series = []

    for m in range(1, 13):
        d = month_avg[month_avg["Month"]==m].sort_values("Hour")
        if len(d) == 0: continue
        vals = [float(d[d["Hour"]==hr][prod_col].iloc[0])
                if len(d[d["Hour"]==hr]) > 0 else None for hr in range(24)]
        series.append({
            "name": MONTH_NAMES[m-1], "type": "line",
            "data": vals, "symbol": "none", "smooth": False,
            "lineStyle": {"color": MONTH_COLORS[m-1], "width": 1.2},
            "opacity": 0.65,
        })

    avg_vals = [float(overall_avg[overall_avg["Hour"]==hr][prod_col].iloc[0])
                if len(overall_avg[overall_avg["Hour"]==hr]) > 0 else None for hr in range(24)]
    series.append({
        "name": "Annual average", "type": "line",
        "data": avg_vals, "symbol": "circle", "symbolSize": 7, "smooth": False,
        "lineStyle": {"color": C1, "width": 2.5},
        "itemStyle": {"color": C1, "borderColor": WHT, "borderWidth": 2},
        "z": 10,
    })

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("MW")},
        "legend": {**_LG, "show": True, "type": "scroll"},
        "grid": {**_GR, "bottom": 56},
        "xAxis": _xcat(hours),
        "yAxis": _yval("{value} MW", "Avg MW"),
        "series": series,
    }


def chart_daily_profile_asset(asset_raw, tech_clr, asset_name):
    a = asset_raw.copy()
    a["Date"]  = pd.to_datetime(a["Date"])
    a["Hour"]  = a["Date"].dt.hour
    a["Month"] = a["Date"].dt.month

    month_avg   = a.groupby(["Month","Hour"])["Prod_MWh"].mean().reset_index()
    overall_avg = a.groupby("Hour")["Prod_MWh"].mean().reset_index()

    hours = [f"{i}h" for i in range(24)]
    series = []

    for m in range(1, 13):
        d = month_avg[month_avg["Month"]==m].sort_values("Hour")
        if len(d) == 0: continue
        vals = [float(d[d["Hour"]==hr]["Prod_MWh"].iloc[0])
                if len(d[d["Hour"]==hr]) > 0 else None for hr in range(24)]
        series.append({
            "name": MONTH_NAMES[m-1], "type": "line",
            "data": vals, "symbol": "none", "smooth": False,
            "lineStyle": {"color": MONTH_COLORS[m-1], "width": 1.2, "type": "dotted"},
            "opacity": 0.65,
        })

    avg_vals = [float(overall_avg[overall_avg["Hour"]==hr]["Prod_MWh"].iloc[0])
                if len(overall_avg[overall_avg["Hour"]==hr]) > 0 else None for hr in range(24)]
    series.append({
        "name": "Annual average", "type": "line",
        "data": avg_vals, "symbol": "circle", "symbolSize": 7, "smooth": False,
        "lineStyle": {"color": tech_clr, "width": 2.5},
        "itemStyle": {"color": tech_clr, "borderColor": WHT, "borderWidth": 2},
        "z": 10,
    })

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("MWh")},
        "legend": {**_LG, "show": True, "type": "scroll"},
        "grid": {**_GR, "bottom": 56},
        "xAxis": _xcat(hours),
        "yAxis": _yval("{value} MWh", "Avg MWh"),
        "series": series,
    }


def chart_monthly_production(hourly, asset_raw, prod_col, tech_clr, asset_name, has_asset):
    nat = hourly[hourly[prod_col] > 0].copy()
    nat_avg = nat.groupby("Month")[prod_col].mean().reset_index()

    series = []

    if has_asset and asset_raw is not None:
        a = asset_raw.copy()
        a["Date"]  = pd.to_datetime(a["Date"])
        a["Month"] = a["Date"].dt.month
        asset_mo   = a.groupby("Month")["Prod_MWh"].sum().reset_index()
        n_years    = a["Date"].dt.year.nunique()
        asset_mo["GWh"] = asset_mo["Prod_MWh"] / 1000 / max(n_years, 1)

        gwh_data = []
        for m in range(1, 13):
            row = asset_mo[asset_mo["Month"] == m]
            v = float(row["GWh"].iloc[0]) if len(row) > 0 else 0
            gwh_data.append({
                "value": round(v, 2),
                "itemStyle": {"color": _hex_rgba(tech_clr, 0.72), "borderRadius": [4,4,0,0]},
            })
        series.append({
            "name": f"{asset_name} (GWh)", "type": "bar",
            "data": gwh_data, "yAxisIndex": 0,
            "barCategoryGap": "40%",
            "label": {"show": True, "position": "top",
                      "formatter": "{c}", "color": C1, "fontSize": 10},
        })

    nat_data = []
    for m in range(1, 13):
        row = nat_avg[nat_avg["Month"] == m]
        nat_data.append(float(row[prod_col].iloc[0]) if len(row) > 0 else None)

    series.append({
        "name": "National avg MW", "type": "line",
        "data": nat_data, "yAxisIndex": 1,
        "symbol": "circle", "symbolSize": 8, "smooth": False,
        "lineStyle": {"color": C1, "width": 1.8, "type": "dashed"},
        "itemStyle": {"color": C1, "borderColor": WHT, "borderWidth": 2},
    })

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("")},
        "legend": {**_LG, "show": True},
        "grid": {**_GR, "right": 52},
        "xAxis": _xcat(MONTH_NAMES),
        "yAxis": [
            _yval("{value} GWh", "GWh/mois"),
            _yval("{value} MW", "MW national", pos="right"),
        ],
        "series": series,
    }


def chart_annual_production(hourly, asset_ann, prod_col, tech_clr, asset_name, has_asset, partial_years):
    if not has_asset or asset_ann is None:
        return _stub("Charger une courbe de charge asset dans la sidebar")

    years = asset_ann["Year"].tolist()
    bar_data = []
    for i, (y, v) in enumerate(zip(years, asset_ann["prod_gwh"].tolist())):
        color = _hex_rgba(C3, 0.65) if y in partial_years else _hex_rgba(tech_clr, 0.72)
        bar_data.append({
            "value": round(float(v), 1),
            "itemStyle": {"color": color, "borderRadius": [4,4,0,0]},
        })

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("GWh")},
        "legend": {**_LG, "show": False},
        "grid": {**_GR},
        "xAxis": _xcat([str(y) for y in years]),
        "yAxis": _yval("{value} GWh", "GWh"),
        "series": [{
            "name": f"{asset_name} (GWh)", "type": "bar",
            "data": bar_data, "barCategoryGap": "45%",
            "label": {"show": True, "position": "top",
                      "formatter": "{c}", "color": C1, "fontSize": 11},
        }],
    }


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Market Dynamics
# ══════════════════════════════════════════════════════════════════════════════

def chart_neg_hours(hourly, partial_years, tech_clr):
    neg = hourly[hourly["Spot"] < 0].groupby("Year").size().reset_index(name="neg_hours")
    all_yrs = pd.DataFrame({"Year": sorted(hourly["Year"].unique())})
    neg = all_yrs.merge(neg, on="Year", how="left").fillna(0)
    neg["neg_hours"] = neg["neg_hours"].astype(int)

    bar_data = []
    for v, yr in zip(neg["neg_hours"], neg["Year"]):
        if yr in partial_years: color = _hex_rgba(C3, 0.70)
        elif v > 300: color = _hex_rgba(C5, 0.80)
        elif v > 100: color = _hex_rgba(C3, 0.65)
        else: color = _hex_rgba(tech_clr, 0.70)
        lbl = f"{int(v)}" + (" YTD" if yr in partial_years else "")
        bar_data.append({"value": int(v),
                         "itemStyle": {"color": color, "borderRadius": [4,4,0,0]},
                         "label": {"show": True, "position": "top",
                                   "formatter": lbl, "color": C1, "fontSize": 11}})

    series = [{"name": "Heures négatives", "type": "bar",
               "data": bar_data, "barCategoryGap": "40%"}]

    neg_c = neg[~neg["Year"].isin(partial_years)]
    if len(neg_c) >= 3:
        xn = neg_c["Year"].values.astype(float)
        yn = neg_c["neg_hours"].values.astype(float)
        sln, icn, *_ = stats.linregress(xn, yn)
        fut = list(range(int(xn.min()), int(xn.max())+4))
        trend_y = [round(max(0, icn+sln*yr), 1) for yr in fut]
        series.append({
            "name": f"Tendance ({sln:+.0f}h/an)", "type": "line",
            "data": [[str(y), v] for y,v in zip(fut, trend_y)],
            "symbol": "none", "smooth": False,
            "lineStyle": {"color": C5, "width": 1.8, "type": "dashed"},
        })

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("h")},
        "legend": {**_LG, "show": True},
        "grid": {**_GR},
        "xAxis": _xcat([str(y) for y in neg["Year"].tolist()]),
        "yAxis": _yval("{value}h", "Heures", mn=0),
        "markLine": {"data": [{"yAxis": 15, "name": "Seuil CRE 15h",
                               "lineStyle": {"color": C2, "type": "dashed", "width": 1.5},
                               "label": {"formatter": "Seuil CRE 15h",
                                         "color": C2, "fontSize": 10}}],
                     "symbol": "none"},
        "series": series,
    }


def chart_monthly_profile(hourly, prod_col, tech_clr, tech_lbl):
    """Returns (opt_dict, monthly_agg_df)"""
    monthly = hourly.copy()
    monthly["Rev_tech"] = monthly[prod_col] * monthly["Spot"]
    monthly_agg = monthly[monthly["Spot"] > 0].groupby(["Year","Month"]).agg(
        spot_avg=("Spot","mean"), prod_tech=(prod_col,"sum"), rev_tech=("Rev_tech","sum"),
    ).reset_index()
    monthly_agg["m0"]   = monthly_agg["rev_tech"] / monthly_agg["prod_tech"].replace(0, np.nan)
    monthly_agg["sd_m"] = 1 - monthly_agg["m0"] / monthly_agg["spot_avg"]
    month_avg = monthly_agg.groupby("Month")["sd_m"].agg(["mean","std"]).reset_index()

    bar_data = []
    for _, row in month_avg.iterrows():
        v = float(row["mean"]); s = float(row["std"]) if pd.notna(row["std"]) else 0
        if v > 0.15: color = _hex_rgba(C5, 0.75)
        elif v > 0.08: color = _hex_rgba(C3, 0.65)
        else: color = _hex_rgba(tech_clr, 0.70)
        bar_data.append({"value": round(v*100, 2),
                         "itemStyle": {"color": color, "borderRadius": [4,4,0,0]}})

    opt = {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("%")},
        "grid": {**_GR},
        "xAxis": _xcat(MONTH_NAMES),
        "yAxis": _yval("{value}%", "Shape Discount moyen"),
        "series": [{
            "name": f"Shape Discount — {tech_lbl}", "type": "bar",
            "data": bar_data, "barCategoryGap": "40%",
            "label": {"show": True, "position": "top",
                      "formatter": "{c}%", "color": C1, "fontSize": 10},
        }],
    }
    return opt, monthly_agg


def chart_shape_disc_delta(nat_ref, nat_sd_col, tech_clr, tech_lbl):
    sd = nat_ref[["year"]].copy()
    sd["shape_disc"] = nat_ref[nat_sd_col].fillna(nat_ref["shape_disc"])
    sd = sd.dropna().sort_values("year")
    sd["delta"] = sd["shape_disc"].diff()
    sd = sd.dropna(subset=["delta"])

    bar_data = []
    for _, row in sd.iterrows():
        v = float(row["delta"])
        color = _hex_rgba(C5, 0.75) if v > 0 else _hex_rgba(tech_clr, 0.70)
        bar_data.append({"value": round(v*100, 2),
                         "itemStyle": {"color": color, "borderRadius": [4,4,0,0]},
                         "label": {"show": True,
                                   "position": "top" if v >= 0 else "bottom",
                                   "formatter": f"{v*100:+.1f}pp",
                                   "color": C1, "fontSize": 11}})

    return {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("pp")},
        "grid": {**_GR},
        "xAxis": _xcat([str(int(y)) for y in sd["year"].tolist()]),
        "yAxis": _yval("{value}%", "Delta Shape Disc (pp)"),
        "series": [{"name": f"Delta SD — {tech_lbl}", "type": "bar",
                    "data": bar_data, "barCategoryGap": "40%"}],
    }


def chart_heatmap(monthly_agg, tech_clr, tech_lbl):
    pivot = monthly_agg.pivot(index="Year", columns="Month", values="sd_m")
    pivot.columns = [MONTH_NAMES[c-1] for c in pivot.columns]
    years  = [str(y) for y in pivot.index.tolist()]
    months = MONTH_NAMES

    data = []
    for yi, yr in enumerate(pivot.index):
        for mi, mo in enumerate(MONTH_NAMES):
            if mo in pivot.columns:
                v = pivot.loc[yr, mo]
                if pd.notna(v):
                    data.append([mi, yi, round(float(v)*100, 1)])

    return {
        "tooltip": {**_TT, "trigger": "item",
                    "formatter": "{b}: {c[2]:.1f}%"},
        "grid": {"top": 32, "bottom": 60, "left": 52, "right": 80},
        "xAxis": {"type":"category","data":months,"axisLine":_AL,"axisTick":_AT,
                  "axisLabel":_AX,"splitLine":{"show":False}},
        "yAxis": {"type":"category","data":years,"axisLine":_AL,"axisTick":_AT,
                  "axisLabel":_AX},
        "visualMap": {
            "min": 0, "max": 30, "calculable": True,
            "orient": "horizontal", "left": "center", "bottom": 0,
            "inRange": {"color": ["#FFFFFF", tech_clr, C3, C5]},
            "textStyle": {"color": TEAL, "fontSize": 11},
            "formatter": "{value}%",
        },
        "series": [{
            "type": "heatmap", "data": data,
            "label": {"show": True, "formatter": "{c}%", "color": C1, "fontSize": 10},
        }],
    }


def chart_market_value_vs_penetration(hourly, prod_col, tech_clr, tech_lbl, partial_years, n_bins=20):
    h = hourly[hourly[prod_col] > 0].copy()
    if len(h) < 100: return _stub("Pas assez de données")
    h = h[~h["Year"].isin(partial_years)]
    bins = pd.cut(h[prod_col], bins=n_bins)
    agg = h.groupby(bins, observed=True).agg(
        avg_spot=("Spot","mean"), avg_mw=(prod_col,"mean"), count=(prod_col,"count")
    ).reset_index()
    agg = agg[agg["count"] > 20]
    if len(agg) == 0: return _stub("Pas assez de données par bin")

    max_mw = agg["avg_mw"].max()
    scatter_data = []
    for _, row in agg.iterrows():
        alpha = 0.4 + 0.5*(float(row["avg_mw"])/max_mw)
        size = min(8 + float(row["count"])/200, 22)
        scatter_data.append({
            "value": [round(float(row["avg_mw"]),1), round(float(row["avg_spot"]),1)],
            "symbolSize": round(size),
            "itemStyle": {"color": _hex_rgba(tech_clr, alpha)},
        })

    series = [{"name": "Spot moyen par bin MW", "type": "scatter",
               "data": scatter_data, "large": True}]

    if len(agg) >= 4:
        sl, ic, r, _, _ = stats.linregress(agg["avg_mw"].astype(float),
                                            agg["avg_spot"].astype(float))
        x0, x1 = float(agg["avg_mw"].min()), float(agg["avg_mw"].max())
        series.append({
            "name": f"Tendance (R²={r**2:.2f})", "type": "line",
            "data": [[round(x0,1), round(ic+sl*x0,1)], [round(x1,1), round(ic+sl*x1,1)]],
            "symbol": "none",
            "lineStyle": {"color": C1, "width": 2, "type": "dashed"},
        })

    return {
        "tooltip": {**_TT, "trigger": "item",
                    "formatter": "{a}<br/>MW: {c[0]}<br/>Prix: {c[1]} €/MWh"},
        "legend": {**_LG, "show": True},
        "grid": {**_GR},
        "xAxis": {"type":"value","name":f"Production {tech_lbl} (MW)",
                  "nameLocation":"middle","nameGap":30,
                  "axisLabel":_AX,"splitLine":_GL,"axisLine":_AL,"axisTick":_AT},
        "yAxis": _yval("{value} €", "Prix spot moyen (€/MWh)"),
        "series": series,
    }


def chart_duck_curve(hourly, tech_clr, tech_lbl, duck_months, recent_years=None):
    h = hourly[hourly["Month"].isin(duck_months)].copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h["Hour"] = h["Date"].dt.hour
    monthly_avg = h.groupby(["Year","Month"])["Spot"].transform("mean")
    h["norm_spot"] = h["Spot"] / monthly_avg.replace(0, np.nan)
    hourly_avg = h.groupby(["Year","Hour"])["norm_spot"].mean().reset_index()

    all_years = sorted(hourly_avg["Year"].unique())
    years = all_years[-recent_years:] if recent_years and len(all_years) >= recent_years else all_years
    hourly_avg = hourly_avg[hourly_avg["Year"].isin(years)]

    n = max(len(years), 1)
    hours = [f"{i}h" for i in range(24)]
    series = []

    for i, yr in enumerate(years):
        alpha = 0.25 + 0.75*i/(n-1) if n > 1 else 1.0
        is_last = (yr == years[-1])
        d = hourly_avg[hourly_avg["Year"]==yr].sort_values("Hour")
        vals = []
        for hr in range(24):
            row = d[d["Hour"]==hr]
            vals.append(float(row["norm_spot"].iloc[0]) if len(row) > 0 else None)
        series.append({
            "name": str(yr), "type": "line",
            "data": vals, "symbol": "none", "smooth": False,
            "lineStyle": {
                "color": _hex_rgba(tech_clr, alpha),
                "width": 2.2 if is_last else 1.2,
            },
            "z": 10 if is_last else 1,
        })

    series[-1]["markLine"] = {
        "data": [{"yAxis": 1.0, "lineStyle": {"color": REF, "type": "dotted", "width": 1.5},
                  "label": {"formatter": "Moy. mensuelle = 1.0",
                            "color": TEAL, "fontSize": 10}}],
        "symbol": "none",
    }

    opt = {
        "tooltip": {**_TT, "trigger": "axis", "valueFormatter": _tt_fmt("x")},
        "legend": {**_LG, "show": True, "type": "scroll"},
        "grid": {**_GR, "bottom": 56},
        "xAxis": _xcat(hours),
        "yAxis": _yval("{value}x", "Prix normalisé (moy. = 1)"),
        "series": series,
    }

    if 4 in duck_months or 5 in duck_months:
        opt["visualMap"] = {
            "show": False, "type": "piecewise",
            "pieces": [{"min": 9.5, "max": 15.5}],
        }

    return opt
