"""
update_entsoe.py v2.7
Incremental by default. Auto full refresh if WindMW missing or all-zero.
Added: balancing_prices.csv with DA, Imbalance, aFRR, mFRR prices.
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
BAL_CSV    = DATA_DIR / "balancing_prices.csv"
NAT_CSV    = DATA_DIR / "nat_reference.csv"
LOG_TXT    = DATA_DIR / "last_update.txt"
COUNTRY    = "FR"
FETCH_FROM = pd.Timestamp("2014-01-01", tz="UTC")
BAL_FROM   = pd.Timestamp("2018-01-01", tz="UTC")  # balancing data sparse before 2018

API_KEY = os.environ.get("ENTSOE_API_KEY", "")
if not API_KEY:
    log.error("ENTSOE_API_KEY not set.")
    sys.exit(1)


# ── Client ────────────────────────────────────────────────────────────────────

def _get_client():
    try:
        from entsoe import EntsoePandasClient
        return EntsoePandasClient(api_key=API_KEY)
    except ImportError:
        log.error("entsoe-py not installed.")
        raise


# ── Generic chunked fetcher ───────────────────────────────────────────────────

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


# ── Spot fetchers ─────────────────────────────────────────────────────────────

def fetch_prices(client, start, end):
    s = _fetch(client, lambda s, e: client.query_day_ahead_prices(COUNTRY, start=s, end=e),
               "DA prices", start, end)
    s.name = "Spot"; return s


def fetch_solar(client, start, end):
    s = _fetch(client, lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B16"),
               "Solar B16", start, end)
    s.name = "NatMW"; return s


def fetch_wind(client, start, end):
    on  = _fetch(client, lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B19"),
                 "Wind B19", start, end)
    off = _fetch(client, lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type="B18"),
                 "Wind B18", start, end)
    if on.empty and off.empty:
        return pd.Series(dtype=float, name="WindMW")
    if on.empty: combined = off
    elif off.empty: combined = on
    else: combined = on.add(off, fill_value=0)
    combined.name = "WindMW"; return combined


# ── Balancing fetchers ────────────────────────────────────────────────────────

def fetch_imbalance(client, start, end):
    """Fetch imbalance prices — positive and negative."""
    try:
        df = _fetch(client,
                    lambda s, e: client.query_imbalance_prices(COUNTRY, start=s, end=e),
                    "Imbalance prices", start, end)
        if isinstance(df, pd.Series):
            return pd.DataFrame({"Imb_Pos": df, "Imb_Neg": df})
        # DataFrame with multiple columns
        pos = df.iloc[:, 0] if len(df.columns) >= 1 else pd.Series(dtype=float)
        neg = df.iloc[:, 1] if len(df.columns) >= 2 else pos
        return pd.DataFrame({"Imb_Pos": pos, "Imb_Neg": neg})
    except Exception as e:
        log.warning(f"  Imbalance fetch failed: {e}")
        return pd.DataFrame({"Imb_Pos": pd.Series(dtype=float),
                             "Imb_Neg": pd.Series(dtype=float)})


def fetch_balancing_energy(client, start, end, psr_type, label):
    """Fetch activated balancing energy prices (aFRR=A96, mFRR=A97)."""
    try:
        s = _fetch(client,
                   lambda s, e: client.query_activated_balancing_energy_prices(
                       COUNTRY, start=s, end=e, business_type=psr_type),
                   label, start, end)
        return s
    except Exception as e:
        log.warning(f"  {label} fetch failed: {e}")
        return pd.Series(dtype=float)


def build_balancing_rows(client, start, end) -> pd.DataFrame:
    """Build hourly balancing prices DataFrame."""
    # DA prices (reference)
    da = fetch_prices(client, start, end)
    if da.empty:
        return pd.DataFrame()

    df = pd.DataFrame({"DA": da})

    # Imbalance
    imb = fetch_imbalance(client, start, end)
    if not imb.empty:
        df = df.join(imb, how="left")
    else:
        df["Imb_Pos"] = np.nan
        df["Imb_Neg"] = np.nan

    # aFRR
    afrr = fetch_balancing_energy(client, start, end, "A96", "aFRR")
    df["aFRR"] = afrr if not afrr.empty else np.nan

    # mFRR
    mfrr = fetch_balancing_energy(client, start, end, "A97", "mFRR")
    df["mFRR"] = mfrr if not mfrr.empty else np.nan

    df = df.reset_index().rename(columns={"index": "Date", "utc_time": "Date"})
    if "Date" not in df.columns:
        df = df.reset_index()
        df.columns = ["Date"] + list(df.columns[1:])

    df["Date"]  = pd.to_datetime(df["Date"], utc=True)
    df["Year"]  = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Hour"]  = df["Date"].dt.hour
    df = df[df["DA"] > -500].copy()

    log.info(f"Balancing: {len(df):,} rows — aFRR: {df['aFRR'].notna().sum():,}, "
             f"mFRR: {df['mFRR'].notna().sum():,}")
    return df


# ── Spot: load / range / build / merge ───────────────────────────────────────

def load_existing_spot():
    if not SPOT_CSV.exists():
        log.info("No spot CSV — full refresh needed.")
        return pd.DataFrame(), True
    df = pd.read_csv(SPOT_CSV, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    wind_ok = "WindMW" in df.columns and df["WindMW"].sum() > 0
    if not wind_ok:
        log.info("WindMW missing — full refresh needed.")
        return df, True
    log.info(f"Spot existing: {len(df):,} rows, "
             f"{df['Date'].min().date()} -> {df['Date'].max().date()}")
    return df, False


def load_existing_bal():
    if not BAL_CSV.exists():
        log.info("No balancing CSV — full fetch from 2018.")
        return pd.DataFrame(), True
    df = pd.read_csv(BAL_CSV, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    log.info(f"Balancing existing: {len(df):,} rows, "
             f"{df['Date'].min().date()} -> {df['Date'].max().date()}")
    return df, False


def get_range(existing, full_refresh, fetch_from):
    end = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=12)).floor("D")
    if full_refresh or existing.empty:
        start = fetch_from
    else:
        start = (existing["Date"].max() + pd.Timedelta(hours=1)).floor("h")
    if start >= end:
        return None, None
    log.info(f"Fetch range: {start.date()} -> {end.date()} "
             f"({'FULL' if full_refresh else 'incremental'})")
    return start, end


def build_spot_rows(client, start, end):
    prices = fetch_prices(client, start, end)
    if prices.empty: return pd.DataFrame()
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
    log.info(f"Spot: {len(df):,} rows")
    return df


def merge_df(existing, new_rows, full_refresh, wind_col=True):
    if full_refresh or existing.empty:
        return new_rows
    if wind_col and "WindMW" not in existing.columns:
        existing["WindMW"] = 0.0
    out = pd.concat([existing, new_rows], ignore_index=True)
    out = out.drop_duplicates(subset=["Date"], keep="last")
    return out.sort_values("Date").reset_index(drop=True)


# ── National reference ────────────────────────────────────────────────────────

def recompute_nat(hourly):
    h = hourly[hourly["Spot"] > 0].copy()
    h["Rev_nat"]  = h["NatMW"] * h["Spot"]
    has_wind      = h["WindMW"].sum() > 0
    if has_wind: h["Rev_wind"] = h["WindMW"] * h["Spot"]
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
    return ann


# ── Save ─────────────────────────────────────────────────────────────────────

def save_spot(df):
    out = df.copy()
    out["Date_str"] = out["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out[["Date_str","Year","Month","Hour","Spot","NatMW","WindMW"]].rename(
        columns={"Date_str":"Date"}).to_csv(SPOT_CSV, index=False)
    log.info(f"Saved spot: {len(out):,} rows")


def save_bal(df):
    out = df.copy()
    out["Date_str"] = out["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["Date_str","Year","Month","Hour","DA","Imb_Pos","Imb_Neg","aFRR","mFRR"]
    cols = [c for c in cols if c in out.columns]
    out[cols].rename(columns={"Date_str":"Date"}).to_csv(BAL_CSV, index=False)
    log.info(f"Saved balancing: {len(out):,} rows")


def write_log(spot_df, bal_df):
    now = datetime.now(timezone.utc)
    lines = [
        f"Last update : {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Spot rows   : {len(spot_df):,}",
        f"Spot through: {str(spot_df['Date'].max())[:10] if not spot_df.empty else 'N/A'}",
        f"Bal rows    : {len(bal_df):,}",
        f"Bal through : {str(bal_df['Date'].max())[:10] if not bal_df.empty else 'N/A'}",
        f"Columns     : Spot|NatMW|WindMW | DA|Imb_Pos|Imb_Neg|aFRR|mFRR",
    ]
    LOG_TXT.write_text("\n".join(lines))
    log.info("\n".join(lines))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("ENTSO-E Update v2.7")
    log.info("=" * 60)

    client = _get_client()

    # ── Spot ──
    existing_spot, full_spot = load_existing_spot()
    start_spot, end_spot     = get_range(existing_spot, full_spot, FETCH_FROM)

    if start_spot is not None:
        new_spot = build_spot_rows(client, start_spot, end_spot)
        if not new_spot.empty:
            combined_spot = merge_df(existing_spot, new_spot, full_spot)
            save_spot(combined_spot)
            recompute_nat(combined_spot).to_csv(NAT_CSV, index=False)
        else:
            combined_spot = existing_spot
    else:
        combined_spot = existing_spot
        if not combined_spot.empty:
            recompute_nat(combined_spot).to_csv(NAT_CSV, index=False)

    # ── Balancing ──
    existing_bal, full_bal = load_existing_bal()
    start_bal, end_bal     = get_range(existing_bal, full_bal, BAL_FROM)

    if start_bal is not None:
        new_bal = build_balancing_rows(client, start_bal, end_bal)
        if not new_bal.empty:
            combined_bal = merge_df(existing_bal, new_bal, full_bal, wind_col=False)
            save_bal(combined_bal)
        else:
            combined_bal = existing_bal
    else:
        combined_bal = existing_bal

    write_log(combined_spot, combined_bal if not combined_bal.empty else pd.DataFrame())

    log.info("=" * 60)
    log.info("Done.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
