"""
compute.py — KAL-EL PPA Dashboard v3
PPA pricing logic, regression, projection, asset annual stats.
"""

import pandas as pd
import numpy as np
from scipy import stats


def compute_asset_annual(hourly: pd.DataFrame,
                         asset_df: pd.DataFrame,
                         prod_col: str = "NatMW") -> pd.DataFrame:
    a = asset_df.copy()
    a["Date"] = pd.to_datetime(a["Date"])
    a = a.set_index("Date").resample("1h").mean().reset_index()
    m = hourly.merge(a[["Date", "Prod_MWh"]], on="Date", how="inner")
    m = m[m["Spot"] > 0].copy()
    m["Rev"] = m["Prod_MWh"] * m["Spot"]
    ann = m.groupby("Year").agg(
        prod_mwh  = ("Prod_MWh", "sum"),
        revenue   = ("Rev",      "sum"),
        spot_avg  = ("Spot",     "mean"),
        prod_hours= ("Prod_MWh", lambda x: (x > 0).sum()),
        neg_hours = ("Spot",     lambda x: (x < 0).sum()),
        nat_mw    = (prod_col,   "mean"),
    ).reset_index()
    ann["prod_gwh"]   = ann["prod_mwh"] / 1000
    ann["cp_eur"]     = ann["revenue"] / ann["prod_mwh"].replace(0, np.nan)
    ann["cp_pct"]     = ann["cp_eur"]  / ann["spot_avg"]
    ann["shape_disc"] = 1 - ann["cp_pct"]
    return ann.dropna(subset=["cp_pct"])


def fit_reg(ann: pd.DataFrame, n: int, ex22: bool):
    d = ann.copy()
    if "partial" in d.columns:
        d = d[d["partial"] != True]
    elif "Year" in d.columns:
        d = d[d["Year"] < pd.Timestamp.now().year]
    if ex22:
        yr_col = "Year" if "Year" in d.columns else "year"
        d = d[d[yr_col] != 2022]
    d = d.tail(n).dropna(subset=["shape_disc"])
    if len(d) < 2:
        d = ann.dropna(subset=["shape_disc"])
    if len(d) < 2:
        return 0.0, float(ann["shape_disc"].mean()) if len(ann) else 0.15, 0.0
    x = d["Year"].values.astype(float) if "Year" in d.columns else d["year"].values.astype(float)
    y = d["shape_disc"].values
    sl, ic, r, *_ = stats.linregress(x, y)
    return float(sl), float(ic), float(r**2)


def project_cp(sl: float, ic: float, last_yr: int,
               n: int = 5, sig: float = 0.04,
               anchor_val: float = None) -> pd.DataFrame:
    """
    Project CP% with cumulative uncertainty bands (P10/P25/P50/P75/P90).

    anchor_val: if provided, the P50 at last_yr+1 is anchored to this value
                (last observed asset CP%), and subsequent years follow the slope.
                If None, projection uses the regression line directly.
    """
    rows = []
    for t, yr in enumerate(range(last_yr + 1, last_yr + n + 1)):
        if anchor_val is not None:
            # Anchor first point on last asset value, then apply slope
            fsd = (1 - anchor_val) + sl * t
        else:
            fsd = ic + sl * yr
        cs = sig * np.sqrt(t + 1)
        rows.append({
            "year": yr, "fsd": fsd,
            "p10": 1 - (fsd + 1.28  * cs),
            "p25": 1 - (fsd + 0.674 * cs),
            "p50": 1 - fsd,
            "p75": 1 - (fsd - 0.674 * cs),
            "p90": 1 - (fsd - 1.28  * cs),
        })
    return pd.DataFrame(rows)


def compute_ppa(ref_fwd: float, sd_ch: float,
                imb_eur: float, add_disc: float) -> dict:
    imb_pct    = imb_eur / ref_fwd if ref_fwd > 0 else 0.0
    tot_disc   = sd_ch + imb_pct + add_disc
    multiplier = 1 - tot_disc
    ppa        = ref_fwd * multiplier - imb_eur
    return {"imb_pct": imb_pct, "tot_disc": tot_disc,
            "multiplier": multiplier, "ppa": ppa}


def compute_pnl_curve(ref_fwd: float, ppa: float, vol_mwh: float,
                      sd_vals: list) -> list:
    cp_vals = [ref_fwd * (1 - s) for s in sd_vals]
    return [vol_mwh * (c - ppa) / 1000 for c in cp_vals]


def compute_scenarios(ref_fwd: float, ppa: float, vol_mwh: float,
                      hist_sd_f: pd.Series, proj_n: int,
                      vol_stress: int, spot_stress: int) -> list:
    sd_med = float(np.percentile(hist_sd_f, 50)) if len(hist_sd_f) > 0 else 0.15
    scenarios = [
        ("Base",                     1.00,                   0.00,            0.00),
        (f"Cannib +{vol_stress}%",   1.00,          +vol_stress/100,          0.00),
        (f"Cannib -{vol_stress}%",   1.00,          -vol_stress/100,          0.00),
        (f"Spot +{spot_stress}%",    1+spot_stress/100,      0.00,            0.00),
        (f"Spot -{spot_stress}%",    1-spot_stress/100,      0.00,            0.00),
        (f"Vol +{vol_stress}%",      1.00,                   0.00,   +vol_stress/100),
        (f"Vol -{vol_stress}%",      1.00,                   0.00,   -vol_stress/100),
        ("Total Stress",             1-spot_stress/100,  +vol_stress/100, -vol_stress/100),
        ("Total Bull",               1+spot_stress/100,  -vol_stress/100, +vol_stress/100),
    ]
    results = []
    for name, sm, da, va in scenarios:
        sdp10 = float(np.percentile(hist_sd_f, 10)) + da if len(hist_sd_f) > 0 else 0.10
        sdp90 = float(np.percentile(hist_sd_f, 90)) + da if len(hist_sd_f) > 0 else 0.30
        base  = vol_mwh * (1 + va) / 1000 * proj_n
        p50t  = base * (sm * ref_fwd * (1 - (sd_med + da)) - ppa)
        p10t  = base * (sm * ref_fwd * (1 - sdp90)         - ppa)
        p90t  = base * (sm * ref_fwd * (1 - sdp10)         - ppa)
        results.append({"Scenario": name, "p10": p10t, "p50": p50t, "p90": p90t})
    return results
