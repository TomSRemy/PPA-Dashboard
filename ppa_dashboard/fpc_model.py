"""
fpc_model.py — KAL-EL : Forward-Looking FPC Monte Carlo Engine
==============================================================
Causal flow: Solar Capacity → SolarMW → Hourly Prices → Capture Price → Shape Discount → P&L

Key design decisions:
- Shape discount is an OUTPUT, not an input
- Hourly prices simulated first, then capture price derived
- Forward anchoring: simulated annual avg = forward input (absence of arbitrage)
- baseload = mean of ALL simulated hours (not just production hours)
- capture_price = production-weighted average price
- shape_discount = 1 - capture_price / baseload
- For "Both": identical simulated price paths, two separate capture prices
- Block bootstrap on residuals (168h blocks), not Gaussian

Defensive: all functions return (result, error_message) tuples.
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_OBS_FOR_FIT    = 5_000    # minimum hourly observations to fit OLS
MIN_R2_WARNING     = 0.20     # warn if R² below this
MIN_ASSET_HOURS    = 2_000    # minimum asset hours for profile
BLOCK_SIZE         = 168      # 7 days × 24h
N_BLOCKS_PER_YEAR  = 52
HOURS_YEAR         = 8_760
HOURS_BLOCK_YEAR   = N_BLOCKS_PER_YEAR * BLOCK_SIZE   # 8736

# PPE3 reference trajectory (Solar FR, GW installed)
PPE3_TRAJECTORY = {
    2020: 13.0,
    2021: 15.0,
    2022: 17.0,
    2023: 20.0,
    2024: 24.0,
    2025: 27.0,
    2030: 48.0,
    2035: 67.5,
}

CAPACITY_SCENARIOS = {
    "Central (PPE3)":      {2030: 48.0, 2035: 67.5},
    "Conservative":        {2030: 40.0, 2035: 55.0},
    "Accelerated":         {2028: 48.0, 2032: 67.5},
    "Custom":              None,   # user-defined
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CAPACITY TRAJECTORY
# ═══════════════════════════════════════════════════════════════════════════════

def build_capacity_trajectory(
    current_cap_gw: float,
    current_year: int,
    tenor_years: list,
    scenario: str = "Central (PPE3)",
    custom_target_gw: float = 48.0,
    custom_target_year: int = 2030,
) -> Tuple[Dict[int, float], Optional[str]]:
    """
    Build capacity trajectory for tenor years.

    Returns
    -------
    (capacity_by_year, error_message)
    capacity_by_year : {year: cap_gw}
    """
    try:
        # Build control points: current + scenario targets
        control = {current_year: current_cap_gw}

        if scenario == "Custom":
            control[custom_target_year] = custom_target_gw
        elif scenario in CAPACITY_SCENARIOS and CAPACITY_SCENARIOS[scenario]:
            control.update(CAPACITY_SCENARIOS[scenario])
        else:
            # Central PPE3
            control.update({2030: 48.0, 2035: 67.5})

        # Interpolate linearly between control points for each tenor year
        ctrl_years = sorted(control.keys())
        ctrl_vals  = [control[y] for y in ctrl_years]

        result = {}
        for yr in tenor_years:
            cap = float(np.interp(yr, ctrl_years, ctrl_vals))
            cap = max(current_cap_gw, cap)   # never below current
            result[yr] = round(cap, 2)

        return result, None

    except Exception as e:
        return {yr: current_cap_gw for yr in tenor_years}, str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. OLS PRICE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

def fit_price_model(
    hourly: pd.DataFrame,
    exclude_2022: bool = False,
    prod_col: str = "NatMW",
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Fit OLS price model on historical hourly data.

    Model:
        Spot_h = alpha
               + beta_solar × SolarMW_h
               + sum_k(gamma_k × I(Hour=k))     k=1..23 (ref=0)
               + sum_m(delta_m × I(Month=m))    m=2..12 (ref=1)
               + epsilon_h

    Parameters
    ----------
    hourly     : DataFrame with Date, Spot, NatMW (or prod_col), Hour, Month, Year
    exclude_2022: exclude 2022 from fit
    prod_col   : solar production column

    Returns
    -------
    (model_dict, error_message)
    """
    try:
        h = hourly.copy()
        h["Date"] = pd.to_datetime(h["Date"])

        # Filter
        if exclude_2022:
            h = h[h["Year"] != 2022]

        # Drop missing / extreme spots
        h = h.dropna(subset=["Spot", prod_col])
        h = h[h["Spot"].between(-100, 800)]    # physical bounds
        h = h[h[prod_col] >= 0]

        if len(h) < MIN_OBS_FOR_FIT:
            return None, (
                f"Not enough observations to fit model: {len(h):,} rows "
                f"(minimum required: {MIN_OBS_FOR_FIT:,}). "
                f"Check that hourly_spot.csv contains sufficient data."
            )

        # Build design matrix manually (no sklearn dependency)
        n = len(h)
        solar = h[prod_col].values.astype(np.float64)
        hours  = h["Hour"].values.astype(int)
        months = h["Month"].values.astype(int)
        spot   = h["Spot"].values.astype(np.float64)

        # Features: intercept + solar + 23 hour dummies + 11 month dummies
        # hour ref = 0, month ref = 1
        n_feat = 1 + 1 + 23 + 11   # = 36
        X = np.zeros((n, n_feat), dtype=np.float64)

        X[:, 0] = 1.0           # intercept
        X[:, 1] = solar         # solar MW

        for k in range(1, 24):  # hour dummies (ref=0)
            X[:, 1 + k] = (hours == k).astype(float)

        for m in range(2, 13):  # month dummies (ref=1)
            X[:, 24 + (m - 2)] = (months == m).astype(float)

        # OLS: (X'X)^-1 X'y — use lstsq for numerical stability
        coeffs, residuals_ss, rank, sv = np.linalg.lstsq(X, spot, rcond=None)

        fitted    = X @ coeffs
        residuals = spot - fitted

        ss_tot = np.sum((spot - spot.mean()) ** 2)
        ss_res = np.sum(residuals ** 2)
        r2     = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        rmse   = float(np.sqrt(np.mean(residuals ** 2)))

        alpha      = float(coeffs[0])
        beta_solar = float(coeffs[1])
        gamma      = coeffs[2:25].tolist()    # 23 hour dummies
        delta      = coeffs[25:36].tolist()   # 11 month dummies

        # Full hour and month coefficients (including reference=0)
        gamma_full = [0.0] + gamma             # index 0..23
        delta_full = [0.0] + delta             # index 0..11 (month-1)

        warning = None
        if r2 < MIN_R2_WARNING:
            warning = (
                f"Model R² = {r2:.2f} is low. "
                f"Predictions may be unreliable. "
                f"Consider using more historical data or checking data quality."
            )

        # Store residuals with their index for block bootstrap
        resid_series = pd.Series(residuals, index=h.index)

        # Monthly fitted vs actual for validation chart
        h2 = h.copy()
        h2["_fitted"]   = fitted
        h2["_residual"] = residuals
        monthly_check = h2.groupby(["Year", "Month"]).agg(
            actual=("Spot", "mean"),
            fitted=("_fitted", "mean"),
        ).reset_index()

        return {
            "alpha":         alpha,
            "beta_solar":    beta_solar,
            "gamma_full":    gamma_full,    # list(24): index = hour
            "delta_full":    delta_full,    # list(12): index = month-1
            "r2":            float(r2),
            "rmse":          rmse,
            "n_obs":         n,
            "residuals":     residuals,     # np.array — used for bootstrap
            "fitted":        fitted,
            "monthly_check": monthly_check,
            "exclude_2022":  exclude_2022,
            "prod_col":      prod_col,
            "warning":       warning,
        }, None

    except Exception as e:
        return None, f"Model fitting failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PRODUCTION PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

def build_national_profile(
    hourly: pd.DataFrame,
    prod_col: str = "NatMW",
    exclude_2022: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Build national production profile: mean MW by (Month, Hour).

    Returns
    -------
    (profile_288, error_message)
    profile_288 : np.array(12, 24) — profile[month-1, hour]
    """
    try:
        h = hourly.copy()
        if exclude_2022:
            h = h[h["Year"] != 2022]

        h = h[h[prod_col] > 0].copy()

        if len(h) < 1000:
            return None, f"Not enough production hours in {prod_col} for profile."

        profile = (
            h.groupby(["Month", "Hour"])[prod_col]
            .mean()
            .unstack("Hour")
            .reindex(index=range(1, 13), columns=range(0, 24), fill_value=0.0)
        )
        return profile.values, None   # shape (12, 24)

    except Exception as e:
        return None, f"National profile build failed: {e}"


def build_asset_profile(
    asset_raw: Optional[pd.DataFrame],
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Build asset production profile: mean MWh/h by (Month, Hour).

    Returns
    -------
    (profile_288, error_message)
    profile_288 : np.array(12, 24)
    """
    if asset_raw is None or len(asset_raw) < MIN_ASSET_HOURS:
        return None, (
            f"Asset profile not available or insufficient "
            f"(minimum {MIN_ASSET_HOURS:,} hours required, "
            f"got {len(asset_raw) if asset_raw is not None else 0:,})."
        )

    try:
        a = asset_raw.copy()
        a["Date"]  = pd.to_datetime(a["Date"])
        a["Month"] = a["Date"].dt.month
        a["Hour"]  = a["Date"].dt.hour
        a = a[a["Prod_MWh"] > 0]

        if len(a) < MIN_ASSET_HOURS:
            return None, (
                f"Asset has {len(a):,} production hours, "
                f"minimum required: {MIN_ASSET_HOURS:,}."
            )

        profile = (
            a.groupby(["Month", "Hour"])["Prod_MWh"]
            .mean()
            .unstack("Hour")
            .reindex(index=range(1, 13), columns=range(0, 24), fill_value=0.0)
        )
        return profile.values, None   # shape (12, 24)

    except Exception as e:
        return None, f"Asset profile build failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _simulate_one_year(
    model: dict,
    forward: float,
    solar_multiplier: float,
    nat_profile_288: np.ndarray,
    asset_profile_288: Optional[np.ndarray],
    rng: np.random.Generator,
    residuals: np.ndarray,
    basis: str,   # "National", "Asset", "Both"
) -> dict:
    """
    Simulate one year of hourly prices and compute outputs.

    Returns dict with keys depending on basis:
        price_sim      : np.array(8760) — simulated anchored prices
        nat_cp         : float (if National or Both)
        nat_sd         : float
        nat_baseload   : float
        asset_cp       : float (if Asset or Both)
        asset_sd       : float
    """
    # ── Block bootstrap on residuals ──────────────────────────────────────────
    # 52 blocks of 168h = 8736h, then top up with 24 more random hours
    n_resid = len(residuals)
    block_starts = rng.integers(0, max(1, n_resid - BLOCK_SIZE), size=N_BLOCKS_PER_YEAR)
    resid_sim = np.concatenate([
        residuals[s: s + BLOCK_SIZE] for s in block_starts
    ])  # 8736h

    # Top up to 8760h
    top_up = rng.integers(0, max(1, n_resid - 24), size=1)[0]
    resid_sim = np.concatenate([resid_sim, residuals[top_up: top_up + 24]])
    resid_sim = resid_sim[:HOURS_YEAR]   # exactly 8760

    # ── Build simulated prices hour by hour ───────────────────────────────────
    prices = np.empty(HOURS_YEAR, dtype=np.float64)

    for h in range(HOURS_YEAR):
        # Map hour index to (month, hour_of_day)
        # Simple approximation: 8760h, months of equal weight
        # Month 1..12, each ~730h
        month_idx = min(h // 730, 11)          # 0..11
        hour_of_day = h % 24

        # Solar MW for this hour (use profile × multiplier)
        solar_base = nat_profile_288[month_idx, hour_of_day]
        solar_sim  = solar_base * solar_multiplier

        prices[h] = (
            model["alpha"]
            + model["beta_solar"] * solar_sim
            + model["gamma_full"][hour_of_day]
            + model["delta_full"][month_idx]
            + resid_sim[h]
        )

    # ── Forward anchoring ─────────────────────────────────────────────────────
    annual_avg = prices.mean()
    if annual_avg > 0:
        prices = prices * (forward / annual_avg)
    else:
        prices = prices + (forward - annual_avg)

    # ── Baseload = mean of ALL simulated hours ────────────────────────────────
    baseload = float(prices.mean())

    result = {"price_sim": prices, "baseload": baseload}

    # ── National capture price ────────────────────────────────────────────────
    if basis in ("National", "Both"):
        nat_weights = np.array([
            nat_profile_288[min(h // 730, 11), h % 24]
            for h in range(HOURS_YEAR)
        ])
        nat_weights = nat_weights * solar_multiplier   # scale with capacity
        nat_prod_total = nat_weights.sum()

        if nat_prod_total > 0:
            nat_cp = float((nat_weights * prices).sum() / nat_prod_total)
        else:
            nat_cp = baseload

        nat_sd = 1.0 - nat_cp / baseload if baseload > 0 else 0.0
        result["nat_cp"] = nat_cp
        result["nat_sd"] = float(np.clip(nat_sd, -0.5, 0.99))

    # ── Asset capture price ───────────────────────────────────────────────────
    if basis in ("Asset", "Both") and asset_profile_288 is not None:
        asset_weights = np.array([
            asset_profile_288[min(h // 730, 11), h % 24]
            for h in range(HOURS_YEAR)
        ])
        asset_prod_total = asset_weights.sum()

        if asset_prod_total > 0:
            asset_cp = float((asset_weights * prices).sum() / asset_prod_total)
        else:
            asset_cp = baseload

        asset_sd = 1.0 - asset_cp / baseload if baseload > 0 else 0.0
        result["asset_cp"] = asset_cp
        result["asset_sd"] = float(np.clip(asset_sd, -0.5, 0.99))

    return result


def run_fpc_montecarlo(
    hourly: pd.DataFrame,
    model: dict,
    nat_profile_288: np.ndarray,
    asset_profile_288: Optional[np.ndarray],
    capacity_by_year: Dict[int, float],
    current_cap_gw: float,
    tenor_years: list,
    forward_by_year: Dict[int, float],   # {year: EUR/MWh} — flat in V1
    ppa: float,
    prod_p50_mwh: float,
    imb_rate: float,
    imb_forfait: float,
    basis: str,   # "National", "Asset", "Both"
    n_sim: int = 5_000,
    seed: int = 42,
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Run full FPC Monte Carlo simulation.

    Returns
    -------
    (results_dict, error_message)
    """
    try:
        rng       = np.random.default_rng(seed)
        residuals = model["residuals"]
        tenor     = len(tenor_years)

        # ── Pre-allocate output matrices ──────────────────────────────────────
        do_nat   = basis in ("National", "Both")
        do_asset = basis in ("Asset", "Both") and asset_profile_288 is not None

        if not do_nat and not do_asset:
            return None, "No valid basis to simulate. Check asset profile."

        # Shape: (n_sim, tenor)
        nat_sd_mat   = np.full((n_sim, tenor), np.nan) if do_nat   else None
        nat_cp_mat   = np.full((n_sim, tenor), np.nan) if do_nat   else None
        nat_pnl_mat  = np.full((n_sim, tenor), np.nan) if do_nat   else None
        asset_sd_mat  = np.full((n_sim, tenor), np.nan) if do_asset else None
        asset_cp_mat  = np.full((n_sim, tenor), np.nan) if do_asset else None
        asset_pnl_mat = np.full((n_sim, tenor), np.nan) if do_asset else None

        # ── Simulate ──────────────────────────────────────────────────────────
        for i in range(n_sim):
            for t, yr in enumerate(tenor_years):
                forward  = forward_by_year.get(yr, forward_by_year.get(tenor_years[0], 55.0))
                cap_yr   = capacity_by_year.get(yr, current_cap_gw)
                solar_mult = cap_yr / current_cap_gw if current_cap_gw > 0 else 1.0

                sim = _simulate_one_year(
                    model, forward, solar_mult,
                    nat_profile_288, asset_profile_288,
                    rng, residuals, basis,
                )

                imb_cost = prod_p50_mwh * imb_rate * imb_forfait / 1000

                if do_nat and "nat_cp" in sim:
                    nat_sd_mat[i, t]  = sim["nat_sd"]
                    nat_cp_mat[i, t]  = sim["nat_cp"]
                    pnl = prod_p50_mwh * (sim["nat_cp"] - ppa) / 1000 - imb_cost
                    nat_pnl_mat[i, t] = pnl

                if do_asset and "asset_cp" in sim:
                    asset_sd_mat[i, t]  = sim["asset_sd"]
                    asset_cp_mat[i, t]  = sim["asset_cp"]
                    pnl = prod_p50_mwh * (sim["asset_cp"] - ppa) / 1000 - imb_cost
                    asset_pnl_mat[i, t] = pnl

        # ── Aggregate ─────────────────────────────────────────────────────────
        def _bands(mat):
            """Compute percentile bands per year from (n_sim, tenor) matrix."""
            out = {}
            for p in [10, 25, 50, 75, 90]:
                out[p] = np.nanpercentile(mat, p, axis=0).tolist()
            return out

        def _cumul_stats(pnl_mat):
            cumul = np.nansum(pnl_mat, axis=1)
            pcts  = {p: float(np.nanpercentile(cumul, p))
                     for p in [5, 10, 25, 50, 75, 90, 95]}
            prob_loss = float((cumul < 0).mean())
            thresh    = np.nanpercentile(cumul, 10)
            es        = float(cumul[cumul <= thresh].mean()) if (cumul <= thresh).any() else float(cumul.min())
            return {
                "cumul_pnl":          cumul,
                "percentiles_cumul":  pcts,
                "prob_loss":          prob_loss,
                "expected_shortfall": es,
                "downside":           pcts[10] - pcts[50],
                "upside":             pcts[90] - pcts[50],
            }

        def _scenario_table(sd_mat, cp_mat, pnl_mat, years):
            rows = []
            for t, yr in enumerate(years):
                sd_col  = sd_mat[:, t]
                cp_col  = cp_mat[:, t]
                pnl_col = pnl_mat[:, t]
                rows.append({
                    "Year":             yr,
                    "SD P10":           f"{np.nanpercentile(sd_col,10)*100:.1f}%",
                    "SD P25":           f"{np.nanpercentile(sd_col,25)*100:.1f}%",
                    "SD P50":           f"{np.nanpercentile(sd_col,50)*100:.1f}%",
                    "SD P75":           f"{np.nanpercentile(sd_col,75)*100:.1f}%",
                    "SD P90":           f"{np.nanpercentile(sd_col,90)*100:.1f}%",
                    "Capture P50 (EUR)":f"{np.nanpercentile(cp_col,50):.2f}",
                    "P&L P10 (kEUR)":   f"{np.nanpercentile(pnl_col,10):+.0f}k",
                    "P&L P50 (kEUR)":   f"{np.nanpercentile(pnl_col,50):+.0f}k",
                    "P&L P90 (kEUR)":   f"{np.nanpercentile(pnl_col,90):+.0f}k",
                    "Downside":         f"{(np.nanpercentile(pnl_col,10)-np.nanpercentile(pnl_col,50)):+.0f}k",
                    "Upside":           f"{(np.nanpercentile(pnl_col,90)-np.nanpercentile(pnl_col,50)):+.0f}k",
                    "Volatility (std)": f"{np.nanstd(pnl_col):.0f}k",
                })
            return rows

        result = {
            "years":         tenor_years,
            "basis":         basis,
            "n_sim":         n_sim,
            "capacity_by_year": capacity_by_year,
            "forward_by_year":  forward_by_year,
        }

        if do_nat:
            cumul_nat = _cumul_stats(nat_pnl_mat)
            result["nat"] = {
                "sd_bands":        _bands(nat_sd_mat),
                "cp_bands":        _bands(nat_cp_mat),
                "pnl_bands":       _bands(nat_pnl_mat),
                "cumul_pnl":       cumul_nat["cumul_pnl"],
                "percentiles_cumul": cumul_nat["percentiles_cumul"],
                "prob_loss":       cumul_nat["prob_loss"],
                "expected_shortfall": cumul_nat["expected_shortfall"],
                "downside":        cumul_nat["downside"],
                "upside":          cumul_nat["upside"],
                "scenario_table":  _scenario_table(nat_sd_mat, nat_cp_mat, nat_pnl_mat, tenor_years),
            }

        if do_asset:
            cumul_asset = _cumul_stats(asset_pnl_mat)
            result["asset"] = {
                "sd_bands":        _bands(asset_sd_mat),
                "cp_bands":        _bands(asset_cp_mat),
                "pnl_bands":       _bands(asset_pnl_mat),
                "cumul_pnl":       cumul_asset["cumul_pnl"],
                "percentiles_cumul": cumul_asset["percentiles_cumul"],
                "prob_loss":       cumul_asset["prob_loss"],
                "expected_shortfall": cumul_asset["expected_shortfall"],
                "downside":        cumul_asset["downside"],
                "upside":          cumul_asset["upside"],
                "scenario_table":  _scenario_table(asset_sd_mat, asset_cp_mat, asset_pnl_mat, tenor_years),
            }

        return result, None

    except Exception as e:
        import traceback
        return None, f"Simulation failed: {e}\n{traceback.format_exc()}"
