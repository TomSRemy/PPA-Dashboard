"""
compute.py — KAL-EL PPA Dashboard v4
PPA pricing logic, regression, projection, asset annual stats.
v4: unified PPA formula including all premiums + margin
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
    rows = []
    for t, yr in enumerate(range(last_yr + 1, last_yr + n + 1)):
        if anchor_val is not None:
            anchor_fsd = 1 - anchor_val
            fsd = anchor_fsd + sl * (t + 1)
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
                imb_eur: float, add_disc: float,
                vol_risk_pct: float = 0.0,
                price_risk_pct: float = 0.0,
                goo_value: float = 1.0,
                margin: float = 1.0) -> dict:
    """
    Unified PPA formula:
    PPA = Forward
          - Forward x Shape Disc
          - Forward x Add. Discount
          - Forward x Vol Risk
          - Forward x Price Risk
          - Imbalance
          + GoO
          + Margin
    """
    shape_disc_eur  = ref_fwd * sd_ch
    add_disc_eur    = ref_fwd * add_disc
    vol_risk_eur    = ref_fwd * vol_risk_pct
    price_risk_eur  = ref_fwd * price_risk_pct
    tot_deductions  = shape_disc_eur + add_disc_eur + vol_risk_eur + price_risk_eur + imb_eur
    ppa             = ref_fwd - tot_deductions + goo_value + margin
    multiplier      = ppa / ref_fwd if ref_fwd > 0 else 0.0
    tot_disc        = tot_deductions / ref_fwd if ref_fwd > 0 else 0.0

    return {
        "ppa":            ppa,
        "multiplier":     multiplier,
        "tot_disc":       tot_disc,
        "shape_disc_eur": shape_disc_eur,
        "add_disc_eur":   add_disc_eur,
        "vol_risk_eur":   vol_risk_eur,
        "price_risk_eur": price_risk_eur,
        "imb_eur":        imb_eur,
        "goo_value":      goo_value,
        "margin":         margin,
    }


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


def detect_technology(asset_raw, hourly,
                      threshold: float = 0.15) -> dict:
    """
    Auto-detect whether an uploaded asset is Solar or Wind
    by comparing its hourly production profile to national Solar/Wind profiles.

    Method:
      - Compute average production by hour-of-day for asset, Solar, Wind
      - Normalise each profile to [0,1]
      - Compute MAE vs Solar and vs Wind
      - Pick the closer one if difference > threshold, else return None (ambiguous)

    Returns:
      dict with keys:
        "techno"      : "Solar" | "Wind" | None (ambiguous)
        "confidence"  : float 0-1 (1 = certain)
        "mae_solar"   : float
        "mae_wind"    : float
        "explanation" : str
    """
    if asset_raw is None or len(asset_raw) < 24:
        return {"techno": None, "confidence": 0, "mae_solar": None,
                "mae_wind": None, "explanation": "Not enough data"}

    # Asset hourly profile
    a = asset_raw.copy()
    a["Date"] = pd.to_datetime(a["Date"])
    a["Hour"] = a["Date"].dt.hour
    asset_profile = a.groupby("Hour")["Prod_MWh"].mean()

    # National profiles from hourly_spot
    h = hourly.copy()
    h["Hour"] = pd.to_datetime(h["Date"]).dt.hour

    solar_profile = h.groupby("Hour")["NatMW"].mean() if "NatMW" in h.columns else None
    wind_profile  = h.groupby("Hour")["WindMW"].mean() \
                    if ("WindMW" in h.columns and h["WindMW"].sum() > 0) else None

    def _normalise(s):
        mn, mx = s.min(), s.max()
        return (s - mn) / (mx - mn) if mx > mn else s * 0

    def _mae(a, b):
        idx = a.index.intersection(b.index)
        if len(idx) < 12:
            return None
        return float(np.mean(np.abs(_normalise(a[idx]) - _normalise(b[idx]))))

    mae_solar = _mae(asset_profile, solar_profile) if solar_profile is not None else None
    mae_wind  = _mae(asset_profile, wind_profile)  if wind_profile  is not None else None

    # Decision
    if mae_solar is None and mae_wind is None:
        return {"techno": None, "confidence": 0,
                "mae_solar": None, "mae_wind": None,
                "explanation": "National profiles unavailable"}

    if mae_solar is None:
        techno = "Wind"
        conf   = max(0.0, 1.0 - mae_wind)
        expl   = f"Wind profile match (MAE {mae_wind:.2f})"
    elif mae_wind is None:
        techno = "Solar"
        conf   = max(0.0, 1.0 - mae_solar)
        expl   = f"Solar profile match (MAE {mae_solar:.2f})"
    else:
        diff = abs(mae_solar - mae_wind)
        if diff < threshold:
            return {"techno": None, "confidence": diff / threshold,
                    "mae_solar": mae_solar, "mae_wind": mae_wind,
                    "explanation": f"Ambiguous — Solar MAE {mae_solar:.2f} vs Wind MAE {mae_wind:.2f}"}
        if mae_solar < mae_wind:
            techno = "Solar"
            conf   = min(1.0, diff / 0.3)
            expl   = f"Solar closer (MAE {mae_solar:.2f} vs Wind {mae_wind:.2f})"
        else:
            techno = "Wind"
            conf   = min(1.0, diff / 0.3)
            expl   = f"Wind closer (MAE {mae_wind:.2f} vs Solar {mae_solar:.2f})"

    return {"techno": techno, "confidence": conf,
            "mae_solar": mae_solar, "mae_wind": mae_wind,
            "explanation": expl}
