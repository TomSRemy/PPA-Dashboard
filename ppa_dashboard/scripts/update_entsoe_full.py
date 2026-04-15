"""
update_entsoe_full.py — Full historical refresh
Fetches everything from 2014-01-01 to yesterday:
  - DA prices (Spot)
  - Solar generation B16 (NatMW)
  - Wind generation B18+B19 (WindMW)
  - Nuclear B14 (NuclearMW)
  - Gas B04 (GasMW)
  - Hydro B11+B12 (HydroMW)
  - Other B17+B20 (OtherMW)
  - Installed capacity B09 Wind + Solar per year -> saved in nat_reference.csv
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


def _fetch_psr(client, psr, label, start, end):
    return _fetch(client,
                  lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type=psr),
                  label, start, end)


def fetch_prices(client, start, end):
    s = _fetch(client, lambda s, e: client.query_day_ahead_prices(COUNTRY, start=s, end=e),
               "DA prices", start, end)
    s.name = "Spot"
    return s


def fetch_solar(client, start, end):
    s = _fetch_psr(client, "B16", "Solar B16", start, end)
    s.name = "NatMW"
    return s


def fetch_wind(client, start, end):
    on  = _fetch_psr(client, "B19", "Wind B19", start, end)
    off = _fetch_psr(client, "B18", "Wind B18", start, end)
    if on.empty and off.empty:
        log.warning("Wind B18+B19 both empty — WindMW will be 0")
        return pd.Series(dtype=float, name="WindMW")
    combined = on.add(off, fill_value=0) if not on.empty and not off.empty else (off if on.empty else on)
    combined.name = "WindMW"
    log.info(f"  Wind combined: {len(combined)} rows, sum={combined.sum():.0f} MW")
    return combined


def fetch_nuclear(client, start, end):
    s = _fetch_psr(client, "B14", "Nuclear B14", start, end)
    s.name = "NuclearMW"
    return s


def fetch_gas(client, start, end):
    s = _fetch_psr(client, "B04", "Gas B04", start, end)
    s.name = "GasMW"
    return s


def fetch_hydro(client, start, end):
    ror = _fetch_psr(client, "B11", "Hydro B11 RoR", start, end)
    res = _fetch_psr(client, "B12", "Hydro B12 Res", start, end)
    if ror.empty and res.empty:
        return pd.Series(dtype=float, name="HydroMW")
    combined = ror.add(res, fill_value=0) if not ror.empty and not res.empty else (res if ror.empty else ror)
    combined.name = "HydroMW"
    return combined


def fetch_other(client, start, end):
    b17 = _fetch_psr(client, "B17", "Other B17 Waste", start, end)
    b20 = _fetch_psr(client, "B20", "Other B20", start, end)
    if b17.empty and b20.empty:
        return pd.Series(dtype=float, name="OtherMW")
    combined = b17.add(b20, fill_value=0) if not b17.empty and not b20.empty else (b20 if b17.empty else b17)
    combined.name = "OtherMW"
    return combined


def fetch_installed_capacity(client) -> pd.DataFrame:
    rows = []
    for year in range(2014, pd.Timestamp.now().year + 1):
        start = pd.Timestamp(f"{year}-01-01", tz="UTC")
        end   = pd.Timestamp(f"{year}-12-31", tz="UTC")
        row   = {"year": year, "cap_solar_gw": np.nan, "cap_wind_gw": np.nan}
        wind_vals = []
        for psr, key in [("B16", "cap_solar_gw"), ("B18", "cap_wind_off_gw"),
                         ("B19", "cap_wind_on_gw")]:
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
                if key == "cap_solar_gw":
                    row["cap_solar_gw"] = val
                else:
                    wind_vals.append(val)
            except Exception as e:
                log.warning(f"  Installed cap {psr} {year}: {e}")
        total_wind = sum(v for v in wind_vals if not np.isnan(v))
        row["cap_wind_gw"] = total_wind if total_wind > 0 else np.nan
        rows.append(row)
        log.info(f"  Installed cap {year}: Solar={row.get('cap_solar_gw',np.nan):.1f}GW")
    return pd.DataFrame(rows)


def build_rows(client, start, end):
    prices  = fetch_prices(client, start, end)
    if prices.empty:
        return pd.DataFrame()
    solar   = fetch_solar(client, start, end)
    wind    = fetch_wind(client, start, end)
    nuclear = fetch_nuclear(client, start, end)
    gas     = fetch_gas(client, start, end)
    hydro   = fetch_hydro(client, start, end)
    other   = fetch_other(client, start, end)

    df = pd.DataFrame({"Spot": prices})
    for s in [solar, wind, nuclear, gas, hydro, other]:
        if not s.empty:
            df = df.join(s, how="left")
        else:
            df[s.name] = np.nan

    df = df.reset_index().rename(columns={"index":"Date","utc_time":"Date"})
    if "Date" not in df.columns:
        df = df.reset_index(); df.columns = ["Date"] + list(df.columns[1:])

    df["Date"]      = pd.to_datetime(df["Date"], utc=True)
    df["Year"]      = df["Date"].dt.year
    df["Month"]     = df["Date"].dt.month
    df["Hour"]      = df["Date"].dt.hour
    df["NatMW"]     = df["NatMW"].fillna(0.0)
    df["WindMW"]    = df["WindMW"].fillna(0.0)
    df["NuclearMW"] = df["NuclearMW"].fillna(0.0)
    df["GasMW"]     = df["GasMW"].fillna(0.0)
    df["HydroMW"]   = df["HydroMW"].fillna(0.0)
    df["OtherMW"]   = df["OtherMW"].fillna(0.0)
    df = df[df["Spot"] > -500].copy()

    log.info(f"Fetched {len(df):,} rows — Nuclear avg: {df['NuclearMW'].mean():.0f} MW | "
             f"Solar avg: {df['NatMW'].mean():.0f} MW | WindMW sum: {df['WindMW'].sum():.0f}")
    return df


def recompute_nat(hourly, cap_df=None):
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

    if cap_df is not None and len(cap_df) > 0:
        ann = ann.merge(cap_df[["year","cap_solar_gw","cap_wind_gw"]], on="year", how="left")
    else:
        ann["cap_solar_gw"] = np.nan
        ann["cap_wind_gw"]  = np.nan

    keep = ["year","spot","cp_nat","cp_nat_pct","shape_disc",
            "cp_wind","cp_wind_pct","shape_disc_wind",
            "neg_h","n_hours","partial","cap_solar_gw","cap_wind_gw"]
    ann = ann[[c for c in keep if c in ann.columns]]
    log.info(f"Nat reference: {len(ann)} years ({ann['year'].min()}-{ann['year'].max()})")
    return ann


def save(df):
    out = df.copy()
    out["Date_str"] = out["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["Date_str","Year","Month","Hour","Spot","NatMW","WindMW",
            "NuclearMW","GasMW","HydroMW","OtherMW"]
    cols = [c for c in cols if c in out.columns]
    out[cols].rename(columns={"Date_str":"Date"}).to_csv(SPOT_CSV, index=False)
    log.info(f"Saved {len(out):,} rows -> {SPOT_CSV}")


def write_log(df):
    now   = datetime.now(timezone.utc)
    lines = [
        f"Last update : {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Mode        : Full refresh (2014 -> yesterday)",
        f"Total rows  : {len(df):,}",
        f"Data through: {str(df['Date'].max())[:10] if not df.empty else 'N/A'}",
        f"WindMW sum  : {df['WindMW'].sum():.0f} MW-hours",
        f"Columns     : Spot | NatMW (B16) | WindMW (B18+B19) | NuclearMW (B14) | GasMW (B04) | HydroMW (B11+B12) | OtherMW (B17+B20)",
    ]
    LOG_TXT.write_text("\n".join(lines))
    log.info("\n".join(lines))


def main():
    log.info("="*60)
    log.info("ENTSO-E Full Refresh — 2014 -> yesterday")
    log.info("="*60)

    end    = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=12)).floor("D")
    client = _get_client()

    df = build_rows(client, FETCH_FROM, end)
    if df.empty:
        log.error("No data fetched — aborting.")
        sys.exit(1)
    save(df)

    log.info("Fetching installed generation capacity...")
    try:
        cap_df = fetch_installed_capacity(client)
        log.info(f"Capacity data: {len(cap_df)} years")
    except Exception as e:
        log.warning(f"Installed capacity fetch failed: {e} — continuing without")
        cap_df = None

    recompute_nat(df, cap_df).to_csv(NAT_CSV, index=False)
    write_log(df)

    log.info("="*60)
    log.info("Done.")
    log.info("="*60)


if __name__ == "__main__":
    main()
