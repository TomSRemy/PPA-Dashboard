#!/usr/bin/env python3
"""
update_entsoe_xborder.py — KAL-EL Cross-Country & FCR Data Fetcher
Fetches daily from ENTSO-E:
  - DA spot prices: DE_LU, BE, ES, IT, NL  (+ FR already in hourly_spot.csv)
  - FCR contracted reserve prices: FR

Outputs:
  ppa_dashboard/data/xborder_da_prices.csv   — hourly DA by country
  ppa_dashboard/data/fcr_prices.csv          — daily FCR capacity prices FR

Usage:
  python update_entsoe_xborder.py            # incremental (last 8 days)
  python update_entsoe_xborder.py --full     # full backfill from 2018-01-01

API key: ENTSOE_API_KEY environment variable (same key as update_entsoe.py)
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR.parent / "data"

DA_FILE  = DATA_DIR / "xborder_da_prices.csv"
FCR_FILE = DATA_DIR / "fcr_prices.csv"

# ── Config ────────────────────────────────────────────────────────────────────
DA_COUNTRIES = {
    "DE": "DE_LU",   # Germany-Luxembourg
    "BE": "BE",
    "ES": "ES",
    "IT": "IT",
    "NL": "NL",
}
FCR_PROCESS_TYPE          = "A51"   # FCR
FCR_AGREEMENT_TYPE        = "A01"   # Daily
FULL_START                = "2020-01-01"   # FCR data sparse before 2020
DA_FULL_START             = "2018-01-01"
INCR_DAYS                 = 8
API_SLEEP                 = 2       # seconds between calls


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def get_client():
    api_key = os.environ.get("ENTSOE_API_KEY", "")
    if not api_key:
        log("ERROR: ENTSOE_API_KEY environment variable not set")
        sys.exit(1)
    from entsoe import EntsoePandasClient
    return EntsoePandasClient(api_key=api_key)


def ts(date_str: str, tz: str = "Europe/Paris") -> pd.Timestamp:
    return pd.Timestamp(date_str, tz=tz)


def strip_tz(s: pd.Series) -> pd.Series:
    if hasattr(s.index, "tz") and s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    return s


# ── DA prices — multi-country ─────────────────────────────────────────────────

def fetch_da_country(client, country_code: str, start: pd.Timestamp,
                     end: pd.Timestamp, col_name: str) -> pd.Series:
    try:
        s = client.query_day_ahead_prices(country_code, start=start, end=end)
        s = s.resample("1h").mean()
        s = strip_tz(s)
        s.name = col_name
        log(f"  DA {country_code}: {len(s)} hours — last {s.dropna().iloc[-1]:.1f} EUR/MWh")
        return s
    except Exception as e:
        log(f"  DA {country_code}: ERROR — {e}")
        return pd.Series(dtype=float, name=col_name)


def load_existing_da() -> pd.DataFrame:
    if DA_FILE.exists():
        df = pd.read_csv(DA_FILE, parse_dates=["Date"])
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        return df
    cols = ["Date"] + list(DA_COUNTRIES.keys())
    return pd.DataFrame(columns=cols)


def update_da_prices(client, start_str: str, end_str: str):
    log("--- DA prices (multi-country) ---")
    existing = load_existing_da()
    log(f"  Existing: {len(existing)} rows")

    start = ts(start_str); end = ts(end_str)
    series_list = []

    for short_name, entsoe_code in DA_COUNTRIES.items():
        s = fetch_da_country(client, entsoe_code, start, end, short_name)
        series_list.append(s)
        time.sleep(API_SLEEP)

    if not any(len(s) > 0 for s in series_list):
        log("  No new data fetched — skipping")
        return

    new_df = pd.concat(series_list, axis=1).reset_index()
    new_df.columns = ["Date"] + [s.name for s in series_list]
    new_df["Date"] = pd.to_datetime(new_df["Date"]).dt.tz_localize(None)

    combined = (
        pd.concat([existing, new_df], ignore_index=True)
        .drop_duplicates(subset="Date", keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )
    for col in DA_COUNTRIES.keys():
        if col not in combined.columns:
            combined[col] = float("nan")

    cols = ["Date"] + list(DA_COUNTRIES.keys())
    combined[cols].to_csv(DA_FILE, index=False)
    log(f"  Saved {len(combined)} rows to {DA_FILE}")


# ── FCR prices — France ───────────────────────────────────────────────────────

def fetch_fcr(client, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """
    query_contracted_reserve_prices returns a DataFrame with columns like
    ['Procurement Price [EUR/MW per period]'] indexed by timestamp.
    We resample to daily average.
    """
    try:
        df = client.query_contracted_reserve_prices(
            country_code="FR",
            process_type=FCR_PROCESS_TYPE,
            type_marketagreement_type=FCR_AGREEMENT_TYPE,
            start=start,
            end=end,
        )
        if df is None or len(df) == 0:
            log("  FCR: no data returned")
            return pd.DataFrame()

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" | ".join(str(c) for c in col).strip() for col in df.columns]

        # Strip timezone
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Take numeric columns only, resample to daily mean
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            log("  FCR: no numeric columns found")
            return pd.DataFrame()

        # Use first numeric column as FCR price
        fcr_series = df[num_cols[0]].resample("1D").mean()
        fcr_df = fcr_series.reset_index()
        fcr_df.columns = ["Date", "FCR_EUR_MW_day"]
        fcr_df["Date"] = pd.to_datetime(fcr_df["Date"]).dt.normalize()
        log(f"  FCR: {len(fcr_df)} days — last {fcr_df['FCR_EUR_MW_day'].dropna().iloc[-1]:.1f} EUR/MW/day")
        return fcr_df

    except Exception as e:
        log(f"  FCR: ERROR — {e}")
        return pd.DataFrame()


def load_existing_fcr() -> pd.DataFrame:
    if FCR_FILE.exists():
        df = pd.read_csv(FCR_FILE, parse_dates=["Date"])
        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        return df
    return pd.DataFrame(columns=["Date", "FCR_EUR_MW_day"])


def update_fcr(client, start_str: str, end_str: str):
    log("--- FCR prices (France) ---")
    existing = load_existing_fcr()
    log(f"  Existing: {len(existing)} rows")

    start = ts(start_str); end = ts(end_str)
    new_df = fetch_fcr(client, start, end)

    if len(new_df) == 0:
        log("  No FCR data — skipping")
        return

    combined = (
        pd.concat([existing, new_df], ignore_index=True)
        .drop_duplicates(subset="Date", keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )
    combined.to_csv(FCR_FILE, index=False)
    log(f"  Saved {len(combined)} rows to {FCR_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true",
                        help="Full refresh from historical start dates")
    parser.add_argument("--da-only",  action="store_true", help="Only fetch DA prices")
    parser.add_argument("--fcr-only", action="store_true", help="Only fetch FCR prices")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = get_client()

    today    = datetime.now(timezone.utc).date()
    end_str  = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    run_da  = not args.fcr_only
    run_fcr = not args.da_only

    if args.full:
        da_start  = DA_FULL_START
        fcr_start = FULL_START
        log(f"=== FULL REFRESH — DA from {da_start}, FCR from {fcr_start} ===")
    else:
        da_start  = (today - timedelta(days=INCR_DAYS)).strftime("%Y-%m-%d")
        fcr_start = da_start
        log(f"=== INCREMENTAL — last {INCR_DAYS} days ({da_start}) ===")

    if run_da:
        update_da_prices(client, da_start, end_str)

    if run_fcr:
        time.sleep(API_SLEEP)
        update_fcr(client, fcr_start, end_str)

    log("=== Done ===")


if __name__ == "__main__":
    main()
