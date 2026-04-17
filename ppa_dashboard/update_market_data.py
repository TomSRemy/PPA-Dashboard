#!/usr/bin/env python3
"""
update_market_data.py — KAL-EL Market Data Fetcher
Fetches daily: TTF gas, Brent oil, EUA carbon price
Output: ppa_dashboard/data/market_prices.csv

Sources:
  - TTF (€/MWh)  : yfinance  — ticker TTF=F
  - Brent ($/bbl): yfinance  — ticker BZ=F
  - EUA (€/tCO2) : Ember Climate public API

Schedule: daily GitHub Actions (same workflow as ENTSO-E update)
Run manually: python update_market_data.py [--full]
  --full : fetch from 2018-01-01 (backfill)
  default: last 7 days (incremental)
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR.parent / "data"
OUT_FILE   = DATA_DIR / "market_prices.csv"

# ── Config ────────────────────────────────────────────────────────────────────
BRENT_TICKER = "BZ=F"
TTF_TICKER   = "TTF=F"
EMBER_API    = "https://api.ember-climate.org/v2/carbon-price"

FULL_START   = "2018-01-01"
INCR_DAYS    = 14          # fetch last 14 days, merge to avoid gaps

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def fetch_yfinance(ticker: str, start: str, end: str, col_name: str) -> pd.Series:
    """
    Fetch daily OHLCV from Yahoo Finance via yfinance.
    Returns a Series indexed by date (tz-naive), named col_name.
    """
    try:
        import yfinance as yf
        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if df is None or len(df) == 0:
            log(f"  yfinance {ticker}: no data returned")
            return pd.Series(dtype=float, name=col_name)

        close = df["Close"]
        if hasattr(close, "squeeze"):
            close = close.squeeze()
        close.index = pd.to_datetime(close.index).tz_localize(None)
        close.name = col_name
        log(f"  yfinance {ticker}: {len(close)} rows — last {close.iloc[-1]:.2f}")
        return close

    except ImportError:
        log("  yfinance not installed — pip install yfinance")
        return pd.Series(dtype=float, name=col_name)
    except Exception as e:
        log(f"  yfinance {ticker}: ERROR — {e}")
        return pd.Series(dtype=float, name=col_name)


def fetch_ember_eua(start: str, end: str) -> pd.Series:
    """
    Fetch EUA carbon prices from Ember Climate public API.
    Returns a Series indexed by date (tz-naive), named 'EUA_EUR_tCO2'.

    Endpoint: GET https://api.ember-climate.org/v2/carbon-price
    Params: period=daily, series=EUA, start=YYYY-MM-DD, end=YYYY-MM-DD
    No API key required for daily data.
    """
    try:
        params = {
            "period": "daily",
            "series": "EUA",
            "start": start,
            "end": end,
            "limit": 5000,
        }
        headers = {"Accept": "application/json", "User-Agent": "KAL-EL/1.0"}
        resp = requests.get(EMBER_API, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Ember returns {"data": [{"date": "YYYY-MM-DD", "value": float}, ...]}
        if "data" not in data or len(data["data"]) == 0:
            log("  Ember EUA: no data in response")
            return pd.Series(dtype=float, name="EUA_EUR_tCO2")

        df_raw = pd.DataFrame(data["data"])
        df_raw["date"] = pd.to_datetime(df_raw["date"])
        df_raw = df_raw.set_index("date")["value"]
        df_raw.name = "EUA_EUR_tCO2"
        df_raw.index = df_raw.index.tz_localize(None)
        log(f"  Ember EUA: {len(df_raw)} rows — last {df_raw.iloc[-1]:.2f} EUR/tCO2")
        return df_raw

    except requests.HTTPError as e:
        log(f"  Ember EUA: HTTP {e.response.status_code} — {e}")
        return pd.Series(dtype=float, name="EUA_EUR_tCO2")
    except Exception as e:
        log(f"  Ember EUA: ERROR — {e}")
        return pd.Series(dtype=float, name="EUA_EUR_tCO2")


def load_existing() -> pd.DataFrame:
    if OUT_FILE.exists():
        df = pd.read_csv(OUT_FILE, parse_dates=["Date"])
        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        return df
    return pd.DataFrame(columns=["Date", "TTF_EUR_MWh", "Brent_USD_bbl", "EUA_EUR_tCO2"])


def merge_series(existing: pd.DataFrame, *series_list) -> pd.DataFrame:
    """
    Merge new series into existing DataFrame.
    New values overwrite existing for overlapping dates.
    """
    # Build new DataFrame from series
    parts = []
    for s in series_list:
        if s is not None and len(s) > 0:
            parts.append(s.rename(s.name))

    if not parts:
        return existing

    new_df = pd.concat(parts, axis=1).reset_index()
    new_df.columns = ["Date"] + [s.name for s in series_list if s is not None and len(s) > 0]
    new_df["Date"] = pd.to_datetime(new_df["Date"]).dt.normalize()

    # Merge: existing + new, new wins on overlapping dates
    combined = (
        pd.concat([existing, new_df], ignore_index=True)
        .drop_duplicates(subset="Date", keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )

    # Ensure all expected columns exist
    for col in ["TTF_EUR_MWh", "Brent_USD_bbl", "EUA_EUR_tCO2"]:
        if col not in combined.columns:
            combined[col] = float("nan")

    return combined[["Date", "TTF_EUR_MWh", "Brent_USD_bbl", "EUA_EUR_tCO2"]]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true",
                        help="Full refresh from 2018-01-01")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).date()
    if args.full:
        start_str = FULL_START
        log(f"=== FULL REFRESH from {start_str} ===")
    else:
        start_date = today - timedelta(days=INCR_DAYS)
        start_str  = start_date.strftime("%Y-%m-%d")
        log(f"=== INCREMENTAL UPDATE — last {INCR_DAYS} days ({start_str}) ===")

    end_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    existing = load_existing()
    log(f"Existing rows: {len(existing)}")

    log("Fetching TTF (€/MWh)...")
    ttf = fetch_yfinance(TTF_TICKER, start_str, end_str, "TTF_EUR_MWh")
    time.sleep(1)

    log("Fetching Brent ($/bbl)...")
    brent = fetch_yfinance(BRENT_TICKER, start_str, end_str, "Brent_USD_bbl")
    time.sleep(1)

    log("Fetching EUA carbon (€/tCO2)...")
    eua = fetch_ember_eua(start_str, end_str)

    log("Merging...")
    result = merge_series(existing, ttf, brent, eua)
    result.to_csv(OUT_FILE, index=False)

    n_new = len(result) - len(existing)
    log(f"Saved {len(result)} rows to {OUT_FILE} (+{max(n_new,0)} new)")

    # Summary
    for col, unit in [("TTF_EUR_MWh","EUR/MWh"), ("Brent_USD_bbl","$/bbl"), ("EUA_EUR_tCO2","EUR/tCO2")]:
        if col in result.columns and result[col].notna().any():
            last_val  = result[col].dropna().iloc[-1]
            last_date = result.loc[result[col].notna(), "Date"].iloc[-1].strftime("%Y-%m-%d")
            log(f"  {col}: last = {last_val:.2f} {unit} on {last_date}")

    log("Done.")


if __name__ == "__main__":
    main()
