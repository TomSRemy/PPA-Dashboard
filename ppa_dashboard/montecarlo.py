"""
montecarlo.py — KAL-EL : Monte Carlo P&L Simulation v2
=======================================================
Fully aligned with the regression-based cannibalization logic.
Bootstrap removed as standalone output — used only as internal
variance estimator if available.

Economic model
--------------
For each simulated year t in [1..tenor]:

    Shape discount (cannibalization):
        sd_t = sd_trend_t + ε_cannib_t
        where:
            sd_trend_t = ic_u + sl_u × year_t   (regression projection)
            ε_cannib_t ~ N(0, σ_cannib)          (intra-year variance)
            σ_cannib   = std(hist_sd_f)           (calibrated on history)

        → level set by regression, noise calibrated on history
        → fully consistent with projection in Tab 1 and Tab 2

    Captured price:
        cp_t = forward_t × (1 − sd_t)

    Forward price with uncertainty:
        forward_t = forward_input × (1 + ε_fwd_t)
        ε_fwd_t ~ N(0, σ_fwd)

    Production with variance:
        prod_t = prod_p50 × (1 + ε_vol_t)
        ε_vol_t ~ N(0, σ_vol)

P&L decomposition (3 components, fully transparent)
-----------------------------------------------------
    [1] Hedged P&L    = prod_t × (cp_t − PPA)          / 1000  [kEUR]
        → Core aggregator P&L on CAL-hedged volume
        → Driver: cannibalization (shape discount) vs PPA price

    [2] Merchant P&L  = prod_t × vol_delta_t × (da_price_t − PPA) / 1000
        → Over/under-production deboucled in DA
        → Currently set to 0 (simplified — can be extended)

    [3] Imbalance     = prod_t × imb_rate × imb_forfait / 1000  [kEUR]
        → Fixed cost, always negative

    Total P&L = [1] + [2] − [3]

Outputs
-------
Per trajectory (n_sim × tenor matrix):
    - annual_pnl_hedged   : hedged P&L [1]
    - annual_pnl_total    : total P&L [1]−[3]
    - annual_sd           : shape discount used
    - annual_cp           : captured price used
    - annual_fwd          : forward used

Aggregated statistics:
    - percentiles_cumul   : {p: kEUR} for cumulative total P&L
    - prob_loss           : P(cumulative P&L < 0)
    - expected_shortfall  : E[P&L | P&L ≤ P10]
    - percentile_bands    : annual fan chart {p: array(tenor)}
    - sd_percentile_bands : annual shape discount fan {p: array(tenor)}
    - cp_percentile_bands : annual capture price fan {p: array(tenor)}
    - scenario_table      : decision-oriented summary table
"""

import numpy as np
import pandas as pd

N_SIM    = 10_000
VOL_STD  = 0.12
FWD_STD  = 0.10
SEED     = 42


def run_montecarlo(
    ppa: float,
    forward_eur: float,
    prod_p50_mwh: float,
    sl_u: float,
    ic_u: float,
    last_yr: int,
    tenor: int,
    hist_sd_f=None,
    vol_std: float = VOL_STD,
    fwd_std: float = FWD_STD,
    n_sim: int = N_SIM,
    imb_rate: float = 0.03,
    imb_forfait: float = 1.9,
    seed: int = SEED,
    # bootstrap kept as optional internal variance input only
    bs_dist=None,
) -> dict:
    """
    Run Monte Carlo simulation aligned with regression cannibalization logic.

    Parameters
    ----------
    ppa            : fixed PPA price (EUR/MWh)
    forward_eur    : baseload forward (EUR/MWh)
    prod_p50_mwh   : P50 annual production (MWh)
    sl_u, ic_u     : regression slope and intercept (shape discount vs year)
    last_yr        : last historical year — tenor starts last_yr+1
    tenor          : contract length in years
    hist_sd_f      : historical shape discount Series — calibrates σ_cannib
    vol_std        : production annual std dev (fraction of P50). Default 12%
    fwd_std        : forward price annual std dev (fraction). Default 10%
    n_sim          : number of trajectories
    imb_rate       : fraction of production going to imbalance
    imb_forfait    : fixed imbalance cost (EUR/MWh)
    seed           : random seed
    bs_dist        : (optional) bootstrap distribution — used only for σ_cannib
                     calibration if hist_sd_f is insufficient
    """
    rng   = np.random.default_rng(seed)
    years = list(range(last_yr + 1, last_yr + tenor + 1))

    # ── Cannibalization variance — calibrate on history ───────────────────────
    # Use historical std of shape discount as intra-year noise
    # This is the ONLY role of bootstrap/history — the LEVEL comes from regression
    if hist_sd_f is not None and len(hist_sd_f) >= 3:
        sigma_cannib = float(np.std(hist_sd_f))
    elif bs_dist is not None and bs_dist.get("n_sim", 0) > 100:
        sigma_cannib = float(np.std(bs_dist["shape_disc_dist"]))
    else:
        sigma_cannib = 0.07   # default: ±7pp intra-year variance

    # ── Regression trend — LEVEL of shape discount per year ──────────────────
    sd_trend = np.array([ic_u + sl_u * yr for yr in years])
    sd_trend = np.clip(sd_trend, 0.0, 0.95)

    # ── Random draws (n_sim × tenor) ─────────────────────────────────────────
    # [1] Cannibalization noise around regression trend
    eps_cannib = rng.normal(0.0, sigma_cannib, size=(n_sim, tenor))

    # [2] Production variance
    eps_vol = rng.normal(1.0, vol_std, size=(n_sim, tenor))
    eps_vol = np.clip(eps_vol, 0.3, 2.0)

    # [3] Forward price variance
    eps_fwd = rng.normal(1.0, fwd_std, size=(n_sim, tenor))
    eps_fwd = np.clip(eps_fwd, 0.3, 3.0)

    # ── Simulate ──────────────────────────────────────────────────────────────
    # Shape discount matrix: trend level + intra-year noise
    sd_mat  = sd_trend[np.newaxis, :] + eps_cannib       # (n_sim, tenor)
    sd_mat  = np.clip(sd_mat, 0.0, 0.95)

    # Forward matrix
    fwd_mat = forward_eur * eps_fwd                       # (n_sim, tenor)

    # Captured price = forward × (1 − shape_discount)
    cp_mat  = fwd_mat * (1.0 - sd_mat)                   # (n_sim, tenor)

    # Production matrix
    prod_mat = prod_p50_mwh * eps_vol                    # (n_sim, tenor)

    # ── P&L decomposition ─────────────────────────────────────────────────────
    # [1] Hedged P&L (kEUR/yr) — core cannibalization risk
    pnl_hedged = prod_mat * (cp_mat - ppa) / 1000        # (n_sim, tenor)

    # [3] Imbalance cost (kEUR/yr) — always negative
    imb_cost   = prod_mat * imb_rate * imb_forfait / 1000  # (n_sim, tenor)

    # Total P&L
    pnl_total  = pnl_hedged - imb_cost                   # (n_sim, tenor)

    # Cumulative
    cumul_pnl  = pnl_total.sum(axis=1)                   # (n_sim,)

    # ── Statistics ────────────────────────────────────────────────────────────
    pct_levels = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    percentiles_cumul = {p: float(np.percentile(cumul_pnl, p)) for p in pct_levels}

    prob_loss = float((cumul_pnl < 0).mean())
    es_thresh = np.percentile(cumul_pnl, 10)
    es        = float(cumul_pnl[cumul_pnl <= es_thresh].mean())

    # Annual fan charts — P&L
    pct_bands = {}
    for p in [5, 10, 25, 50, 75, 90, 95]:
        pct_bands[p] = np.percentile(pnl_total, p, axis=0).tolist()

    # Annual fan charts — Shape Discount
    sd_bands = {}
    for p in [10, 25, 50, 75, 90]:
        sd_bands[p] = np.percentile(sd_mat, p, axis=0).tolist()

    # Annual fan charts — Captured Price
    cp_bands = {}
    for p in [10, 25, 50, 75, 90]:
        cp_bands[p] = np.percentile(cp_mat, p, axis=0).tolist()

    # Deterministic trend reference (no noise)
    sd_trend_det  = sd_trend.tolist()
    cp_trend_det  = (forward_eur * (1.0 - sd_trend)).tolist()
    pnl_trend_det = [
        prod_p50_mwh * (cp - ppa) / 1000 - prod_p50_mwh * imb_rate * imb_forfait / 1000
        for cp in cp_trend_det
    ]

    # ── Decision-oriented scenario table ──────────────────────────────────────
    # For each year, build summary stats across simulations
    scenario_rows = []
    for i, yr in enumerate(years):
        sd_col  = sd_mat[:, i]
        cp_col  = cp_mat[:, i]
        pnl_col = pnl_total[:, i]
        scenario_rows.append({
            "Year":                yr,
            "SD trend (reg.)":     f"{sd_trend[i]*100:.1f}%",
            "SD P50 (sim.)":       f"{np.percentile(sd_col,50)*100:.1f}%",
            "SD P90 (worst)":      f"{np.percentile(sd_col,90)*100:.1f}%",
            "Capture P50 (EUR/MWh)": f"{np.percentile(cp_col,50):.2f}",
            "P&L P50 (kEUR)":      f"{np.percentile(pnl_col,50):+.0f}k",
            "P&L P10 (kEUR)":      f"{np.percentile(pnl_col,10):+.0f}k",
            "P&L P90 (kEUR)":      f"{np.percentile(pnl_col,90):+.0f}k",
            "Downside (P10-P50)":  f"{(np.percentile(pnl_col,10)-np.percentile(pnl_col,50)):+.0f}k",
            "Upside (P90-P50)":    f"{(np.percentile(pnl_col,90)-np.percentile(pnl_col,50)):+.0f}k",
            "Volatility (std)":    f"{pnl_col.std():.0f}k",
        })

    # Cumulative decision table (single row summary)
    cumul_summary = {
        "Tenor":              tenor,
        "PPA price":          f"{ppa:.2f} EUR/MWh",
        "Forward":            f"{forward_eur:.2f} EUR/MWh",
        "SD trend yr1":       f"{sd_trend[0]*100:.1f}%",
        "SD trend last yr":   f"{sd_trend[-1]*100:.1f}%",
        "P50 cumul (kEUR)":   f"{percentiles_cumul[50]:+.0f}k",
        "P10 cumul (kEUR)":   f"{percentiles_cumul[10]:+.0f}k",
        "P90 cumul (kEUR)":   f"{percentiles_cumul[90]:+.0f}k",
        "Prob. of loss":      f"{prob_loss*100:.1f}%",
        "Expected shortfall": f"{es:+.0f}k",
        "Downside (P10-P50)": f"{(percentiles_cumul[10]-percentiles_cumul[50]):+.0f}k",
        "Upside (P90-P50)":   f"{(percentiles_cumul[90]-percentiles_cumul[50]):+.0f}k",
    }

    return {
        # Raw matrices
        "cumul_pnl":           cumul_pnl,
        "annual_pnl_total":    pnl_total,
        "annual_pnl_hedged":   pnl_hedged,
        "annual_sd":           sd_mat,
        "annual_cp":           cp_mat,
        "annual_fwd":          fwd_mat,
        # Summary stats
        "years":               years,
        "percentiles_cumul":   percentiles_cumul,
        "prob_loss":           prob_loss,
        "expected_shortfall":  es,
        # Fan charts
        "percentile_bands":    pct_bands,
        "sd_percentile_bands": sd_bands,
        "cp_percentile_bands": cp_bands,
        # Deterministic reference
        "sd_trend":            sd_trend_det,
        "cp_trend":            cp_trend_det,
        "pnl_trend":           pnl_trend_det,
        # Tables
        "scenario_table":      scenario_rows,
        "cumul_summary":       cumul_summary,
        # Metadata
        "n_sim":               n_sim,
        "sigma_cannib":        sigma_cannib,
        "use_bootstrap":       False,
        "params": {
            "ppa":          ppa,
            "forward":      forward_eur,
            "prod_p50_mwh": prod_p50_mwh,
            "vol_std":      vol_std,
            "fwd_std":      fwd_std,
            "tenor":        tenor,
            "sigma_cannib": sigma_cannib,
        },
    }
