"""
data.py — KAL-EL PPA Dashboard
Data loading (cached) and rolling M0 computation.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from config import DATA_DIR

def load_nat() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "nat_reference.csv")
    if "partial" not in df.columns:
        df["partial"] = False
    for col in ["cp_wind", "cp_wind_pct", "shape_disc_wind"]:
        if col not in df.columns:
            df[col] = np.nan
    return df


@st.cache_data(ttl=3600)
def load_hourly() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "hourly_spot.csv", parse_dates=["Date"])
    df["Month"] = df["Date"].dt.month
    if "WindMW" not in df.columns:
        df["WindMW"] = 0.0
    return df


def load_log() -> str:
    p = DATA_DIR / "last_update.txt"
    return p.read_text() if p.exists() else "Initial data loaded."


def wind_available(hourly: pd.DataFrame) -> bool:
    return "WindMW" in hourly.columns and hourly["WindMW"].sum() > 0


@st.cache_data(ttl=3600)
def compute_rolling_m0(hourly_df: pd.DataFrame,
                       prod_col: str = "NatMW",
                       windows: tuple = (30, 90, 365)) -> pd.DataFrame:
    """
    Rolling M0 on RAW hourly data — not a mean of daily means.

    For each calendar day t and window N:
      M0(t)  = sum(MW * Spot) / sum(MW)   over hours in (t-N, t]
      BL(t)  = sum(Spot) / count(hours)   over same window
      CP%(t) = M0(t) / BL(t)
    """
    h = hourly_df.copy()
    h["Date"]     = pd.to_datetime(h["Date"])
    h             = h.sort_values("Date").reset_index(drop=True)
    h["Rev_tech"] = h[prod_col] * h["Spot"]
    h["Date_d"]   = h["Date"].dt.normalize()

    dates = sorted(h["Date_d"].unique())
    rows  = {w: [] for w in windows}

    for d in dates:
        for w in windows:
            cutoff = pd.Timestamp(d) - pd.Timedelta(days=w)
            mask   = (h["Date_d"] > cutoff) & (h["Date_d"] <= d)
            window = h[mask]
            if len(window) < w * 12:
                rows[w].append({"Date": d, f"m0_{w}d": np.nan,
                                 f"bl_{w}d": np.nan, f"cp_{w}d": np.nan})
                continue
            sum_rev  = window["Rev_tech"].sum()
            sum_prod = window[prod_col].sum()
            sum_spot = window["Spot"].sum()
            count_h  = len(window)
            m0 = sum_rev / sum_prod if sum_prod > 0 else np.nan
            bl = sum_spot / count_h
            cp = m0 / bl   if bl != 0 else np.nan
            rows[w].append({"Date": d, f"m0_{w}d": m0,
                             f"bl_{w}d": bl, f"cp_{w}d": cp})

    dfs = [pd.DataFrame(rows[w]).set_index("Date") for w in windows]
    out = pd.concat(dfs, axis=1).reset_index()
    out["Date"] = pd.to_datetime(out["Date"])
    return out


def nat_series(df: pd.DataFrame, col: str, fallback: str) -> list:
    """Return tech-appropriate column, falling back to solar if all-NaN."""
    if col in df.columns and not df[col].isna().all():
        return df[col].fillna(df[fallback]).tolist()
    return df[fallback].tolist()


def get_nat_sd(df: pd.DataFrame, col: str, fallback: str = "shape_disc") -> pd.Series:
    """Return shape discount series for the active technology."""
    if col in df.columns and not df[col].isna().all():
        return df[col].dropna()
    return df[fallback].dropna()

@st.cache_data(ttl=3600)
def load_balancing() -> pd.DataFrame:
    p = DATA_DIR / "balancing_prices.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    return df
