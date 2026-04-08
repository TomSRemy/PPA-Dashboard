"""
update_entsoe.py — Daily ENTSO-E data update
=============================================
Called by GitHub Actions every morning at 08:00 UTC.

What it does:
1. Reads the existing hourly_spot.csv to find the last date already stored
2. Fetches only the missing days from ENTSO-E API (incremental — fast)
3. Computes updated national annual reference (nat_reference.csv)
4. Writes last_update.txt with timestamp and row count

Run manually:
    ENTSOE_API_KEY=your_key python scripts/update_entsoe.py
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
DATA_DIR  = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

SPOT_CSV  = DATA_DIR / "hourly_spot.csv"
NAT_CSV   = DATA_DIR / "nat_reference.csv"
LOG_TXT   = DATA_DIR / "last_update.txt"

# ── ENTSO-E settings ──────────────────────────────────────────────────────────
COUNTRY   = "FR"
DOMAIN    = "10YFR-RTE------C"    # France bidding zone
TZ_LOCAL  = "Europe/Paris"

# ── API key ───────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ENTSOE_API_KEY", "")
if not API_KEY:
    log.error("ENTSOE_API_KEY environment variable not set.")
    log.error("Set it with: export ENTSOE_API_KEY=your_key_here")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTSOE FETCH (with retry + annual chunking)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_da_prices(start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """
    Fetch Day-Ahead prices from ENTSO-E for France.
    Chunks into annual requests to stay within API limits.
    Returns hourly Series EUR/MWh, UTC index.
    """
    try:
        from entsoe import EntsoePandasClient
        client = EntsoePandasClient(api_key=API_KEY)
    except ImportError:
        log.error("entsoe-py not installed. Run: pip install entsoe-py")
        raise

    all_prices = []
    current    = start

    while current < end:
        chunk_end = min(current + pd.DateOffset(years=1), end)
        log.info(f"  Fetching DA prices {current.date()} → {chunk_end.date()}")

        for attempt in range(3):
            try:
                prices = client.query_day_ahead_prices(
                    COUNTRY, start=current, end=chunk_end)
                all_prices.append(prices)
                break
            except Exception as e:
                if attempt == 2:
                    log.warning(f"  Failed after 3 attempts: {e}")
                else:
                    log.warning(f"  Attempt {attempt+1} failed: {e} — retrying in 5s")
                    time.sleep(5)

        current = chunk_end
        time.sleep(1)   # be polite with the API

    if not all_prices:
        return pd.Series(dtype=float)

    series = pd.concat(all_prices)
    series = series[~series.index.duplicated(keep="first")]
    series = series.resample("1h").mean()
    series.name = "Spot"
    return series


def fetch_solar_generation(start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """
    Fetch national solar generation (B16) from ENTSO-E.
    Returns hourly Series in MW, UTC index.
    """
    try:
        from entsoe import EntsoePandasClient
        client = EntsoePandasClient(api_key=API_KEY)
    except ImportError:
        raise

    all_gen = []
    current = start

    while current < end:
        chunk_end = min(current + pd.DateOffset(years=1), end)
        log.info(f"  Fetching solar generation {current.date()} → {chunk_end.date()}")

        for attempt in range(3):
            try:
                gen = client.query_generation(
                    COUNTRY, start=current, end=chunk_end, psr_type="B16")
                # May return DataFrame or Series
                if isinstance(gen, pd.DataFrame):
                    gen = gen.sum(axis=1)
                gen = gen.resample("1h").mean()
                all_gen.append(gen)
                break
            except Exception as e:
                if attempt == 2:
                    log.warning(f"  Solar gen fetch failed: {e}")
                    all_gen.append(pd.Series(dtype=float))
                else:
                    time.sleep(5)

        current = chunk_end
        time.sleep(1)

    if not all_gen:
        return pd.Series(dtype=float)

    series = pd.concat(all_gen)
    series = series[~series.index.duplicated(keep="first")]
    series.name = "NatMW"
    return series


# ═══════════════════════════════════════════════════════════════════════════════
#  INCREMENTAL UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

def load_existing() -> pd.DataFrame:
    """Load existing hourly_spot.csv, return empty DataFrame if not found."""
    if not SPOT_CSV.exists():
        log.info("No existing data file — will fetch from 2014-01-01")
        return pd.DataFrame()

    df = pd.read_csv(SPOT_CSV, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    log.info(f"Existing data: {len(df):,} rows, "
             f"{df['Date'].min().date()} → {df['Date'].max().date()}")
    return df


def find_missing_range(existing: pd.DataFrame) -> tuple:
    """
    Determine what date range needs to be fetched.
    Returns (start, end) as UTC Timestamps, or (None, None) if up to date.
    """
    now_utc = pd.Timestamp.now(tz="UTC")

    # DA prices for J-1 are published by 13:00 CET → available by 12:00 UTC
    # We fetch up to yesterday
    target_end = (now_utc - pd.Timedelta(hours=12)).floor("D")

    if existing.empty:
        start = pd.Timestamp("2014-01-01", tz="UTC")
    else:
        last = existing["Date"].max()
        start = (last + pd.Timedelta(hours=1)).floor("h")

    if start >= target_end:
        log.info("Data already up to date.")
        return None, None

    log.info(f"Need to fetch: {start.date()} → {target_end.date()} "
             f"({(target_end-start).days} days)")
    return start, target_end


def build_new_rows(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Fetch prices + solar gen, merge into hourly DataFrame."""
    prices = fetch_da_prices(start, end)
    solar  = fetch_solar_generation(start, end)

    if prices.empty:
        log.warning("No price data fetched — nothing to add.")
        return pd.DataFrame()

    df = pd.DataFrame({"Spot": prices})

    if not solar.empty:
        df = df.join(solar.rename("NatMW"), how="left")
    else:
        df["NatMW"] = np.nan

    df = df.reset_index().rename(columns={"index": "Date", "utc_time": "Date"})
    if "Date" not in df.columns:
        df = df.reset_index()
        df.columns = ["Date"] + list(df.columns[1:])

    df["Date"]  = pd.to_datetime(df["Date"], utc=True)
    df["Year"]  = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Hour"]  = df["Date"].dt.hour
    df["NatMW"] = df["NatMW"].fillna(0.0)

    df = df[df["Spot"] > -500].copy()   # remove obviously wrong values
    log.info(f"Built {len(df):,} new rows")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  NATIONAL REFERENCE (annual table)
# ═══════════════════════════════════════════════════════════════════════════════

def recompute_nat_reference(hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Recompute annual national M0 from hourly data.
    M0 = volume-weighted average price = sum(NatMW × Spot) / sum(NatMW)
    """
    h = hourly[hourly["Spot"] > 0].copy()
    h["Rev_nat"] = h["NatMW"] * h["Spot"]

    # Only years with at least 8000 hours of data (full year)
    hours_per_year = h.groupby("Year")["Spot"].count()
    complete_years = hours_per_year[hours_per_year >= 8000].index.tolist()

    ann = h[h["Year"].isin(complete_years)].groupby("Year").agg(
        spot    = ("Spot",    "mean"),
        prod_nat= ("NatMW",  "sum"),
        rev_nat = ("Rev_nat", "sum"),
        neg_h   = ("Spot",   lambda x: (x < 0).sum()),
    ).reset_index()

    ann["cp_nat"]     = ann["rev_nat"] / ann["prod_nat"].replace(0, np.nan)
    ann["cp_nat_pct"] = ann["cp_nat"] / ann["spot"]
    ann["shape_disc"] = 1 - ann["cp_nat_pct"]
    ann = ann.rename(columns={"Year": "year"})

    # Keep only meaningful rows
    ann = ann.dropna(subset=["cp_nat_pct"])
    ann = ann[["year","spot","cp_nat","cp_nat_pct","shape_disc","neg_h"]]

    log.info(f"National reference: {len(ann)} complete years "
             f"({ann['year'].min()}–{ann['year'].max()})")
    return ann


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info("ENTSO-E Daily Update")
    log.info("=" * 60)

    # 1. Load existing data
    existing = load_existing()

    # 2. Determine what's missing
    start, end = find_missing_range(existing)

    if start is None:
        log.info("Nothing to update.")
        # Still write last_update.txt
        _write_log(existing, updated=False)
        return

    # 3. Fetch new data
    new_rows = build_new_rows(start, end)

    if new_rows.empty:
        log.warning("No new rows fetched — keeping existing data.")
        _write_log(existing, updated=False)
        return

    # 4. Merge and save
    if existing.empty:
        combined = new_rows
    else:
        # Ensure same columns
        for col in new_rows.columns:
            if col not in existing.columns:
                existing[col] = np.nan
        combined = pd.concat([existing, new_rows], ignore_index=True)
        combined = combined.drop_duplicates(subset=["Date"], keep="last")
        combined = combined.sort_values("Date").reset_index(drop=True)

    # Convert Date to string for CSV (remove timezone info for compatibility)
    combined["Date_str"] = combined["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    save_cols = ["Date_str","Year","Month","Hour","Spot","NatMW"]
    save_df   = combined[save_cols].rename(columns={"Date_str":"Date"})
    save_df.to_csv(SPOT_CSV, index=False)
    log.info(f"Saved {len(save_df):,} rows to {SPOT_CSV}")

    # 5. Recompute national reference
    nat_ref = recompute_nat_reference(combined)
    nat_ref.to_csv(NAT_CSV, index=False)
    log.info(f"Saved national reference: {NAT_CSV}")

    # 6. Write update log
    _write_log(combined, updated=True, new_rows=len(new_rows))

    log.info("=" * 60)
    log.info("Update complete.")
    log.info("=" * 60)


def _write_log(df: pd.DataFrame, updated: bool, new_rows: int = 0):
    now = datetime.now(timezone.utc)
    if df.empty:
        last_date = "N/A"
        total     = 0
    else:
        last_date = str(df["Date"].max())[:10] if "Date" in df.columns else "N/A"
        total     = len(df)

    lines = [
        f"Last update : {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Status      : {'Updated' if updated else 'Already up to date'}",
        f"New rows    : {new_rows:,}",
        f"Total rows  : {total:,}",
        f"Data through: {last_date}",
    ]
    LOG_TXT.write_text("\n".join(lines))
    log.info("\n".join(lines))


if __name__ == "__main__":
    main()
