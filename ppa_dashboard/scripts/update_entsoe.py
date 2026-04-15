"""
update_entsoe.py — Incremental daily update
Fetches only missing hours (Spot + NatMW + WindMW + NuclearMW + GasMW + HydroMW + OtherMW
+ SolarForecastMW via A69).
Updates nat_reference.csv including cap_solar_gw / cap_wind_gw.
Called automatically every morning at 08:00 UTC via GitHub Actions.

v2.8: Added SolarForecastMW (ENTSO-E A69 Day-Ahead Generation Forecast, psr B16)
      Used by bootstrap.py for WPD-style shape discount distribution.
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


def _fetch_psr(client, psr, label, start, end):
    return _fetch(client,
                  lambda s, e: client.query_generation(COUNTRY, start=s, end=e, psr_type=psr),
                  label, start, end)


def _fetch_forecast_psr(client, psr, label, start, end):
    """Fetch Day-Ahead Generation Forecast (A69) for a given PSR type."""
    return _fetch(
        client,
        lambda s, e: client.query_generation_forecast(COUNTRY, start=s, end=e, psr_type=psr),
        label, start, end,
    )


def fetch_installed_capacity_year(client, year: int) -> dict:
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
    for col in ["WindMW", "NuclearMW", "GasMW", "HydroMW", "OtherMW", "SolarForecastMW"]:
        if col not in df.columns:
            df[col] = np.nan
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
    # DA prices
    prices = _fetch(client, lambda s, e: client.query_day_ahead_prices(COUNTRY, start=s, end=e),
                    "DA prices", start, end)
    if prices.empty:
        return pd.DataFrame()
    prices.name = "Spot"

    # Solar realised B16
    solar = _fetch_psr(client, "B16", "Solar B16 realised", start, end)
    solar.name = "NatMW"

    # Solar DA forecast A69/B16
    solar_fc = _fetch_forecast_psr(client, "B16", "Solar B16 DA forecast", start, end)
    solar_fc.name = "SolarForecastMW"

    # Wind B18+B19
    on  = _fetch_psr(client, "B19", "Wind B19", start, end)
    off = _fetch_psr(client, "B18", "Wind B18", start, end)
    if on.empty and off.empty:
        wind = pd.Series(dtype=float, name="WindMW")
    else:
        wind = on.add(off, fill_value=0) if not on.empty and not off.empty else (off if on.empty else on)
        wind.name = "WindMW"

    # Nuclear B14
    nuclear = _fetch_psr(client, "B14", "Nuclear B14", start, end)
    nuclear.name = "NuclearMW"

    # Gas B04
    gas = _fetch_psr(client, "B04", "Gas B04", start, end)
    gas.name = "GasMW"

    # Hydro B11+B12
    hydro_ror = _fetch_psr(client, "B11", "Hydro B11 RoR", start, end)
    hydro_res = _fetch_psr(client, "B12", "Hydro B12 Res", start, end)
    if hydro_ror.empty and hydro_res.empty:
        hydro = pd.Series(dtype=float, name="HydroMW")
    else:
        hydro = hydro_ror.add(hydro_res, fill_value=0) if not hydro_ror.empty and not hydro_res.empty \
                else (hydro_res if hydro_ror.empty else hydro_ror)
        hydro.name = "HydroMW"

    # Other B17+B20
    other_b17 = _fetch_psr(client, "B17", "Other B17", start, end)
    other_b20 = _fetch_psr(client, "B20", "Other B20", start, end)
    if other_b17.empty and other_b20.empty:
        other = pd.Series(dtype=float, name="OtherMW")
    else:
        other = other_b17.add(other_b20, fill_value=0) if not other_b17.empty and not other_b20.empty \
                else (other_b20 if other_b17.empty else other_b17)
        other.name = "OtherMW"

    # Assemble
    df = pd.DataFrame({"Spot": prices})
    for s in [solar, solar_fc, wind, nuclear, gas, hydro, other]:
        if not s.empty:
            df = df.join(s, how="left")
        else:
            df[s.name] = np.nan

    df = df.reset_index().rename(columns={"index": "Date", "utc_time": "Date"})
    if "Date" not in df.columns:
        df = df.reset_index()
        df.columns = ["Date"] + list(df.columns[1:])

    df["Date"]             = pd.to_datetime(df["Date"], utc=True)
    df["Year"]             = df["Date"].dt.year
    df["Month"]            = df["Date"].dt.month
    df["Hour"]             = df["Date"].dt.hour
    df["NatMW"]            = df["NatMW"].fillna(0.0)
    df["SolarForecastMW"]  = df.get("SolarForecastMW", pd.Series(dtype=float)).fillna(0.0)
    df["WindMW"]           = df["WindMW"].fillna(0.0)
    df["NuclearMW"]        = df["NuclearMW"].fillna(0.0)
    df["GasMW"]            = df["GasMW"].fillna(0.0)
    df["HydroMW"]          = df["HydroMW"].fillna(0.0)
    df["OtherMW"]          = df["OtherMW"].fillna(0.0)
    df = df[df["Spot"] > -500].copy()

    fc_coverage = (df["SolarForecastMW"] > 0).mean() * 100
    log.info(f"Fetched {len(df):,} new rows — "
             f"Solar realised: {df['NatMW'].mean():.0f} MW avg | "
             f"Solar forecast: {df['SolarForecastMW'].mean():.0f} MW avg "
             f"(coverage: {fc_coverage:.0f}%)")
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
    ann = ann.rename(columns={"Year": "year"}).dropna(subset=["cp_nat_pct"])

    if existing_nat is not None and "cap_solar_gw" in existing_nat.columns:
        cap_cols = [c for c in ["year", "cap_solar_gw", "cap_wind_gw"] if c in existing_nat.columns]
        ann = ann.merge(existing_nat[cap_cols], on="year", how="left")
    else:
        ann["cap_solar_gw"] = np.nan
        ann["cap_wind_gw"]  = np.nan

    keep = ["year", "spot", "cp_nat", "cp_nat_pct", "shape_disc",
            "cp_wind", "cp_wind_pct", "shape_disc_wind",
            "neg_h", "n_hours", "partial", "cap_solar_gw", "cap_wind_gw"]
    ann = ann[[c for c in keep if c in ann.columns]]
    log.info(f"Nat reference: {len(ann)} years ({ann['year'].min()}-{ann['year'].max()})")
    return ann


def update_capacity_current_year(client, nat_df: pd.DataFrame) -> pd.DataFrame:
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
    cols = ["Date_str", "Year", "Month", "Hour", "Spot",
            "NatMW", "SolarForecastMW", "WindMW",
            "NuclearMW", "GasMW", "HydroMW", "OtherMW"]
    cols = [c for c in cols if c in out.columns]
    out[cols].rename(columns={"Date_str": "Date"}).to_csv(SPOT_CSV, index=False)
    log.info(f"Saved {len(out):,} rows -> {SPOT_CSV}")


def write_log(df, new_rows):
    now   = datetime.now(timezone.utc)
    fc_ok = "SolarForecastMW" in df.columns and (df["SolarForecastMW"] > 0).any()
    lines = [
        f"Last update : {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Mode        : Incremental",
        f"New rows    : {new_rows:,}",
        f"Total rows  : {len(df):,}",
        f"Data through: {str(df['Date'].max())[:10] if not df.empty else 'N/A'}",
        f"Forecast    : {'SolarForecastMW available' if fc_ok else 'SolarForecastMW not yet available'}",
        f"Columns     : Spot | NatMW (B16) | SolarForecastMW (A69/B16) | WindMW (B18+B19) | "
        f"NuclearMW (B14) | GasMW (B04) | HydroMW (B11+B12) | OtherMW (B17+B20)",
    ]
    LOG_TXT.write_text("\n".join(lines))
    log.info("\n".join(lines))


def main():
    log.info("=" * 60)
    log.info("ENTSO-E Incremental Update v2.8")
    log.info("=" * 60)

    existing = load_existing()
    start, end = get_range(existing)

    existing_nat = pd.read_csv(NAT_CSV) if NAT_CSV.exists() else None

    client = _get_client()

    if start is None:
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

    for col in ["NuclearMW", "GasMW", "HydroMW", "OtherMW", "SolarForecastMW"]:
        if col not in combined.columns:
            combined[col] = np.nan

    save(combined)

    nat = recompute_nat(combined, existing_nat)
    nat = update_capacity_current_year(client, nat)
    nat.to_csv(NAT_CSV, index=False)

    write_log(combined, len(new_rows))
    log.info("=" * 60)
    log.info("Done.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
