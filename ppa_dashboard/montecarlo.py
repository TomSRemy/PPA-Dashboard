"""
montecarlo.py — KAL-EL : Monte Carlo P&L Simulation
=====================================================
Simulates N_SIM trajectories of cumulative P&L over the contract tenor.

Three independent sources of uncertainty
-----------------------------------------
[1] Cannibalization (shape discount)
    - Structural drift  : regression trend (sl_u × year + ic_u)
    - Intra-year noise  : bootstrap distribution (if available)
                          else normal(0, hist_std)
    - These are combined: sd_yr = sd_trend_yr + (sd_bootstrap_draw - sd_p50_bs)
      → the bootstrap contributes the *deviation from its median*, not its level.
      → the trend contributes the *level* forecast for that year.

[2] Volume (production vs P50e)
    - Normal(0, vol_std) applied to P50e each year
    - Default vol_std = 12% (typical solar FR interannual variance)
    - Independent of price and cannibalization

[3] Forward price
    - Normal(0, fwd_std) applied to forward each year
    - Default fwd_std = 10% (±1 sigma price uncertainty)
    - Independent of volume

Outputs per trajectory
-----------------------
    annual P&L × tenor years → cumulative P&L

Outputs of the simulation
--------------------------
    Distribution of cumulative P&L over N_SIM trajectories:
    - P10, P25, P50, P75, P90, mean
    - Probability of loss (P&L < 0)
    - Expected shortfall (mean of bottom 10%)
    - Annual fan chart: percentile bands per year

Integration
-----------
    from montecarlo import run_montecarlo
    mc = run_montecarlo(
        ppa=ppa, forward_eur=forward_eur,
        prod_p50_mwh=prod_mwh,
        sl_u=sl_u, ic_u=ic_u,
        last_yr=last_yr_proj,
        tenor=tenor_yr,
        bs_dist=bs_dist,          # from bootstrap.run_bootstrap() or None
        hist_sd_f=hist_sd_f,      # fallback if no bootstrap
        vol_std=0.12,
        fwd_std=0.10,
        n_sim=10_000,
    )
"""

import numpy as np
import pandas as pd
from typing import Optional


N_SIM     = 10_000
VOL_STD   = 0.12    # ±12% production variance (solar FR)
FWD_STD   = 0.10    # ±10% forward price uncertainty
SEED      = 42


def run_montecarlo(
    ppa: float,
    forward_eur: float,
    prod_p50_mwh: float,
    sl_u: float,
    ic_u: float,
    last_yr: int,
    tenor: int,
    bs_dist: Optional[dict] = None,
    hist_sd_f = None,
    vol_std: float = VOL_STD,
    fwd_std: float = FWD_STD,
    n_sim: int = N_SIM,
    imb_rate: float = 0.03,
    imb_forfait: float = 1.9,
    seed: int = SEED,
) -> dict:
    """
    Run Monte Carlo simulation.

    Parameters
    ----------
    ppa            : fixed PPA price (EUR/MWh)
    forward_eur    : baseload forward (EUR/MWh) — reference level
    prod_p50_mwh   : P50 annual production (MWh)
    sl_u, ic_u     : regression slope and intercept for shape discount trend
    last_yr        : last historical year (projection starts last_yr+1)
    tenor          : contract length in years
    bs_dist        : bootstrap distribution dict (from bootstrap.run_bootstrap)
                     If None, falls back to normal distribution from hist_sd_f
    hist_sd_f      : historical shape discount series (fallback)
    vol_std        : annual production std dev as fraction of P50
    fwd_std        : annual forward price std dev as fraction of forward
    n_sim          : number of trajectories
    imb_rate       : imbalance volume as fraction of production
    imb_forfait    : imbalance fixed cost (EUR/MWh)
    seed           : random seed

    Returns
    -------
    dict:
        cumul_pnl        : np.array(n_sim) — cumulative P&L per trajectory (kEUR)
        annual_pnl       : np.array(n_sim, tenor) — annual P&L matrix (kEUR)
        years            : list[int] — contract years
        percentiles_cumul: dict {p: value} for p in [5,10,25,50,75,90,95]
        prob_loss        : float — probability of cumulative loss
        expected_shortfall: float — mean of bottom 10% (kEUR)
        percentile_bands : dict {p: np.array(tenor)} — annual fan chart
        sd_trend         : np.array(tenor) — projected median shape disc per year
        params           : dict — simulation parameters for display
    """
    rng   = np.random.default_rng(seed)
    years = list(range(last_yr + 1, last_yr + tenor + 1))

    # ── Prepare cannibalization noise source ──────────────────────────────────
    if bs_dist is not None and bs_dist.get("n_sim", 0) > 100:
        # Use bootstrap distribution: draw deviations from bootstrap median
        bs_arr    = bs_dist["shape_disc_dist"]
        bs_median = float(np.median(bs_arr))
        bs_std    = float(np.std(bs_arr))
        use_bootstrap = True
    else:
        # Fallback: normal distribution calibrated on historical std
        if hist_sd_f is not None and len(hist_sd_f) >= 3:
            bs_median = float(np.median(hist_sd_f))
            bs_std    = float(np.std(hist_sd_f))
        else:
            bs_median = 0.15
            bs_std    = 0.08
        use_bootstrap = False

    # ── Projected trend per year ──────────────────────────────────────────────
    sd_trend = np.array([ic_u + sl_u * yr for yr in years])
    # Clip to [0, 0.95] — physical bounds
    sd_trend = np.clip(sd_trend, 0.0, 0.95)

    # ── Pre-draw random matrices ──────────────────────────────────────────────
    # Shape: (n_sim, tenor)

    # Cannibalization noise: deviation from bootstrap median
    if use_bootstrap:
        # Sample with replacement from bootstrap distribution
        bs_idx    = rng.integers(0, len(bs_arr), size=(n_sim, tenor))
        cannib_noise = bs_arr[bs_idx] - bs_median   # deviation only
    else:
        cannib_noise = rng.normal(0, bs_std, size=(n_sim, tenor))

    # Volume noise: multiplicative factor on P50
    vol_noise = rng.normal(1.0, vol_std, size=(n_sim, tenor))
    vol_noise = np.clip(vol_noise, 0.3, 2.0)   # physical bounds

    # Forward price noise: multiplicative factor
    fwd_noise = rng.normal(1.0, fwd_std, size=(n_sim, tenor))
    fwd_noise = np.clip(fwd_noise, 0.3, 3.0)

    # ── Simulate ──────────────────────────────────────────────────────────────
    # sd_yr[sim, yr] = trend[yr] + intra-year noise
    # Broadcast sd_trend (tenor,) across n_sim
    sd_matrix = sd_trend[np.newaxis, :] + cannib_noise        # (n_sim, tenor)
    sd_matrix = np.clip(sd_matrix, 0.0, 0.95)

    # Captured price matrix
    fwd_matrix       = forward_eur * fwd_noise                 # (n_sim, tenor)
    cp_matrix        = fwd_matrix * (1.0 - sd_matrix)         # (n_sim, tenor)

    # Production matrix
    prod_matrix      = prod_p50_mwh * vol_noise                # (n_sim, tenor)

    # P&L [1] CAL hedged (kEUR/yr)
    pnl1_matrix = prod_matrix * (cp_matrix - ppa) / 1000      # (n_sim, tenor)

    # P&L [3] Imbalance (kEUR/yr) — fixed cost, no noise on price
    imb_cost    = prod_matrix * imb_rate * imb_forfait / 1000  # (n_sim, tenor)

    # Total annual P&L (kEUR/yr)
    annual_pnl  = pnl1_matrix - imb_cost                      # (n_sim, tenor)

    # Cumulative P&L (kEUR)
    cumul_pnl   = annual_pnl.sum(axis=1)                      # (n_sim,)

    # ── Statistics ────────────────────────────────────────────────────────────
    pct_levels = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    percentiles_cumul = {p: float(np.percentile(cumul_pnl, p)) for p in pct_levels}

    prob_loss  = float((cumul_pnl < 0).mean())

    # Expected Shortfall = mean of bottom 10%
    threshold  = np.percentile(cumul_pnl, 10)
    es         = float(cumul_pnl[cumul_pnl <= threshold].mean())

    # Annual fan chart: percentile bands per year
    pct_bands  = {}
    for p in [5, 10, 25, 50, 75, 90, 95]:
        pct_bands[p] = np.percentile(annual_pnl, p, axis=0)   # (tenor,)

    # Trend-only (no noise) for reference line
    cp_trend   = forward_eur * (1.0 - sd_trend)
    pnl_trend  = prod_p50_mwh * (cp_trend - ppa) / 1000 - prod_p50_mwh * imb_rate * imb_forfait / 1000

    return {
        "cumul_pnl":          cumul_pnl,
        "annual_pnl":         annual_pnl,
        "years":              years,
        "percentiles_cumul":  percentiles_cumul,
        "prob_loss":          prob_loss,
        "expected_shortfall": es,
        "percentile_bands":   pct_bands,
        "sd_trend":           sd_trend,
        "pnl_trend":          pnl_trend,
        "n_sim":              n_sim,
        "use_bootstrap":      use_bootstrap,
        "params": {
            "ppa":          ppa,
            "forward":      forward_eur,
            "prod_p50_mwh": prod_p50_mwh,
            "vol_std":      vol_std,
            "fwd_std":      fwd_std,
            "tenor":        tenor,
            "bs_median":    bs_median,
            "bs_std":       bs_std,
        },
    }
