"""
excel.py — KAL-EL PPA Dashboard
8-sheet Excel export builder.
"""

import io
import pandas as pd
import numpy as np


def build_excel(nat_ref: pd.DataFrame,
                hourly: pd.DataFrame,
                asset_ann,
                has_asset: bool,
                asset_name: str,
                proj: pd.DataFrame,
                pnl_v: list,
                ppa: float,
                scenarios: list,
                fwd_curve: dict,
                hist_sd: np.ndarray) -> io.BytesIO:

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:

        # Sheet 1 — National History
        nat_ref.rename(columns={
            "year":            "Year",
            "spot":            "Spot Avg",
            "cp_nat":          "M0 Solar (EUR/MWh)",
            "cp_nat_pct":      "M0 Solar (%)",
            "shape_disc":      "Shape Discount Solar",
            "cp_wind":         "M0 Wind (EUR/MWh)",
            "cp_wind_pct":     "M0 Wind (%)",
            "shape_disc_wind": "Shape Discount Wind",
        }).to_excel(w, sheet_name="National History", index=False)

        # Sheet 2 — Asset History
        if has_asset and asset_ann is not None:
            asset_ann.to_excel(w, sheet_name="Asset History", index=False)

        # Sheet 3 — Forward Curve
        pd.DataFrame([{"Year": yr, "Forward (EUR/MWh)": px}
                      for yr, px in fwd_curve.items()]).to_excel(
            w, sheet_name="Forward Curve", index=False)

        # Sheet 4 — Projection
        proj.to_excel(w, sheet_name="Projection", index=False)

        # Sheet 5 — Percentiles P1-P100
        ref_fwd = list(fwd_curve.values())[0] if fwd_curve else 55.0
        pd.DataFrame([{
            "Percentile": p,
            "Shape Discount":
                float(np.percentile(hist_sd, p)) if len(hist_sd) > 0 else 0.15,
            "Captured Price (EUR/MWh)":
                ref_fwd * (1 - float(np.percentile(hist_sd, p))) if len(hist_sd) > 0 else ref_fwd * 0.85,
            "Annual P&L (k EUR)": pnl_v[p - 1],
        } for p in range(1, 101)]).to_excel(
            w, sheet_name="Percentiles P1-P100", index=False)

        # Sheet 6 — Scenarios
        if scenarios:
            pd.DataFrame([{
                "Scenario":     s["Scenario"],
                "P10 (k EUR)":  f"{s['p10']:+.0f}k",
                "P50 (k EUR)":  f"{s['p50']:+.0f}k",
                "P90 (k EUR)":  f"{s['p90']:+.0f}k",
            } for s in scenarios]).to_excel(w, sheet_name="Scenarios", index=False)

        # Sheet 7 — Monthly Stats
        monthly = hourly.groupby(["Year", "Month"]).agg(
            spot_avg  = ("Spot", "mean"),
            neg_hours = ("Spot", lambda x: (x < 0).sum()),
        ).reset_index()
        monthly.to_excel(w, sheet_name="Monthly Stats", index=False)

        # Sheet 8 — Hourly Data (last year)
        hourly.head(8760).to_excel(w, sheet_name="Hourly Data 1yr", index=False)

    buf.seek(0)
    return buf
