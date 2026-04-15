"""
bootstrap.py — KAL-EL : Block Bootstrap Shape Discount Distribution
=====================================================================
Generates a robust shape discount distribution using block bootstrap
on historical hourly data (NatMW/SolarForecastMW, Spot).

Method
------
1. Build a pool of hourly (production, spot) pairs from history.
   Priority: SolarForecastMW (DA forecast) > NatMW (realised).
   Using the forecast mirrors the actual price formation mechanism:
   it is the J-1 forecast published ~10h before delivery that traders
   see when submitting bids, not the realised production.

2. If an asset load curve is available, weight production hours by the
   asset's hourly profile (normalised to 1), so the shape discount
   reflects this specific asset's exposure, not the national average.

3. Draw N_SIM synthetic years by sampling BLOCK_WEEKS-week blocks with
   replacement. Block sampling preserves intra-week correlations
   (e.g. sustained sunny/cloudy periods, weekday patterns).

4. For each synthetic year compute:
     Captured price = sum(Prod × Spot) / sum(Prod)   [production-hours only]
     Baseload       = mean(Spot)                       [production-hours only]
     Shape discount = 1 − Captured / Baseload

5. Return the full distribution over N_SIM years + key percentiles.

Why this is better than np.percentile on 8-10 annual observations
------------------------------------------------------------------
- ~88 000 hourly observations vs 8 annual averages
- Block structure preserves autocorrelation
- 10 000 synthetic years → smooth percentile estimates
- DA forecast used as production proxy → captures price formation mechanism
- Falls back to realised NatMW when forecast not available (pre-2015)

Limitation vs full WPD model
-----------------------------
We resample historical price patterns; we do not model future ones.
The distribution therefore does not capture the ongoing trend of
increasing cannibalization from growing solar fleet.
→ Use the regression projection in tab 1 for trend adjustment,
  and use this bootstrap for within-year variance estimation.

Integration in tab_pricer.py
-----------------------------
    from bootstrap import run_bootstrap, percentile_from_dist
    dist   = run_bootstrap(hourly, asset_raw=asset_raw, prod_col="NatMW")
    sd_p74 = percentile_from_dist(dist, 74)
"""

import numpy as np
import pandas as pd
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────
N_SIM        = 10_000   # synthetic years — ~3s on Streamlit Cloud
BLOCK_WEEKS  = 2        # 2 weeks = 336 hours per block
HOURS_YEAR   = 8_760
RANDOM_SEED  = 42


# ── Core simulation ───────────────────────────────────────────────────────────

def run_bootstrap(
    hourly: pd.DataFrame,
    asset_raw: Optional[pd.DataFrame] = None,
    prod_col: str = "NatMW",
    n_sim: int = N_SIM,
    block_weeks: int = BLOCK_WEEKS,
    exclude_2022: bool = False,
    random_seed: int = RANDOM_SEED,
) -> dict:
    """
    Run block bootstrap and return shape discount distribution.

    Parameters
    ----------
    hourly      : hourly_spot DataFrame — must contain Date, Spot,
                  and either SolarForecastMW or prod_col
    asset_raw   : asset load curve DataFrame (Date, Prod_MWh)
                  If provided, weights are derived from the asset profile
    prod_col    : fallback production column ('NatMW' or 'WindMW')
    n_sim       : number of synthetic years
    block_weeks : block size in weeks
    exclude_2022: drop 2022 from sampling pool
    random_seed : reproducibility seed

    Returns
    -------
    dict:
        shape_disc_dist  : np.array(n_sim)  — distribution of shape discounts
        cp_pct_dist      : np.array(n_sim)  — distribution of capture rates
        percentiles      : dict {1..100: float}
        prod_source      : str — which production column was used
        fc_coverage_pct  : float — % hours where SolarForecastMW > 0
        n_hours_pool     : int
        n_blocks         : int
        block_size_h     : int
        years_used       : list[int]
        n_sim            : int — actual simulations completed
        method           : str — description for display
    """
    rng = np.random.default_rng(random_seed)

    # ── 1. Prepare hourly pool ────────────────────────────────────────────────
    h = hourly.copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h = h.sort_values("Date").reset_index(drop=True)

    if exclude_2022:
        h = h[h["Date"].dt.year != 2022].reset_index(drop=True)

    # Choose production column: prefer SolarForecastMW if available and populated
    has_forecast = (
        "SolarForecastMW" in h.columns
        and (h["SolarForecastMW"] > 0).sum() > len(h) * 0.1  # at least 10% coverage
    )

    if has_forecast:
        prod_source  = "SolarForecastMW"
        fc_coverage  = (h["SolarForecastMW"] > 0).mean() * 100
        # For hours where forecast is 0 but realised > 0, fall back to realised
        # (covers pre-2015 and data gaps)
        if prod_col in h.columns:
            h["_prod"] = np.where(
                h["SolarForecastMW"] > 0,
                h["SolarForecastMW"],
                h[prod_col],
            )
        else:
            h["_prod"] = h["SolarForecastMW"]
    else:
        prod_source = prod_col
        fc_coverage = 0.0
        h["_prod"]  = h[prod_col] if prod_col in h.columns else 0.0

    # Filter to production hours (daytime for solar)
    h = h[h["_prod"] > 0].copy()

    # ── 2. Apply asset weight profile if available ────────────────────────────
    # Normalise asset production to a [0,1] weight per hour-of-day × month
    # so that the shape discount reflects this asset's specific profile
    if asset_raw is not None and len(asset_raw) > 100:
        a = asset_raw.copy()
        a["Date"]  = pd.to_datetime(a["Date"])
        a["Hour"]  = a["Date"].dt.hour
        a["Month"] = a["Date"].dt.month
        a = a[a["Prod_MWh"] > 0]

        if len(a) > 50:
            # Build normalised weight per (Month, Hour)
            weight_profile = (
                a.groupby(["Month", "Hour"])["Prod_MWh"].mean()
                .reset_index()
                .rename(columns={"Prod_MWh": "_weight"})
            )
            max_w = weight_profile["_weight"].max()
            if max_w > 0:
                weight_profile["_weight"] /= max_w

            h["Month"] = h["Date"].dt.month
            h["Hour"]  = h["Date"].dt.hour
            h = h.merge(weight_profile, on=["Month", "Hour"], how="left")
            h["_weight"] = h["_weight"].fillna(0.0)

            # Apply weight: effective production = national/forecast × asset weight
            h["_prod_eff"] = h["_prod"] * h["_weight"]
            h = h[h["_prod_eff"] > 0].copy()
            h["_prod"] = h["_prod_eff"]
            asset_profile_applied = True
        else:
            asset_profile_applied = False
    else:
        asset_profile_applied = False

    spot_arr  = h["Spot"].values.astype(np.float64)
    prod_arr  = h["_prod"].values.astype(np.float64)
    n_hours   = len(h)
    years_used = sorted(h["Date"].dt.year.unique().tolist())

    # ── 3. Build blocks ───────────────────────────────────────────────────────
    block_size = block_weeks * 7 * 24

    # Ensure we have enough blocks; fall back to 1-week blocks if needed
    if n_hours < block_size * 10:
        block_size = 7 * 24
    n_blocks = n_hours // block_size

    if n_blocks < 5:
        # Last resort: use all data as one pool (iid sampling)
        block_size = 1
        n_blocks   = n_hours

    # Slice data into contiguous blocks
    idx_end  = n_blocks * block_size
    prod_mat = prod_arr[:idx_end].reshape(n_blocks, block_size)
    spot_mat = spot_arr[:idx_end].reshape(n_blocks, block_size)

    # ── 4. Simulate ───────────────────────────────────────────────────────────
    blocks_per_year = max(1, HOURS_YEAR // block_size)

    shape_disc_arr = np.empty(n_sim)
    cp_pct_arr     = np.empty(n_sim)

    for i in range(n_sim):
        idx      = rng.integers(0, n_blocks, size=blocks_per_year)
        sim_prod = prod_mat[idx].ravel()[:HOURS_YEAR]
        sim_spot = spot_mat[idx].ravel()[:HOURS_YEAR]

        mask = sim_prod > 0
        if mask.sum() < 50:
            shape_disc_arr[i] = np.nan
            cp_pct_arr[i]     = np.nan
            continue

        total_rev  = (sim_prod[mask] * sim_spot[mask]).sum()
        total_prod = sim_prod[mask].sum()
        baseload   = sim_spot[mask].mean()

        if total_prod == 0 or baseload == 0:
            shape_disc_arr[i] = np.nan
            cp_pct_arr[i]     = np.nan
            continue

        cp_pct     = (total_rev / total_prod) / baseload
        shape_disc = 1.0 - cp_pct

        shape_disc_arr[i] = shape_disc
        cp_pct_arr[i]     = cp_pct

    # Clean NaN
    valid            = ~np.isnan(shape_disc_arr)
    shape_disc_dist  = shape_disc_arr[valid]
    cp_pct_dist      = cp_pct_arr[valid]

    # ── 5. Percentile table ───────────────────────────────────────────────────
    percentiles = {p: float(np.percentile(shape_disc_dist, p))
                   for p in range(1, 101)}

    method = (
        f"Block bootstrap — {block_weeks}w blocks — "
        f"{len(shape_disc_dist):,} synthetic years — "
        f"production: {prod_source}"
        + (" + asset profile" if asset_profile_applied else " (national profile)")
        + (f" — DA forecast coverage: {fc_coverage:.0f}%" if has_forecast else "")
    )

    return {
        "shape_disc_dist": shape_disc_dist,
        "cp_pct_dist":     cp_pct_dist,
        "percentiles":     percentiles,
        "prod_source":     prod_source,
        "fc_coverage_pct": fc_coverage,
        "n_hours_pool":    n_hours,
        "n_blocks":        n_blocks,
        "block_size_h":    block_size,
        "years_used":      years_used,
        "n_sim":           int(len(shape_disc_dist)),
        "method":          method,
        "asset_profile":   asset_profile_applied,
        "exclude_2022":    exclude_2022,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def percentile_from_dist(dist: dict, p: int) -> float:
    """Get shape discount at percentile p from bootstrap distribution."""
    return dist["percentiles"][p]


def build_percentile_table(dist: dict, key_pcts=None) -> pd.DataFrame:
    """Summary table of shape discount / capture rate at key percentiles."""
    if key_pcts is None:
        key_pcts = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50,
                    55, 60, 65, 70, 74, 75, 80, 85, 90, 95, 100]
    rows = []
    for p in key_pcts:
        sd = dist["percentiles"][p]
        rows.append({
            "Percentile":    f"P{p}",
            "Shape Discount": f"{sd * 100:.1f}%",
            "Capture Rate":   f"{(1 - sd) * 100:.1f}%",
        })
    return pd.DataFrame(rows)
