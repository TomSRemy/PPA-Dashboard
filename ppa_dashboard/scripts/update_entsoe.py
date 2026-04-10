"""
update_entsoe.py — Daily ENTSO-E data update  (v2.3)

Changes vs v2.2:
- Adds fetch_wind_generation() fetching B18 (offshore) + B19 (onshore)
- Saves WindMW column in hourly_spot.csv
- Computes cp_wind / cp_wind_pct / shape_disc_wind in nat_reference.csv
- Backward-compatible: adds WindMW=NaN for existing rows when column missing

Run manually:
  ENTSOE_API_KEY=your_key python scripts/update_entsoe.py
"""

import os, sys, time, logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
SPOT_CSV = DATA_DIR / "hourly_spot.csv"
NAT_CSV  = DATA_DIR / "nat_reference.csv"
LOG_TXT  = DATA_DIR / "last_update.txt"
COUNTRY  = "FR"
TZ_LOCAL = "Europe/Paris"

API_KEY = os.environ.get("ENTSOE_API_KEY", "")
if not API_KEY:
    log.error("ENTSOE_API_KEY environment variable not set.")
    sys.exit(1)


# ── Fetch helpers ─────────────────────────────────────────────────────────────

def _get_client():
    try:
        from entsoe import EntsoePandasClient
        return EntsoePandasClient(api_key=API_KEY)
    except ImportError:
        log.error("entsoe-py not installed.")
        raise


def _fetch_series(client, fetch_fn, label, start, end):
    """Generic chunked fetcher with retry. Returns hourly Series."""
    all_chunks = []
    current    = start
    while current < end:
        chunk_end = min(current + pd.DateOffset(years=1), end)
        log.info(f"  Fetching {label} {current.date()} -> {chunk_end.date()}")
        for attempt in range(3):
            try:
                result = fetch_fn(current, chunk_end)
                if isinstance(result, pd.DataFrame):
                    result = result.sum(axis=1)
                result = result.resample("1h").mean()
                all_chunks.append(result)
                break
            except Exception as e:
                if attempt == 2:
                    log.warning(f"  {label} failed after 3 attempts: {e}")
                else:
                    log.warning(f"  {label} attempt {attempt+1} failed — retrying in 5s")
                    time.sleep(5)
        current = chunk_end
        time.sleep(1)
    if not all_chunks:
        return pd.Series(dtype=float)
    s = pd.concat(all_chunks)
    s = s[~s.index.duplicated(keep="first")].resample("1h").mean()
    return s


def fetch_da_prices(start, end):
    client = _get_client()
    s = _fetch_series(client,
                      lambda s, e: client.query_day_ahead_prices(COUNTRY, start=s, end=e),
                      "DA prices", start, end)
    s.name = "Spot"
    return s


def fetch_solar_generation(start, end):
    client = _get_client()
    s = _fetch_series(client,
                      lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B16"),
                      "Solar B16", start, end)
    s.name = "NatMW"
    return s


def fetch_wind_generation(start, end):
    """Fetch onshore (B19) + offshore (B18) wind, return combined hourly Series."""
    client = _get_client()
    s_on  = _fetch_series(client,
                          lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B19"),
                          "Wind onshore B19", start, end)
    s_off = _fetch_series(client,
                          lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B18"),
                          "Wind offshore B18", start, end)
    if s_on.empty and s_off.empty:
        return pd.Series(dtype=float, name="WindMW")
    if s_on.empty:
        combined = s_off
    elif s_off.empty:
        combined = s_on
    else:
        combined = s_on.add(s_off, fill_value=0)
    combined.name = "WindMW"
    return combined


# ── Load / merge ──────────────────────────────────────────────────────────────

def load_existing():
    if not SPOT_CSV.exists():
        log.info("No existing data — will fetch from 2014-01-01")
        return pd.DataFrame()
    df = pd.read_csv(SPOT_CSV, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    if "WindMW" not in df.columns:
        log.info("WindMW column not found — adding as NaN (will be filled on next full fetch)")
        df["WindMW"] = np.nan
    log.info(f"Existing: {len(df):,} rows, {df['Date'].min().date()} -> {df['Date'].max().date()}")
    return df


def find_missing_range(existing):
    now_utc    = pd.Timestamp.now(tz="UTC")
    target_end = (now_utc - pd.Timedelta(hours=12)).floor("D")
    if existing.empty:
        start = pd.Timestamp("2014-01-01", tz="UTC")
    else:
        start = (existing["Date"].max() + pd.Timedelta(hours=1)).floor("h")
    if start >= target_end:
        log.info("Data already up to date.")
        return None, None
    log.info(f"Need to fetch: {start.date()} -> {target_end.date()} ({(target_end-start).days} days)")
    return start, target_end


def build_new_rows(start, end):
    prices = fetch_da_prices(start, end)
    solar  = fetch_solar_generation(start, end)
    wind   = fetch_wind_generation(start, end)

    if prices.empty:
        log.warning("No price data — nothing to add.")
        return pd.DataFrame()

    df = pd.DataFrame({"Spot": prices})
    if not solar.empty:
        df = df.join(solar.rename("NatMW"), how="left")
    else:
        df["NatMW"] = np.nan
    if not wind.empty:
        df = df.join(wind.rename("WindMW"), how="left")
    else:
        df["WindMW"] = np.nan

    df = df.reset_index().rename(columns={"index": "Date", "utc_time": "Date"})
    if "Date" not in df.columns:
        df = df.reset_index()
        df.columns = ["Date"] + list(df.columns[1:])

    df["Date"]   = pd.to_datetime(df["Date"], utc=True)
    df["Year"]   = df["Date"].dt.year
    df["Month"]  = df["Date"].dt.month
    df["Hour"]   = df["Date"].dt.hour
    df["NatMW"]  = df["NatMW"].fillna(0.0)
    df["WindMW"] = df["WindMW"].fillna(0.0)
    df = df[df["Spot"] > -500].copy()
    log.info(f"Built {len(df):,} new rows")
    return df


# ── National reference ────────────────────────────────────────────────────────

def recompute_nat_reference(hourly):
    h = hourly[hourly["Spot"] > 0].copy()
    h["Rev_nat"]  = h["NatMW"]  * h["Spot"]
    has_wind = "WindMW" in h.columns and h["WindMW"].sum() > 0
    if has_wind:
        h["Rev_wind"] = h["WindMW"] * h["Spot"]

    current_year   = pd.Timestamp.now().year
    hours_per_year = h.groupby("Year")["Spot"].count()
    min_hours = {yr: (500 if yr == current_year else 8000) for yr in hours_per_year.index}
    complete_years = [yr for yr, cnt in hours_per_year.items() if cnt >= min_hours[yr]]

    agg = {
        "spot":     ("Spot",    "mean"),
        "prod_nat": ("NatMW",   "sum"),
        "rev_nat":  ("Rev_nat", "sum"),
        "neg_h":    ("Spot",    lambda x: (x < 0).sum()),
        "n_hours":  ("Spot",    "count"),
    }
    if has_wind:
        agg["prod_wind"] = ("WindMW",   "sum")
        agg["rev_wind"]  = ("Rev_wind", "sum")

    ann = h[h["Year"].isin(complete_years)].groupby("Year").agg(**agg).reset_index()
    ann["cp_nat"]     = ann["rev_nat"] / ann["prod_nat"].replace(0, np.nan)
    ann["cp_nat_pct"] = ann["cp_nat"] / ann["spot"]
    ann["shape_disc"] = 1 - ann["cp_nat_pct"]

    if has_wind:
        ann["cp_wind"]         = ann["rev_wind"] / ann["prod_wind"].replace(0, np.nan)
        ann["cp_wind_pct"]     = ann["cp_wind"] / ann["spot"]
        ann["shape_disc_wind"] = 1 - ann["cp_wind_pct"]
    else:
        ann["cp_wind"]         = np.nan
        ann["cp_wind_pct"]     = np.nan
        ann["shape_disc_wind"] = np.nan

    ann["partial"] = ann["Year"] == current_year
    ann = ann.rename(columns={"Year": "year"}).dropna(subset=["cp_nat_pct"])
    keep = ["year","spot","cp_nat","cp_nat_pct","shape_disc",
            "cp_wind","cp_wind_pct","shape_disc_wind","neg_h","n_hours","partial"]
    ann = ann[[c for c in keep if c in ann.columns]]
    log.info(f"National reference: {len(ann)} years ({ann['year'].min()}-{ann['year'].max()})")
    return ann


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("ENTSO-E Daily Update v2.3")
    log.info("=" * 60)

    existing = load_existing()
    start, end = find_missing_range(existing)

    if start is None:
        if not existing.empty:
            nat_ref = recompute_nat_reference(existing)
            nat_ref.to_csv(NAT_CSV, index=False)
        _write_log(existing, updated=False)
        return

    new_rows = build_new_rows(start, end)
    if new_rows.empty:
        log.warning("No new rows — keeping existing data.")
        _write_log(existing, updated=False)
        return

    if existing.empty:
        combined = new_rows
    else:
        for col in new_rows.columns:
            if col not in existing.columns:
                existing[col] = np.nan
        combined = pd.concat([existing, new_rows], ignore_index=True)
        combined = combined.drop_duplicates(subset=["Date"], keep="last")
        combined = combined.sort_values("Date").reset_index(drop=True)

    combined["Date_str"] = combined["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    save_cols = [c for c in ["Date_str","Year","Month","Hour","Spot","NatMW","WindMW"]
                 if c in combined.columns]
    save_df = combined[save_cols].rename(columns={"Date_str": "Date"})
    save_df.to_csv(SPOT_CSV, index=False)
    log.info(f"Saved {len(save_df):,} rows to {SPOT_CSV}")

    nat_ref = recompute_nat_reference(combined)
    nat_ref.to_csv(NAT_CSV, index=False)
    _write_log(combined, updated=True, new_rows=len(new_rows))

    log.info("=" * 60)
    log.info("Update complete.")
    log.info("=" * 60)


def _write_log(df, updated, new_rows=0):
    now       = datetime.now(timezone.utc)
    last_date = str(df["Date"].max())[:10] if not df.empty and "Date" in df.columns else "N/A"
    total     = len(df) if not df.empty else 0
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
