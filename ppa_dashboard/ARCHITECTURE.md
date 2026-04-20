# KAL-EL PPA Dashboard — Architecture

## File Map

```
ppa_dashboard/
│
├── theme.py          ← SINGLE SOURCE OF TRUTH for colors + chart sizes
│                        Edit here to retheme or resize all charts at once
│
├── config.py         ← Re-exports theme.py + constants (paths, TECH_CONFIG, CSS)
│                        No color values here
│
├── app.py            ← Thin orchestrator: sidebar, data loading, compute, tab dispatch
│                        316 lines — no UI rendering logic
│
├── ui.py             ← Reusable UI components (section, kpi_card, plotly_base, etc.)
├── data.py           ← All data loading functions (cached), rolling M0
├── compute.py        ← Pure business logic: PPA pricing, regression, projection
├── charts.py         ← All Plotly chart functions — each returns go.Figure
├── excel.py          ← Excel export builder
│
├── tab_overview.py          ← Tab 1: Historical CP, projection, production profiles
├── tab_ppa_pricing.py       ← Tab 2: Forward curve, waterfall, premiums
├── tab_market_dynamics.py   ← Tab 3: Neg hours, monthly profile, duck curve
├── tab_market_evolution.py  ← Tab 4: Rolling M0 capture rate
├── tab_pricer.py            ← Tab 5: Asset pricer (render_pricer_tab)
├── tab_market_overview.py   ← Tab 6: FR spot, commodities, imbalance, ancillary
├── tab_export.py            ← Tab 7: Excel export, load curve converter, ENTSO-E
├── tab_fpc.py               ← Tab 8: FPC Monte Carlo (render_fpc_tab)
│
├── data/
│   ├── hourly_spot.csv
│   ├── nat_reference.csv
│   ├── balancing_prices.csv
│   ├── market_prices.csv
│   ├── xborder_da_prices.csv
│   ├── fcr_prices.csv
│   └── last_update.txt
│
└── scripts/
    ├── update_entsoe.py
    └── update_entsoe_full.py
```

## Dependency Graph

```
theme.py
  └── config.py (re-exports + CSS)
        └── app.py
        └── charts.py
        └── ui.py
              └── charts.py
              └── tab_*.py
```

## How to Retheme

Open `theme.py` and edit **Section 1 — CORE PALETTE** (10 lines):

```python
NAVY    = "#1D3A4A"   # primary text, axis labels
TEAL    = "#2A9D8F"   # solar, positive, CTA
GOLD    = "#FFD700"   # warnings, tabs, bands
...
```

Everything else — CSS, chart colors, KPI cards, tab styles — updates automatically.

## How to Resize All Charts

Open `theme.py`, edit **Section 7 — CHART SIZES**:

```python
CHART_H_XS  = 300    # small KPI charts
CHART_H_SM  = 380    # compact charts
CHART_H_MD  = 480    # standard (default)
CHART_H_LG  = 580    # feature charts, dual-axis
CHART_H_XL  = 720    # heatmaps, full-page
```

## How to Add a New Chart

1. Write `chart_xxx(...)` function in `charts.py` — return `go.Figure`
2. Apply `plotly_base(fig, h=CHART_H_MD)` at the end
3. Use theme constants for all colors — never raw hex strings
4. Import and call from the appropriate `tab_*.py` file

## Token Efficiency for Claude Sessions

When working on a specific feature, load only:
- `theme.py` — colors/sizes
- The relevant `tab_*.py` — UI logic for that tab
- `charts.py` — only the chart functions involved

You don't need `app.py` unless changing sidebar or data flow.

## Data Flow

```
Sidebar inputs
     ↓
app.py: data loading + compute → ctx dict
     ↓
tab_*.py: render_tab_xxx(**ctx)
     ↓
charts.py: chart functions → go.Figure
     ↓
st.plotly_chart(fig)
```
