"""
fpc_model.py — KAL-EL : Generic Forward-Looking FPC Monte Carlo Engine v2
=========================================================================
Technology-agnostic capture price simulation framework.

Causal flow:
    Renewable Capacity (GW)
    → Renewable Output Multiplier
    → Simulated Hourly Prices (OLS + block bootstrap residuals)
    → Forward Anchoring (no-arbitrage: annual avg = forward input)
    → Capture Price (production-weighted average price)
    → Shape Discount (endogenous output: 1 - CP / baseload)
    → P&L

Key design decisions:
- Generic: works for Solar and Wind (and any technology with a national series)
- beta_renewable replaces beta_solar — linked to selected technology
- OLS fitted on production hours only (above configurable threshold)
  to avoid dilution of beta by irrelevant zero-production hours
- Baseload = mean of ALL simulated hours (not just production hours)
- Capture price = production-weighted average over production hours
- Shape discount = 1 - capture_price / baseload
- For "Both": identical simulated price paths, two separate capture prices
- Defensive: all functions return (result, error_message) tuples

Production thresholds (MW) — configurable here:
    SOLAR_THRESHOLD_MW : minimum NatMW to include in OLS fit
    WIND_THRESHOLD_MW  : minimum WindMW to include in OLS fit
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict

# ── Configurable thresholds ───────────────────────────────────────────────────
SOLAR_THRESHOLD_MW   = 100    # MW — exclude hours below this for Solar OLS fit
WIND_THRESHOLD_MW    = 200    # MW — exclude hours below this for Wind OLS fit

# ── Other constants ───────────────────────────────────────────────────────────
MIN_OBS_FOR_FIT      = 3_000  # minimum filtered hours to fit OLS
MIN_R2_WARNING       = 0.10   # warn if R² below this
BETA_ZERO_THRESHOLD  = -0.0001  # warn if beta_renewable >= this (not meaningfully negative)
MIN_ASSET_HOURS      = 2_000  # minimum asset production hours
BLOCK_SIZE           = 168    # 7 days × 24h for block bootstrap
N_BLOCKS_PER_YEAR    = 52
HOURS_YEAR           = 8_760

# ── PPE3 capacity scenarios by technology ─────────────────────────────────────
PPE3_TARGETS = {
    "Solar": {2030: 48.0,  2035: 67.5},
    "Wind":  {2030: 31.0,  2035: 37.5},
}

CAPACITY_SCENARIOS = {
    "Central (PPE3)":  "ppe3",
    "Conservative":    "conservative",
    "Accelerated":     "accelerated",
    "Custom":          "custom",
}

_SCENARIO_MULTIPLIERS = {
    "Solar": {
        "conservative": {2030: 40.0,  2035: 55.0},
        "accelerated":  {2028: 48.0,  2032: 67.5},
    },
    "Wind": {
        "conservative": {2030: 26.0,  2035: 32.0},
        "accelerated":  {2028: 31.0,  2032: 45.0},
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CAPACITY TRAJECTORY
# ═══════════════════════════════════════════════════════════════════════════════

def build_capacity_trajectory(
    current_cap_gw: float,
    current_year: int,
    tenor_years: list,
    techno: str = "Solar",
    scenario: str = "Central (PPE3)",
    custom_target_gw: float = 48.0,
    custom_target_year: int = 2030,
) -> Tuple[Dict[int, float], Optional[str]]:
    """
    Build renewable capacity trajectory for tenor years.

    Parameters
    ----------
    current_cap_gw    : current installed capacity (GW) from ENTSO-E B09
    current_year      : last historical year
    tenor_years       : list of future years to simulate
    techno            : "Solar" or "Wind"
    scenario          : one of CAPACITY_SCENARIOS keys
    custom_target_gw  : used if scenario == "Custom"
    custom_target_year: used if scenario == "Custom"

    Returns
    -------
    (capacity_by_year, error_message)
    """
    try:
        control = {current_year: current_cap_gw}
        ppe3    = PPE3_TARGETS.get(techno, PPE3_TARGETS["Solar"])

        scenario_key = CAPACITY_SCENARIOS.get(scenario, "ppe3")

        if scenario_key == "ppe3":
            control.update(ppe3)
        elif scenario_key == "conservative":
            control.update(_SCENARIO_MULTIPLIERS.get(techno, {}).get("conservative", ppe3))
        elif scenario_key == "accelerated":
            control.update(_SCENARIO_MULTIPLIERS.get(techno, {}).get("accelerated", ppe3))
        elif scenario_key == "custom":
            control[custom_target_year] = custom_target_gw
        else:
            control.update(ppe3)

        ctrl_years = sorted(control.keys())
        ctrl_vals  = [control[y] for y in ctrl_years]

        result = {}
        for yr in tenor_years:
            cap = float(np.interp(yr, ctrl_years, ctrl_vals))
            cap = max(current_cap_gw, cap)
            result[yr] = round(cap, 2)

        return result, None

    except Exception as e:
        return {yr: current_cap_gw for yr in tenor_years}, str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GENERIC OLS PRICE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

def _get_threshold(techno: str) -> float:
    """Return the production threshold (MW) for the given technology."""
    if techno == "Wind":
        return float(WIND_THRESHOLD_MW)
    return float(SOLAR_THRESHOLD_MW)


def fit_price_model(
    hourly: pd.DataFrame,
    renewable_col: str,
    techno: str = "Solar",
    exclude_2022: bool = False,
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Fit generic OLS price model on historical hourly data.

    Model (fitted on production hours only, above technology threshold):
        Spot_h = alpha
               + beta_renewable × RenewableMW_h
               + Σ gamma_k × I(Hour=k)    k=1..23  (ref=0)
               + Σ delta_m × I(Month=m)   m=2..12  (ref=1)
               + epsilon_h

    Parameters
    ----------
    hourly       : DataFrame with Date, Spot, Hour, Month, Year + renewable_col
    renewable_col: column name for renewable generation (e.g. "NatMW", "WindMW")
    techno       : "Solar" or "Wind" — determines production threshold
    exclude_2022 : exclude 2022 from calibration

    Returns
    -------
    (model_dict, error_message)
    """
    try:
        h = hourly.copy()
        h["Date"] = pd.to_datetime(h["Date"])

        # Check renewable column exists
        if renewable_col not in h.columns:
            return None, (
                f"Column '{renewable_col}' not found in hourly data. "
                f"Available columns: {list(h.columns)}. "
                f"Run the ENTSO-E update script to populate {renewable_col}."
            )

        if exclude_2022:
            h = h[h["Year"] != 2022]

        # Basic quality filters
        h = h.dropna(subset=["Spot", renewable_col])
        h = h[h["Spot"].between(-200, 1000)]
        h = h[h[renewable_col] >= 0]

        # ── Production threshold filter ───────────────────────────────────────
        # Only fit on hours where the technology actually produces
        # This prevents dilution of beta_renewable by zero-production hours
        threshold = _get_threshold(techno)
        h_fit = h[h[renewable_col] > threshold].copy()

        n_all      = len(h)
        n_filtered = len(h_fit)
        pct_kept   = n_filtered / n_all * 100 if n_all > 0 else 0

        if n_filtered < MIN_OBS_FOR_FIT:
            return None, (
                f"Not enough production hours after filtering "
                f"({renewable_col} > {threshold:.0f} MW): "
                f"{n_filtered:,} rows (minimum: {MIN_OBS_FOR_FIT:,}). "
                f"Total hours available: {n_all:,}. "
                f"Check that {renewable_col} is populated in hourly_spot.csv. "
                f"Consider lowering the threshold ({techno} threshold = {threshold:.0f} MW)."
            )

        # ── Build design matrix ───────────────────────────────────────────────
        renewable = h_fit[renewable_col].values.astype(np.float64)
        hours_arr = h_fit["Hour"].values.astype(int)
        months_arr = h_fit["Month"].values.astype(int)
        spot_arr  = h_fit["Spot"].values.astype(np.float64)
        n = len(h_fit)

        # Features: intercept(1) + renewable(1) + hour dummies(23) + month dummies(11) = 36
        n_feat = 36
        X = np.zeros((n, n_feat), dtype=np.float64)
        X[:, 0] = 1.0
        X[:, 1] = renewable
        for k in range(1, 24):
            X[:, 1 + k] = (hours_arr == k).astype(float)
        for m in range(2, 13):
            X[:, 24 + (m - 2)] = (months_arr == m).astype(float)

        # OLS via least squares (numerically stable)
        coeffs, _, rank, _ = np.linalg.lstsq(X, spot_arr, rcond=None)

        fitted    = X @ coeffs
        residuals = spot_arr - fitted

        ss_tot = float(np.sum((spot_arr - spot_arr.mean()) ** 2))
        ss_res = float(np.sum(residuals ** 2))
        r2     = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        rmse   = float(np.sqrt(np.mean(residuals ** 2)))

        alpha         = float(coeffs[0])
        beta_renewable = float(coeffs[1])
        gamma_full    = [0.0] + coeffs[2:25].tolist()   # index 0..23
        delta_full    = [0.0] + coeffs[25:36].tolist()  # index 0..11 (month-1)

        # ── Validation ────────────────────────────────────────────────────────
        warnings_list = []

        if beta_renewable >= BETA_ZERO_THRESHOLD:
            warnings_list.append(
                f"WARNING: beta_renewable = {beta_renewable:.5f} is zero or positive. "
                f"Expected: negative (more {techno.lower()} generation → lower prices). "
                f"Possible causes: insufficient data, wrong column, or data quality issues. "
                f"Simulated shape discounts will be unreliable."
            )

        if r2 < MIN_R2_WARNING:
            warnings_list.append(
                f"Model R² = {r2:.3f} is low. "
                f"Residual uncertainty (RMSE = {rmse:.1f} EUR/MWh) dominates. "
                f"P&L fan charts will be wide. Consider more historical data."
            )

        effect_at_peak = beta_renewable * h_fit[renewable_col].quantile(0.95)
        if abs(effect_at_peak) < 1.0 and beta_renewable < BETA_ZERO_THRESHOLD:
            warnings_list.append(
                f"beta_renewable is negative but very small "
                f"(effect at P95 production = {effect_at_peak:.2f} EUR/MWh). "
                f"Simulated shape discounts may be close to zero."
            )

        warning_str = "\n".join(warnings_list) if warnings_list else None

        # Monthly fitted vs actual (for validation chart)
        h_fit2 = h_fit.copy()
        h_fit2["_fitted"] = fitted
        monthly_check = h_fit2.groupby(["Year", "Month"]).agg(
            actual=("Spot", "mean"),
            fitted=("_fitted", "mean"),
        ).reset_index()

        return {
            "alpha":           alpha,
            "beta_renewable":  beta_renewable,
            "gamma_full":      gamma_full,
            "delta_full":      delta_full,
            "r2":              r2,
            "rmse":            rmse,
            "n_obs":           n_filtered,
            "n_obs_total":     n_all,
            "pct_hours_kept":  pct_kept,
            "threshold_mw":    threshold,
            "residuals":       residuals,
            "fitted":          fitted,
            "monthly_check":   monthly_check,
            "renewable_col":   renewable_col,
            "techno":          techno,
            "exclude_2022":    exclude_2022,
            "warning":         warning_str,
        }, None

    except Exception as e:
        import traceback
        return None, f"Model fitting failed: {e}\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PRODUCTION PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

def build_national_profile(
    hourly: pd.DataFrame,
    renewable_col: str,
    techno: str = "Solar",
    exclude_2022: bool = False,
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Build national production profile: mean MW by (Month, Hour).

    Returns
    -------
    (profile_288, error_message)
    profile_288 : np.array(12, 24) — profile[month-1, hour], mean MW
    """
    try:
        h = hourly.copy()
        if exclude_2022:
            h = h[h["Year"] != 2022]

        if renewable_col not in h.columns:
            return None, f"Column '{renewable_col}' not found in hourly data."

        h = h[h[renewable_col] > 0].copy()

        if len(h) < 1000:
            return None, (
                f"Not enough production hours in '{renewable_col}' "
                f"({len(h)} rows). Check data availability."
            )

        profile = (
            h.groupby(["Month", "Hour"])[renewable_col]
            .mean()
            .unstack("Hour")
            .reindex(index=range(1, 13), columns=range(0, 24), fill_value=0.0)
        )
        return profile.values.astype(np.float64), None

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
    if asset_raw is None:
        return None, "No asset load curve uploaded. Upload a file in the sidebar."

    if len(asset_raw) < MIN_ASSET_HOURS:
        return None, (
            f"Asset load curve has {len(asset_raw):,} rows, "
            f"minimum required: {MIN_ASSET_HOURS:,}. "
            "Upload more historical production data."
        )

    try:
        a = asset_raw.copy()
        a["Date"]  = pd.to_datetime(a["Date"])
        a["Month"] = a["Date"].dt.month
        a["Hour"]  = a["Date"].dt.hour
        a = a[a["Prod_MWh"] > 0]

        if len(a) < MIN_ASSET_HOURS:
            return None, (
                f"Asset has only {len(a):,} production hours "
                f"(minimum: {MIN_ASSET_HOURS:,}). Upload more data."
            )

        profile = (
            a.groupby(["Month", "Hour"])["Prod_MWh"]
            .mean()
            .unstack("Hour")
            .reindex(index=range(1, 13), columns=range(0, 24), fill_value=0.0)
        )
        return profile.values.astype(np.float64), None

    except Exception as e:
        return None, f"Asset profile build failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _simulate_one_year(
    model: dict,
    forward: float,
    renewable_multiplier: float,
    tech_profile_288: np.ndarray,
    asset_profile_288: Optional[np.ndarray],
    rng: np.random.Generator,
    residuals: np.ndarray,
    basis: str,
) -> dict:
    """
    Simulate one year of hourly prices and compute capture prices.

    Guardrails:
    - Same simulated price path used for both National and Asset in "Both"
    - Baseload = mean of ALL 8760 simulated hours
    - Capture price = production-weighted average price

    Parameters
    ----------
    model               : fitted OLS model dict
    forward             : forward price for anchoring (EUR/MWh)
    renewable_multiplier: cap_t / cap_current — scales national renewable output
    tech_profile_288    : np.array(12,24) national technology profile (mean MW)
    asset_profile_288   : np.array(12,24) asset profile (mean MWh/h) or None
    rng                 : numpy random generator
    residuals           : OLS residuals array for block bootstrap
    basis               : "National", "Asset", or "Both"

    Returns
    -------
    dict with: price_sim, baseload, nat_cp, nat_sd (if nat), asset_cp, asset_sd (if asset)
    """
    n_resid = len(residuals)

    # ── Block bootstrap on OLS residuals (168h blocks) ────────────────────────
    block_starts = rng.integers(0, max(1, n_resid - BLOCK_SIZE), size=N_BLOCKS_PER_YEAR)
    resid_parts  = [residuals[s: s + BLOCK_SIZE] for s in block_starts]
    resid_sim    = np.concatenate(resid_parts)  # 8736h

    # Top-up to 8760h
    top_start  = int(rng.integers(0, max(1, n_resid - 24)))
    resid_sim  = np.concatenate([resid_sim, residuals[top_start: top_start + 24]])
    resid_sim  = resid_sim[:HOURS_YEAR]

    # ── Build hour and month index arrays ─────────────────────────────────────
    # Each hour maps to a (month_idx 0..11, hour_of_day 0..23)
    # Simple uniform month approximation: 730h per month
    month_idx_arr   = np.minimum(np.arange(HOURS_YEAR) // 730, 11).astype(int)
    hour_of_day_arr = (np.arange(HOURS_YEAR) % 24).astype(int)

    # ── Renewable generation for each simulated hour ──────────────────────────
    # tech_profile_288[month_idx, hour_of_day] × multiplier
    renewable_sim = (
        tech_profile_288[month_idx_arr, hour_of_day_arr] * renewable_multiplier
    )

    # ── Simulate hourly prices ────────────────────────────────────────────────
    gamma_arr = np.array(model["gamma_full"])[hour_of_day_arr]   # (8760,)
    delta_arr = np.array(model["delta_full"])[month_idx_arr]     # (8760,)

    prices = (
        model["alpha"]
        + model["beta_renewable"] * renewable_sim
        + gamma_arr
        + delta_arr
        + resid_sim
    )

    # ── Forward anchoring (no-arbitrage) ──────────────────────────────────────
    # Rescale so annual average = forward input
    annual_avg = prices.mean()
    if annual_avg != 0:
        prices = prices * (forward / annual_avg)
    else:
        prices = prices + forward

    # ── Baseload = mean of ALL simulated hours ────────────────────────────────
    baseload = float(prices.mean())

    result = {"price_sim": prices, "baseload": baseload}

    # ── National capture price ────────────────────────────────────────────────
    if basis in ("National", "Both"):
        nat_weights    = tech_profile_288[month_idx_arr, hour_of_day_arr] * renewable_multiplier
        nat_prod_total = nat_weights.sum()

        if nat_prod_total > 0:
            nat_cp = float((nat_weights * prices).sum() / nat_prod_total)
        else:
            nat_cp = baseload

        nat_sd = float(np.clip(1.0 - nat_cp / baseload if baseload != 0 else 0.0, -0.5, 0.99))
        result["nat_cp"] = nat_cp
        result["nat_sd"] = nat_sd

    # ── Asset capture price (same price path) ────────────────────────────────
    if basis in ("Asset", "Both") and asset_profile_288 is not None:
        asset_weights    = asset_profile_288[month_idx_arr, hour_of_day_arr]
        asset_prod_total = asset_weights.sum()

        if asset_prod_total > 0:
            asset_cp = float((asset_weights * prices).sum() / asset_prod_total)
        else:
            asset_cp = baseload

        asset_sd = float(np.clip(1.0 - asset_cp / baseload if baseload != 0 else 0.0, -0.5, 0.99))
        result["asset_cp"] = asset_cp
        result["asset_sd"] = asset_sd

    return result


def run_fpc_montecarlo(
    model: dict,
    tech_profile_288: np.ndarray,
    asset_profile_288: Optional[np.ndarray],
    capacity_by_year: Dict[int, float],
    current_cap_gw: float,
    tenor_years: list,
    forward_by_year: Dict[int, float],
    ppa: float,
    prod_p50_mwh: float,
    imb_rate: float,
    imb_forfait: float,
    basis: str,
    n_sim: int = 1_000,
    seed: int = 42,
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Run generic FPC Monte Carlo simulation.

    For "Both": identical price paths, separate National and Asset capture prices.

    Returns
    -------
    (results_dict, error_message)
    """
    try:
        rng      = np.random.default_rng(seed)
        residuals = model["residuals"]
        tenor    = len(tenor_years)

        do_nat   = basis in ("National", "Both")
        do_asset = basis in ("Asset", "Both") and asset_profile_288 is not None

        if not do_nat and not do_asset:
            return None, (
                "No valid basis to simulate. "
                "Check that asset profile is available or select National."
            )

        # ── Pre-allocate (n_sim × tenor) matrices ─────────────────────────────
        def _alloc():
            return np.full((n_sim, tenor), np.nan)

        nat_sd_mat    = _alloc() if do_nat   else None
        nat_cp_mat    = _alloc() if do_nat   else None
        nat_pnl_mat   = _alloc() if do_nat   else None
        asset_sd_mat  = _alloc() if do_asset else None
        asset_cp_mat  = _alloc() if do_asset else None
        asset_pnl_mat = _alloc() if do_asset else None

        imb_cost_per_yr = prod_p50_mwh * imb_rate * imb_forfait / 1000  # kEUR

        # ── Simulation loop ───────────────────────────────────────────────────
        for i in range(n_sim):
            for t, yr in enumerate(tenor_years):
                forward  = forward_by_year.get(yr, list(forward_by_year.values())[0])
                cap_yr   = capacity_by_year.get(yr, current_cap_gw)
                mult     = cap_yr / current_cap_gw if current_cap_gw > 0 else 1.0

                sim = _simulate_one_year(
                    model, forward, mult,
                    tech_profile_288, asset_profile_288,
                    rng, residuals, basis,
                )

                if do_nat and "nat_cp" in sim:
                    nat_sd_mat[i, t]  = sim["nat_sd"]
                    nat_cp_mat[i, t]  = sim["nat_cp"]
                    nat_pnl_mat[i, t] = prod_p50_mwh * (sim["nat_cp"] - ppa) / 1000 - imb_cost_per_yr

                if do_asset and "asset_cp" in sim:
                    asset_sd_mat[i, t]  = sim["asset_sd"]
                    asset_cp_mat[i, t]  = sim["asset_cp"]
                    asset_pnl_mat[i, t] = prod_p50_mwh * (sim["asset_cp"] - ppa) / 1000 - imb_cost_per_yr

        # ── Aggregate results ─────────────────────────────────────────────────
        def _bands(mat):
            return {p: np.nanpercentile(mat, p, axis=0).tolist()
                    for p in [10, 25, 50, 75, 90]}

        def _cumul(pnl_mat):
            cumul = np.nansum(pnl_mat, axis=1)
            pcts  = {p: float(np.nanpercentile(cumul, p))
                     for p in [5, 10, 25, 50, 75, 90, 95]}
            prob_loss = float((cumul < 0).mean())
            thresh    = np.nanpercentile(cumul, 10)
            es_vals   = cumul[cumul <= thresh]
            es        = float(es_vals.mean()) if len(es_vals) > 0 else float(cumul.min())
            return {
                "cumul_pnl":          cumul,
                "percentiles_cumul":  pcts,
                "prob_loss":          prob_loss,
                "expected_shortfall": es,
                "downside":           pcts[10] - pcts[50],
                "upside":             pcts[90] - pcts[50],
            }

        def _table(sd_mat, cp_mat, pnl_mat, years):
            rows = []
            for t, yr in enumerate(years):
                sd_col  = sd_mat[:, t]
                cp_col  = cp_mat[:, t]
                pnl_col = pnl_mat[:, t]
                rows.append({
                    "Year":                yr,
                    "SD P10":              f"{np.nanpercentile(sd_col,10)*100:.1f}%",
                    "SD P25":              f"{np.nanpercentile(sd_col,25)*100:.1f}%",
                    "SD P50":              f"{np.nanpercentile(sd_col,50)*100:.1f}%",
                    "SD P75":              f"{np.nanpercentile(sd_col,75)*100:.1f}%",
                    "SD P90":              f"{np.nanpercentile(sd_col,90)*100:.1f}%",
                    "Capture P50 (EUR/MWh)": f"{np.nanpercentile(cp_col,50):.2f}",
                    "P&L P10 (kEUR)":      f"{np.nanpercentile(pnl_col,10):+.0f}k",
                    "P&L P50 (kEUR)":      f"{np.nanpercentile(pnl_col,50):+.0f}k",
                    "P&L P90 (kEUR)":      f"{np.nanpercentile(pnl_col,90):+.0f}k",
                    "Downside (P10−P50)":  f"{(np.nanpercentile(pnl_col,10)-np.nanpercentile(pnl_col,50)):+.0f}k",
                    "Upside (P90−P50)":    f"{(np.nanpercentile(pnl_col,90)-np.nanpercentile(pnl_col,50)):+.0f}k",
                    "Volatility (std)":    f"{np.nanstd(pnl_col):.0f}k",
                })
            return rows

        result = {
            "years":            tenor_years,
            "basis":            basis,
            "n_sim":            n_sim,
            "capacity_by_year": capacity_by_year,
            "forward_by_year":  forward_by_year,
        }

        if do_nat:
            c = _cumul(nat_pnl_mat)
            result["nat"] = {
                "sd_bands":           _bands(nat_sd_mat),
                "cp_bands":           _bands(nat_cp_mat),
                "pnl_bands":          _bands(nat_pnl_mat),
                "cumul_pnl":          c["cumul_pnl"],
                "percentiles_cumul":  c["percentiles_cumul"],
                "prob_loss":          c["prob_loss"],
                "expected_shortfall": c["expected_shortfall"],
                "downside":           c["downside"],
                "upside":             c["upside"],
                "scenario_table":     _table(nat_sd_mat, nat_cp_mat, nat_pnl_mat, tenor_years),
            }

        if do_asset:
            c = _cumul(asset_pnl_mat)
            result["asset"] = {
                "sd_bands":           _bands(asset_sd_mat),
                "cp_bands":           _bands(asset_cp_mat),
                "pnl_bands":          _bands(asset_pnl_mat),
                "cumul_pnl":          c["cumul_pnl"],
                "percentiles_cumul":  c["percentiles_cumul"],
                "prob_loss":          c["prob_loss"],
                "expected_shortfall": c["expected_shortfall"],
                "downside":           c["downside"],
                "upside":             c["upside"],
                "scenario_table":     _table(asset_sd_mat, asset_cp_mat, asset_pnl_mat, tenor_years),
            }

        return result, None

    except Exception as e:
        import traceback
        return None, f"Simulation failed: {e}\n{traceback.format_exc()}"
