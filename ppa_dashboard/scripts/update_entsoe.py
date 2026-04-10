"""
update_entsoe.py v2.5
Incremental by default. Auto full refresh if WindMW missing or all-zero.
GitHub Actions runs this every morning at 08:00 UTC automatically.
"""

from entsoe import EntsoePandasClient
import pandas as pd

client = EntsoePandasClient(api_key="TON_API_KEY")
start  = pd.Timestamp("2024-01-01", tz="Europe/Paris")
end    = pd.Timestamp("2024-02-01", tz="Europe/Paris")

result = client.query_generation("FR", start=start, end=end, psr_type="B19")
print(type(result))
print(result.head())
print(result.sum())

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
FETCH_FROM = pd.Timestamp("2014-01-01", tz="UTC")

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
    """Annual-chunked fetch with retry. Returns hourly UTC Series."""
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


def fetch_prices(client, start, end):
    s = _fetch(client, lambda s,e: client.query_day_ahead_prices(COUNTRY, start=s, end=e),
               "DA prices", start, end)
    s.name = "Spot"; return s


def fetch_solar(client, start, end):
    s = _fetch(client, lambda s,e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B16"),
               "Solar B16", start, end)
    s.name = "NatMW"; return s


def fetch_wind(client, start, end):
    on  = _fetch(client, lambda s,e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B19"),
                 "Wind B19", start, end)
    off = _fetch(client, lambda s,e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B18"),
                 "Wind B18", start, end)
    if on.empty and off.empty:
        return pd.Series(dtype=float, name="WindMW")
    combined = (on.add(off, fill_value=0) if not on.empty and not off.empty
                else (off if on.empty else on))
    combined.name = "WindMW"; return combined


def load_existing():
    """Returns (df, full_refresh_needed)."""
    if not SPOT_CSV.exists():
        log.info("No CSV found — full refresh needed.")
        return pd.DataFrame(), True
    df = pd.read_csv(SPOT_CSV, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    wind_ok = "WindMW" in df.columns and df["WindMW"].sum() > 0
    if not wind_ok:
        log.info("WindMW missing or all-zero — full refresh needed.")
        return df, True
    log.info(f"Existing: {len(df):,} rows, {df['Date'].min().date()} -> {df['Date'].max().date()}")
    return df, False


def get_range(existing, full_refresh):
    end = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=12)).floor("D")
    start = FETCH_FROM if (full_refresh or existing.empty) else \
            (existing["Date"].max() + pd.Timedelta(hours=1)).floor("h")
    if start >= end:
        log.info("Already up to date.")
        return None, None
    log.info(f"Fetch range: {start.date()} -> {end.date()} ({'FULL' if full_refresh else 'incremental'})")
    return start, end


def build_rows(client, start, end):
    prices = fetch_prices(client, start, end)
    if prices.empty:
        return pd.DataFrame()
    solar = fetch_solar(client, start, end)
    wind  = fetch_wind(client, start, end)
    df = pd.DataFrame({"Spot": prices})
    df = df.join(solar if not solar.empty else pd.Series(name="NatMW",  dtype=float), how="left")
    df = df.join(wind  if not wind.empty  else pd.Series(name="WindMW", dtype=float), how="left")
    df = df.reset_index().rename(columns={"index": "Date", "utc_time": "Date"})
    if "Date" not in df.columns:
        df = df.reset_index(); df.columns = ["Date"] + list(df.columns[1:])
    df["Date"]   = pd.to_datetime(df["Date"], utc=True)
    df["Year"]   = df["Date"].dt.year
    df["Month"]  = df["Date"].dt.month
    df["Hour"]   = df["Date"].dt.hour
    df["NatMW"]  = df["NatMW"].fillna(0.0)
    df["WindMW"] = df["WindMW"].fillna(0.0)
    df = df[df["Spot"] > -500].copy()
    log.info(f"Fetched {len(df):,} rows")
    return df


def combine(existing, new_rows, full_refresh):
    if full_refresh or existing.empty:
        return new_rows
    if "WindMW" not in existing.columns:
        existing["WindMW"] = 0.0
    out = pd.concat([existing, new_rows], ignore_index=True)
    out = out.drop_duplicates(subset=["Date"], keep="last")
    return out.sort_values("Date").reset_index(drop=True)


def recompute_nat(hourly):
    h = hourly[hourly["Spot"] > 0].copy()
    h["Rev_nat"]  = h["NatMW"] * h["Spot"]
    has_wind      = h["WindMW"].sum() > 0
    if has_wind:
        h["Rev_wind"] = h["WindMW"] * h["Spot"]

    current_year   = pd.Timestamp.now().year
    hpy            = h.groupby("Year")["Spot"].count()
    min_h          = {yr: (500 if yr == current_year else 8000) for yr in hpy.index}
    complete       = [yr for yr, cnt in hpy.items() if cnt >= min_h[yr]]

    agg = {"spot":("Spot","mean"), "prod_nat":("NatMW","sum"), "rev_nat":("Rev_nat","sum"),
           "neg_h":("Spot", lambda x: (x<0).sum()), "n_hours":("Spot","count")}
    if has_wind:
        agg["prod_wind"] = ("WindMW","sum"); agg["rev_wind"] = ("Rev_wind","sum")

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
    keep = ["year","spot","cp_nat","cp_nat_pct","shape_disc",
            "cp_wind","cp_wind_pct","shape_disc_wind","neg_h","n_hours","partial"]
    ann = ann[[c for c in keep if c in ann.columns]]
    log.info(f"Nat reference: {len(ann)} years ({ann['year'].min()}-{ann['year'].max()})")
    return ann


def save(df):
    out = df.copy()
    out["Date_str"] = out["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out[["Date_str","Year","Month","Hour","Spot","NatMW","WindMW"]].rename(
        columns={"Date_str":"Date"}).to_csv(SPOT_CSV, index=False)
    log.info(f"Saved {len(out):,} rows -> {SPOT_CSV}")


def write_log(df, full_refresh, new_rows):
    now   = datetime.now(timezone.utc)
    mode  = "Full refresh (2014->yesterday)" if full_refresh else "Incremental"
    lines = [
        f"Last update : {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Mode        : {mode}",
        f"New rows    : {new_rows:,}",
        f"Total rows  : {len(df):,}",
        f"Data through: {str(df['Date'].max())[:10] if not df.empty else 'N/A'}",
        f"Columns     : Spot | NatMW (B16) | WindMW (B18+B19)",
    ]
    LOG_TXT.write_text("\n".join(lines))
    log.info("\n".join(lines))


def main():
    log.info("=" * 60)
    log.info("ENTSO-E Update v2.5")
    log.info("=" * 60)

    existing, full_refresh = load_existing()
    start, end = get_range(existing, full_refresh)

    if start is None:
        if not existing.empty:
            recompute_nat(existing).to_csv(NAT_CSV, index=False)
        write_log(existing, False, 0)
        return

    client   = _get_client()
    new_rows = build_rows(client, start, end)

    if new_rows.empty:
        log.warning("Nothing fetched.")
        write_log(existing, full_refresh, 0)
        return

    combined = combine(existing, new_rows, full_refresh)
    save(combined)
    recompute_nat(combined).to_csv(NAT_CSV, index=False)
    write_log(combined, full_refresh, len(new_rows))

    log.info("=" * 60)
    log.info("Done.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
