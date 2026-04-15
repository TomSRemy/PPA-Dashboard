"""
update_entsoe.py — Incremental daily update
Fetches only missing hours (Spot + NatMW + WindMW).
Updates nat_reference.csv including cap_solar_gw / cap_wind_gw.
Called automatically every morning at 08:00 UTC via GitHub Actions.
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

ROOT       = Path(__file__).parent.parent
DATA_DIR   = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
SPOT_CSV   = DATA_DIR / "hourly_spot.csv"
NAT_CSV    = DATA_DIR / "nat_reference.csv"
LOG_TXT    = DATA_DIR / "last_update.txt"
COUNTRY    = "FR"

API_KEY = os.environ.get("ENTSOE_API_KEY", "")
if not API_KEY:
    log.error("ENTSOE_API_KEY not set.")
    sys.exit(1)


def _get_client():
    try:
        from entsoe import EntsoePandasClient
        return EntsoePandasClient(api_key=API_KEY)
    except ImportError:
        log.error("entsoe-py not installed.")
        raise


def _fetch(client, fetch_fn, label, start, end):
    chunks = []
    cur    = start
    while cur < end:
        chunk_end = min(cur + pd.DateOffset(years=1), end)
        log.info(f"  {label}: {cur.date()} -> {chunk_end.date()}")
        for attempt in range(3):
            try:
                r = fetch_fn(cur, chunk_end)
                if isinstance(r, pd.DataFrame):
                    r = r.sum(axis=1)
                chunks.append(r.resample("1h").mean())
                break
            except Exception as e:
                if attempt == 2:
                    log.warning(f"  {label} failed: {e}")
                else:
                    time.sleep(5)
        cur = chunk_end
        time.sleep(1)
    if not chunks:
        return pd.Series(dtype=float)
    s = pd.concat(chunks)
    return s[~s.index.duplicated(keep="first")].resample("1h").mean()


def fetch_installed_capacity_year(client, year: int) -> dict:
    """Fetch installed capacity for a single year. Returns dict with cap_solar_gw, cap_wind_gw."""
    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    end   = pd.Timestamp(f"{year}-12-31", tz="UTC")
    result = {"cap_solar_gw": np.nan, "cap_wind_gw": np.nan}
    wind_vals = []
    for psr, key in [("B16","solar"), ("B19","wind_on"), ("B18","wind_off")]:
        try:
            time.sleep(0.5)
            df = client.query_installed_generation_capacity(
                COUNTRY, start=start, end=end, psr_type=psr)
            if isinstance(df, pd.DataFrame):
                val = df.iloc[-1].sum() / 1000
            elif isinstance(df, pd.Series):
                val = df.iloc[-1] / 1000
            else:
                val = np.nan
            if key == "solar":
                result["cap_solar_gw"] = val
            else:
                wind_vals.append(val)
        except Exception as e:
            log.warning(f"  Installed cap {psr} {year}: {e}")
    if wind_vals:
        total_wind = sum(v for v in wind_vals if not np.isnan(v))
        result["cap_wind_gw"] = total_wind if total_wind > 0 else np.nan
    return result


def load_existing():
    if not SPOT_CSV.exists():
        log.error("No CSV found — run update_entsoe_full.py first.")
        sys.exit(1)
    df = pd.read_csv(SPOT_CSV, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    if "WindMW" not in df.columns:
        df["WindMW"] = 0.0
    log.info(f"Existing: {len(df):,} rows, "
             f"{df['Date'].min().date()} -> {df['Date'].max().date()}")
    return df


def get_range(existing):
    end   = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=12)).floor("D")
    start = (existing["Date"].max() + pd.Timedelta(hours=1)).floor("h")
    if start >= end:
        log.info("Already up to date.")
        return None, None
    log.info(f"Fetch range: {start.date()} -> {end.date()} (incremental)")
    return start, end


def fetch_new_rows(client, start, end):
    prices = _fetch(client, lambda s, e: client.query_day_ahead_prices(COUNTRY, start=s, end=e),
                    "DA prices", start, end)
    if prices.empty:
        return pd.DataFrame()
    prices.name = "Spot"
    solar = _fetch(client, lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B16"),
                   "Solar B16", start, end)
    solar.name = "NatMW"
    on  = _fetch(client, lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B19"),
                 "Wind B19", start, end)
    off = _fetch(client, lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B18"),
                 "Wind B18", start, end)
    if on.empty and off.empty:
        wind = pd.Series(dtype=float, name="WindMW")
    else:
        wind = on.add(off, fill_value=0) if not on.empty and not off.empty else (off if on.empty else on)
        wind.name = "WindMW"

    df = pd.DataFrame({"Spot": prices})
    df = df.join(solar if not solar.empty else pd.Series(name="NatMW", dtype=float), how="left")
    df = df.join(wind  if not wind.empty  else pd.Series(name="WindMW",dtype=float), how="left")
    df = df.reset_index().rename(columns={"index":"Date","utc_time":"Date"})
    if "Date" not in df.columns:
        df = df.reset_index(); df.columns = ["Date"] + list(df.columns[1:])
    df["Date"]   = pd.to_datetime(df["Date"], utc=True)
    df["Year"]   = df["Date"].dt.year
    df["Month"]  = df["Date"].dt.month
    df["Hour"]   = df["Date"].dt.hour
    df["NatMW"]  = df["NatMW"].fillna(0.0)
    df["WindMW"] = df["WindMW"].fillna(0.0)
    df = df[df["Spot"] > -500].copy()
    log.info(f"Fetched {len(df):,} new rows")
    return df


def recompute_nat(hourly, existing_nat=None):
    h = hourly[hourly["Spot"] > 0].copy()
    h["Rev_nat"]  = h["NatMW"]  * h["Spot"]
    has_wind      = h["WindMW"].sum() > 0
    if has_wind:
        h["Rev_wind"] = h["WindMW"] * h["Spot"]
    current_year = pd.Timestamp.now().year
    hpy  = h.groupby("Year")["Spot"].count()
    min_h = {yr: (500 if yr == current_year else 8000) for yr in hpy.index}
    complete = [yr for yr, cnt in hpy.items() if cnt >= min_h[yr]]
    agg = {
        "spot":     ("Spot",   "mean"),
        "prod_nat": ("NatMW",  "sum"),
        "rev_nat":  ("Rev_nat","sum"),
        "neg_h":    ("Spot",   lambda x: (x < 0).sum()),
        "n_hours":  ("Spot",   "count"),
    }
    if has_wind:
        agg["prod_wind"] = ("WindMW",   "sum")
        agg["rev_wind"]  = ("Rev_wind", "sum")
    ann = h[h["Year"].isin(complete)].groupby("Year").agg(**agg).reset_index()
    ann["cp_nat"]     = ann["rev_nat"] / ann["prod_nat"].replace(0, np.nan)
    ann["cp_nat_pct"] = ann["cp_nat"] / ann["spot"]
    ann["shape_disc"] = 1 - ann["cp_nat_pct"]
    if has_wind:
        ann["cp_wind"]         = ann["rev_wind"] / ann["prod_wind"].replace(0, np.nan)
        ann["cp_wind_pct"]     = ann["cp_wind"] / ann["spot"]
        ann["shape_disc_wind"] = 1 - ann["cp_wind_pct"]
    else:
        ann["cp_wind"] = ann["cp_wind_pct"] = ann["shape_disc_wind"] = np.nan
    ann["partial"] = ann["Year"] == current_year
    ann = ann.rename(columns={"Year":"year"}).dropna(subset=["cp_nat_pct"])

    # Carry over installed capacity from existing nat_reference if available
    if existing_nat is not None and "cap_solar_gw" in existing_nat.columns:
        cap_cols = ["year","cap_solar_gw","cap_wind_gw"]
        cap_cols = [c for c in cap_cols if c in existing_nat.columns]
        ann = ann.merge(existing_nat[cap_cols], on="year", how="left")
    else:
        ann["cap_solar_gw"] = np.nan
        ann["cap_wind_gw"]  = np.nan

    keep = ["year","spot","cp_nat","cp_nat_pct","shape_disc",
            "cp_wind","cp_wind_pct","shape_disc_wind",
            "neg_h","n_hours","partial","cap_solar_gw","cap_wind_gw"]
    ann = ann[[c for c in keep if c in ann.columns]]
    log.info(f"Nat reference: {len(ann)} years ({ann['year'].min()}-{ann['year'].max()})")
    return ann


def update_capacity_current_year(client, nat_df: pd.DataFrame) -> pd.DataFrame:
    """Update installed capacity for current year only."""
    current_year = pd.Timestamp.now().year
    log.info(f"Updating installed capacity for {current_year}...")
    try:
        cap = fetch_installed_capacity_year(client, current_year)
        for col, val in cap.items():
            if col not in nat_df.columns:
                nat_df[col] = np.nan
            nat_df.loc[nat_df["year"] == current_year, col] = val
        log.info(f"  Solar: {cap['cap_solar_gw']:.1f} GW | Wind: {cap['cap_wind_gw']:.1f} GW")
    except Exception as e:
        log.warning(f"Capacity update failed: {e}")
    return nat_df


def save(df):
    out = df.copy()
    out["Date_str"] = out["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out[["Date_str","Year","Month","Hour","Spot","NatMW","WindMW"]].rename(
        columns={"Date_str":"Date"}).to_csv(SPOT_CSV, index=False)
    log.info(f"Saved {len(out):,} rows -> {SPOT_CSV}")


def write_log(df, new_rows):
    now   = datetime.now(timezone.utc)
    lines = [
        f"Last update : {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Mode        : Incremental",
        f"New rows    : {new_rows:,}",
        f"Total rows  : {len(df):,}",
        f"Data through: {str(df['Date'].max())[:10] if not df.empty else 'N/A'}",
        f"Columns     : Spot | NatMW (B16) | WindMW (B18+B19)",
    ]
    LOG_TXT.write_text("\n".join(lines))
    log.info("\n".join(lines))


def main():
    log.info("="*60)
    log.info("ENTSO-E Incremental Update")
    log.info("="*60)

    existing = load_existing()
    start, end = get_range(existing)

    # Load existing nat_reference to preserve capacity columns
    existing_nat = pd.read_csv(NAT_CSV) if NAT_CSV.exists() else None

    client = _get_client()

    if start is None:
        # Already up to date — just recompute nat + update capacity for current year
        nat = recompute_nat(existing, existing_nat)
        nat = update_capacity_current_year(client, nat)
        nat.to_csv(NAT_CSV, index=False)
        write_log(existing, 0)
        return

    new_rows = fetch_new_rows(client, start, end)
    if new_rows.empty:
        log.warning("Nothing fetched.")
        write_log(existing, 0)
        return

    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined = combined.drop_duplicates(subset=["Date"], keep="last")
    combined = combined.sort_values("Date").reset_index(drop=True)

    save(combined)

    nat = recompute_nat(combined, existing_nat)
    nat = update_capacity_current_year(client, nat)
    nat.to_csv(NAT_CSV, index=False)

    write_log(combined, len(new_rows))
    log.info("="*60)
    log.info("Done.")
    log.info("="*60)


if __name__ == "__main__":
    main()
