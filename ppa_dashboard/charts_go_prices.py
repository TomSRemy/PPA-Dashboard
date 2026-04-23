"""
charts_go_prices.py — KAL-EL PPA Dashboard
ECharts chart functions for GO price indicators.
To be imported in tab_market_overview.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ── Palette (same as charts_overview_dynamics.py) ────────────────────────────
C1   = "#001219"
C2   = "#0A9396"
C3   = "#EE9B00"
C4   = "#E9D8A6"
C5   = "#BB3E03"
WHT  = "#FFFFFF"
TEAL = "#005F73"
AQUA = "#94D2BD"
REF  = "#C0C0C0"

# One colour per production year
YEAR_COLORS = {
    2020: "#888888",
    2021: "#AAAAAA",
    2022: "#BBBBBB",
    2023: "#BB0000",
    2024: "#005F73",
    2025: "#2A9D5C",
    2026: "#EE9B00",
    2027: "#E76F51",
    2028: "#9B5DE5",
}

_AX = {"color": TEAL, "fontSize": 11, "fontFamily": "Calibri, Arial"}
_GL = {"lineStyle": {"color": "rgba(0,95,115,0.10)", "width": 1}}
_AL = {"show": False}
_AT = {"show": False}
_TT = {
    "backgroundColor": WHT, "borderColor": AQUA, "borderWidth": 1,
    "textStyle": {"color": C1, "fontSize": 12, "fontFamily": "Calibri, Arial"},
    "extraCssText": "border-radius:6px;box-shadow:0 2px 8px rgba(0,95,115,0.12);",
    "trigger": "axis",
}
_LG = {
    "bottom": 0, "left": "center",
    "textStyle": {"color": TEAL, "fontSize": 11, "fontFamily": "Calibri, Arial"},
    "itemWidth": 16, "itemHeight": 3, "icon": "rect",
}
_GR = {"top": 40, "bottom": 60, "left": 56, "right": 16}

GO_CSV = Path("ppa_dashboard/data/go_prices.csv")


def _load_go(product_filter="GO AIB Renewable", source_filter="Commerg"):
    """Load and filter go_prices.csv."""
    if not GO_CSV.exists():
        return None
    df = pd.read_csv(GO_CSV, parse_dates=["mail_date"])
    df = df[df["source"] == source_filter]
    df = df[df["product"] == product_filter]
    df = df.dropna(subset=["bid"])
    df = df.sort_values("mail_date")
    return df


def go_kpi(product="GO AIB Renewable", source="Commerg"):
    """
    Returns dict with latest GO price info for KPI card.
    Keys: last_bid, last_ask, last_date, week_num, delta, year_label
    """
    df = _load_go(product, source)
    if df is None or len(df) == 0:
        return None

    # Y+1 only for KPI
    df1 = df[df["term"] == "Y + 1"].copy()
    if len(df1) == 0:
        df1 = df[df["year"] == df["mail_date"].dt.year + 1].copy()
    if len(df1) == 0:
        return None

    last = df1.iloc[-1]
    prev = df1.iloc[-2] if len(df1) >= 2 else None

    delta = None
    if prev is not None and pd.notna(prev["bid"]):
        delta = round(float(last["bid"]) - float(prev["bid"]), 4)

    return {
        "last_bid":   round(float(last["bid"]), 2),
        "last_ask":   round(float(last["ask"]), 2) if pd.notna(last.get("ask")) else None,
        "last_date":  last["mail_date"].strftime("%d/%m/%Y"),
        "week_num":   int(last["week_num"]) if pd.notna(last["week_num"]) else None,
        "delta":      delta,
        "year_label": int(last["year"]),
        "term":       last.get("term", "Y+1"),
    }


def chart_go_price_indications(
    product="GO AIB Renewable",
    source="Commerg",
    date_start=None,
    date_end=None,
):
    """
    Multi-line chart — one line per production year.
    X axis = mail_date, Y = bid price.
    """
    df = _load_go(product, source)
    if df is None or len(df) == 0:
        return _stub("Données GO non disponibles — vérifier go_prices.csv")

    if date_start:
        df = df[df["mail_date"] >= pd.Timestamp(date_start)]
    if date_end:
        df = df[df["mail_date"] <= pd.Timestamp(date_end)]

    if len(df) == 0:
        return _stub("Aucune donnée sur la période sélectionnée")

    # One series per production year
    years = sorted(df["year"].unique())
    series = []

    for yr in years:
        sub = df[df["year"] == yr].sort_values("mail_date")
        color = YEAR_COLORS.get(yr, "#888888")
        is_recent = yr >= 2024

        data = [[row["mail_date"].strftime("%Y-%m-%d"), round(float(row["bid"]), 4)]
                for _, row in sub.iterrows()]

        series.append({
            "name": str(yr),
            "type": "line",
            "data": data,
            "symbol": "none",
            "smooth": False,
            "lineStyle": {
                "color": color,
                "width": 2.0 if is_recent else 1.2,
                "opacity": 1.0 if is_recent else 0.65,
            },
            "itemStyle": {"color": color},
        })

    return {
        "tooltip": {**_TT, "formatter": "{b}<br/>" + "<br/>".join(
            [f"<span style='color:{YEAR_COLORS.get(y,'#888')}'>{y}</span>: {{c}}" for y in years]
        )},
        "legend": {**_LG, "show": True,
                   "data": [str(y) for y in years]},
        "grid": {**_GR},
        "xAxis": {
            "type": "time",
            "axisLabel": {**_AX, "formatter": "{MMM} {yy}"},
            "axisLine": _AL, "axisTick": _AT, "splitLine": _GL,
        },
        "yAxis": {
            "type": "value",
            "name": "€/MWh",
            "nameTextStyle": {"color": TEAL, "fontSize": 10},
            "axisLabel": {**_AX, "formatter": "{value} €"},
            "splitLine": _GL, "axisLine": _AL, "axisTick": _AT,
            "min": 0,
        },
        "series": series,
        "dataZoom": [
            {"type": "inside", "start": 0, "end": 100},
            {"type": "slider", "start": 0, "end": 100,
             "height": 18, "bottom": 8,
             "textStyle": {"color": TEAL, "fontSize": 10}},
        ],
    }


def chart_go_cal1(
    product="GO AIB Renewable",
    source="Commerg",
    date_start=None,
    date_end=None,
):
    """
    Single line chart — CAL+1 (Y+1) bid price over time.
    """
    df = _load_go(product, source)
    if df is None or len(df) == 0:
        return _stub("Données GO non disponibles")

    # Filter Y+1
    df1 = df[df["term"] == "Y + 1"].copy()
    if len(df1) == 0:
        # Fallback: year = mail year + 1
        df1 = df[df["year"] == df["mail_date"].dt.year + 1].copy()

    if date_start:
        df1 = df1[df1["mail_date"] >= pd.Timestamp(date_start)]
    if date_end:
        df1 = df1[df1["mail_date"] <= pd.Timestamp(date_end)]

    if len(df1) == 0:
        return _stub("Aucune donnée CAL+1 sur la période")

    df1 = df1.sort_values("mail_date")
    data = [[row["mail_date"].strftime("%Y-%m-%d"), round(float(row["bid"]), 4)]
            for _, row in df1.iterrows()]

    return {
        "tooltip": {**_TT,
                    "formatter": "{b}<br/>CAL+1 bid: <b>{c} €/MWh</b>"},
        "legend": {"show": False},
        "grid": {**_GR},
        "xAxis": {
            "type": "time",
            "axisLabel": {**_AX, "formatter": "{MMM} {yy}"},
            "axisLine": _AL, "axisTick": _AT, "splitLine": _GL,
        },
        "yAxis": {
            "type": "value",
            "name": "€/MWh",
            "nameTextStyle": {"color": TEAL, "fontSize": 10},
            "axisLabel": {**_AX, "formatter": "{value} €"},
            "splitLine": _GL, "axisLine": _AL, "axisTick": _AT,
            "min": 0,
        },
        "series": [{
            "name": "GO CAL+1",
            "type": "line",
            "data": data,
            "symbol": "none",
            "smooth": False,
            "lineStyle": {"color": C2, "width": 2},
            "areaStyle": {"color": "rgba(10,147,150,0.08)"},
            "itemStyle": {"color": C2},
        }],
        "dataZoom": [
            {"type": "inside", "start": 0, "end": 100},
            {"type": "slider", "start": 0, "end": 100,
             "height": 18, "bottom": 8,
             "textStyle": {"color": TEAL, "fontSize": 10}},
        ],
    }


def _stub(msg):
    return {"graphic": [{"type": "text", "left": "center", "top": "middle",
                          "style": {"text": msg, "fill": TEAL, "fontSize": 13,
                                    "fontFamily": "Calibri, Arial"}}]}
