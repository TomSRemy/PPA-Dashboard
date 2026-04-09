"""
PPA Pricing Dashboard —  v2.2
v2.2: Rolling M0 computed on raw hourly windows (not daily averages)
"""

import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import io

st.set_page_config(
    page_title="  PPA Pricing Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

C1  = "#1D3A4A"
C2  = "#2A9D8F"
C3  = "#FFD700"
C4  = "#F7DC6F"
C5  = "#E76F51"
BG  = "#F7F4F0"
C2L = "#D4EDEA"
C3L = "#FFF8DC"
C4L = "#FFFACD"
C5L = "#FAEAE6"
WHT = "#FFFFFF"

st.markdown(f"""<style>
html, body, [class*="css"] {{
    font-family: Calibri, 'Segoe UI', Arial, sans-serif !important;
    font-size: 15px !important;
    background-color: {BG} !important;
}}
h1 {{ font-size: 24px !important; font-weight: 700 !important; color: {C1} !important; font-family: Calibri, Arial, sans-serif !important; }}
h2 {{ font-size: 18px !important; font-weight: 700 !important; color: {C1} !important; }}
h3 {{ font-size: 16px !important; font-weight: 700 !important; color: {C1} !important; }}
p, li, label, .stMarkdown, td, th {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; color: {C1} !important; }}

.section-title {{
    font-size: 13px !important; font-weight: 700; color: {WHT};
    background: linear-gradient(135deg, {C1}, #2A4A5A);
    padding: 8px 14px; border-radius: 4px; margin: 24px 0 10px 0;
    letter-spacing: 0.06em; text-transform: uppercase; display: block;
    border-left: 4px solid {C3};
}}
.chart-desc {{
    font-size: 13px !important; color: {C1} !important;
    background: {C3L}; border-left: 4px solid {C3};
    padding: 10px 14px; border-radius: 0 6px 6px 0;
    margin: 0 0 16px 0; line-height: 1.6; font-family: Calibri, Arial, sans-serif;
}}
.ppa-card {{
    background: linear-gradient(135deg, {C2}, #238B7D); color: {WHT};
    padding: 20px 22px; border-radius: 10px; text-align: center;
    box-shadow: 0 4px 12px rgba(42,157,143,0.3);
}}
.ppa-card .val {{ font-size: 32px; font-weight: 700; color: {WHT} !important; font-family: Calibri, Arial, sans-serif; }}
.ppa-card .lbl {{ font-size: 11px; color: {WHT} !important; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.06em; }}
.kpi-card {{
    background: {WHT}; border-left: 5px solid {C2}; padding: 14px 18px; border-radius: 6px;
    border: 1px solid #E0E0E0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
.kpi-val {{ font-size: 24px; font-weight: 700; color: {C1}; font-family: Calibri, Arial, sans-serif; }}
.kpi-lbl {{ font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-red {{ border-left-color: {C5} !important; }}
.kpi-gold {{ border-left-color: {C3} !important; }}
.update-pill {{
    background: {C3L}; border: 1px solid {C3}; border-radius: 20px; padding: 5px 16px;
    font-size: 12px; color: {C1}; display: inline-block; font-family: Calibri, Arial, sans-serif; font-weight: 600;
}}
.ytd-badge {{
    font-size: 10px; font-weight: 700; color: {C1}; background: {C3};
    padding: 2px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}}
.tbl-note {{ font-size: 12px; color: #555; font-style: italic; margin-top: 6px; font-family: Calibri, Arial, sans-serif; }}
.status-msg {{
    background: linear-gradient(135deg, {C2L}, #E8F5F3); border: 1px solid {C2};
    border-radius: 8px; padding: 12px 18px; color: {C1} !important; font-weight: 500; margin: 10px 0;
}}

[data-testid="stSidebar"] {{ background: linear-gradient(90deg, {C1}, #152A36) !important; }}
[data-testid="stSidebar"] * {{ color: {WHT} !important; font-family: Calibri, Arial, sans-serif !important; }}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] p {{ color: #D0E4ED !important; font-size: 13px !important; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {WHT} !important; font-size: 15px !important; border-bottom: 1px solid {WHT}; padding-bottom: 6px; }}
[data-testid="stSlider"] > div > div > div {{ background: linear-gradient(90deg, {C3}, {C4}) !important; }}
[data-testid="stSlider"] div[role="slider"] {{ background-color: {C3} !important; border: 2px solid {WHT} !important; box-shadow: none !important; }}

.stTabs [data-baseweb="tab"] {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; font-weight: 600; padding: 10px 20px !important; }}
.stTabs [data-baseweb="tab"]:not([aria-selected="true"]) p {{ color: rgba(247, 220, 111, 0.7) !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ border-bottom: 3px solid {C3} !important; background: {C3L} !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] p {{ color: {C2} !important; font-weight: 700 !important; font-size: 15.5px !important; }}

.stButton > button {{
    background: linear-gradient(135deg, {C2}, #238B7D) !important; color: {WHT} !important;
    border: none !important; border-radius: 6px !important; font-family: Calibri, Arial, sans-serif !important;
    font-size: 14px !important; font-weight: 600 !important; padding: 10px 24px !important;
    box-shadow: 0 2px 8px rgba(42,157,143,0.3) !important; transition: all 0.2s ease !important;
}}
.stButton > button:hover {{ background: linear-gradient(135deg, {C1}, #2A4A5A) !important; transform: translateY(-1px) !important; }}
.stDownloadButton > button {{ background: linear-gradient(135deg, {C3}, {C4}) !important; color: {C1} !important; border: none !important; font-weight: 700 !important; }}
.stAlert {{ background-color: {C3L} !important; border: 1px solid {C3} !important; border-radius: 6px !important; }}
.stAlert > div {{ color: {C1} !important; }}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_FORWARD = {2026: 55.0, 2027: 54.0, 2028: 53.0, 2029: 52.0, 2030: 51.0}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def section(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)

def desc(text):
    st.markdown(f'<div class="chart-desc">{text}</div>', unsafe_allow_html=True)

def plotly_base(fig, h=400, show_legend=True, legend_below=True):
    legend_config = dict(
        orientation="h", yanchor="top",
        y=-0.15 if legend_below else 1.02,
        xanchor="center", x=0.5,
        font=dict(size=12, color=C1, family="Calibri, Arial"),
        bgcolor="rgba(255,255,255,0.9)", bordercolor="#DDDDDD", borderwidth=1,
    ) if show_legend else dict(visible=False)
    fig.update_layout(
        height=h, plot_bgcolor=WHT, paper_bgcolor=BG,
        margin=dict(l=60, r=40, t=50, b=100 if legend_below else 40),
        font=dict(family="Calibri, Arial, sans-serif", size=14, color=C1),
        legend=legend_config,
        title=dict(font=dict(size=16, color=C1, family="Calibri, Arial"), x=0.5, xanchor="center", y=0.98, yanchor="top")
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEEEEE", gridwidth=1, linecolor="#CCCCCC", linewidth=1,
                     tickfont=dict(family="Calibri, Arial", size=12, color=C1),
                     title_font=dict(family="Calibri, Arial", size=13, color=C1))
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE", gridwidth=1, linecolor="#CCCCCC", linewidth=1,
                     tickfont=dict(family="Calibri, Arial", size=12, color=C1),
                     title_font=dict(family="Calibri, Arial", size=13, color=C1))

# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_nat():
    df = pd.read_csv(DATA_DIR / "nat_reference.csv")
    if "partial" not in df.columns:
        df["partial"] = False
    return df

@st.cache_data(ttl=3600)
def load_hourly():
    df = pd.read_csv(DATA_DIR / "hourly_spot.csv", parse_dates=["Date"])
    df["Month"] = df["Date"].dt.month
    return df

def load_log():
    p = DATA_DIR / "last_update.txt"
    return p.read_text() if p.exists() else "Initial data loaded."

# ══════════════════════════════════════════════════════════════════════════════
# ROLLING M0 — computed on raw hourly windows
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def compute_rolling_m0(hourly_df, windows=(30, 90, 365)):
    """
    For each calendar day t, compute M0 and Baseload over the last N days
    of RAW hourly data (not a mean of daily means).

    M0_N(t)       = sum(NatMW * Spot) / sum(NatMW)   over hours in [t-N, t]
    Baseload_N(t) = sum(Spot) / count(hours)           over hours in [t-N, t]
    CP%_N(t)      = M0_N(t) / Baseload_N(t)

    Requires at least half the window filled (min_periods = N*12 hours).
    """
    h = hourly_df.copy()
    h["Date"] = pd.to_datetime(h["Date"])
    h = h.sort_values("Date").reset_index(drop=True)
    h["Rev_nat"] = h["NatMW"] * h["Spot"]
    h["Date_d"]  = h["Date"].dt.normalize()

    dates = sorted(h["Date_d"].unique())
    max_window = max(windows)

    # Pre-index by date for fast slicing
    h_indexed = h.set_index("Date_d")

    rows = {w: [] for w in windows}

    for d in dates:
        for w in windows:
            cutoff = pd.Timestamp(d) - pd.Timedelta(days=w)
            # Select rows where Date_d is in (cutoff, d] — inclusive on d
            mask = (h["Date_d"] > cutoff) & (h["Date_d"] <= d)
            window = h[mask]

            min_h = w * 12   # require at least half the window
            if len(window) < min_h:
                rows[w].append({"Date": d, f"m0_{w}d": np.nan,
                                f"bl_{w}d": np.nan, f"cp_{w}d": np.nan})
                continue

            sum_rev  = window["Rev_nat"].sum()
            sum_prod = window["NatMW"].sum()
            sum_spot = window["Spot"].sum()
            count_h  = len(window)

            m0 = sum_rev / sum_prod if sum_prod > 0 else np.nan
            bl = sum_spot / count_h
            cp = m0 / bl if bl and bl != 0 else np.nan

            rows[w].append({"Date": d, f"m0_{w}d": m0,
                            f"bl_{w}d": bl, f"cp_{w}d": cp})

    dfs = [pd.DataFrame(rows[w]).set_index("Date") for w in windows]
    out = pd.concat(dfs, axis=1).reset_index()
    out["Date"] = pd.to_datetime(out["Date"])
    return out

def compute_asset_annual(hourly, asset_df):
    a = asset_df.copy()
    a["Date"] = pd.to_datetime(a["Date"])
    a = a.set_index("Date").resample("1h").mean().reset_index()
    m = hourly.merge(a[["Date", "Prod_MWh"]], on="Date", how="inner")
    m = m[m["Spot"] > 0].copy()
    m["Rev"] = m["Prod_MWh"] * m["Spot"]
    ann = m.groupby("Year").agg(
        prod_mwh=("Prod_MWh", "sum"), revenue=("Rev", "sum"),
        spot_avg=("Spot", "mean"),
        prod_hours=("Prod_MWh", lambda x: (x > 0).sum()),
        neg_hours=("Spot", lambda x: (x < 0).sum()),
        nat_mw=("NatMW", "mean"),
    ).reset_index()
    ann["prod_gwh"]  = ann["prod_mwh"] / 1000
    ann["cp_eur"]    = ann["revenue"] / ann["prod_mwh"].replace(0, np.nan)
    ann["cp_pct"]    = ann["cp_eur"] / ann["spot_avg"]
    ann["shape_disc"]= 1 - ann["cp_pct"]
    return ann.dropna(subset=["cp_pct"])

def fit_reg(ann, n, ex22):
    d = ann.copy()
    if "partial" in d.columns:
        d = d[d["partial"] != True]
    elif "Year" in d.columns:
        d = d[d["Year"] < pd.Timestamp.now().year]
    if ex22:
        col = "Year" if "Year" in d.columns else "year"
        d = d[d[col] != 2022]
    d = d.tail(n).dropna(subset=["shape_disc"])
    if len(d) < 2:
        d = ann.dropna(subset=["shape_disc"])
    if len(d) < 2:
        return 0.0, ann["shape_disc"].mean() if len(ann) else 0.15, 0.0
    x = d["Year"].values.astype(float) if "Year" in d.columns else d["year"].values.astype(float)
    y = d["shape_disc"].values
    sl, ic, r, *_ = stats.linregress(x, y)
    return sl, ic, r**2

def project_cp(sl, ic, last_yr, n=5, sig=0.04):
    rows = []
    for t, yr in enumerate(range(last_yr + 1, last_yr + n + 1)):
        fsd = ic + sl * yr
        cs  = sig * np.sqrt(t + 1)
        rows.append({"year": yr, "fsd": fsd,
                     "p10": 1-(fsd+1.28*cs), "p25": 1-(fsd+0.674*cs),
                     "p50": 1-fsd,
                     "p75": 1-(fsd-0.674*cs), "p90": 1-(fsd-1.28*cs)})
    return pd.DataFrame(rows)

def build_excel(nat_ref, hourly, asset_ann, has_asset, asset_name,
                proj, pnl_v, ppa, scenarios_data, fwd_curve, hist_sd):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        nat_ref.rename(columns={"year": "Year", "spot": "Spot Avg",
                                "cp_nat": "M0 (EUR/MWh)", "cp_nat_pct": "M0 (%)",
                                "shape_disc": "Shape Discount"}).to_excel(w, sheet_name="National History", index=False)
        if has_asset and asset_ann is not None:
            asset_ann.to_excel(w, sheet_name="Asset History", index=False)
        pd.DataFrame([{"Year": yr, "Forward (EUR/MWh)": px}
                      for yr, px in fwd_curve.items()]).to_excel(w, sheet_name="Forward Curve", index=False)
        proj.to_excel(w, sheet_name="Projection", index=False)
        ref_fwd = list(fwd_curve.values())[0] if fwd_curve else 55.0
        pd.DataFrame([{
            "Percentile": p,
            "Shape Discount": float(np.percentile(hist_sd, p)) if len(hist_sd) > 0 else 0.15,
            "Captured Price (EUR/MWh)": ref_fwd*(1-float(np.percentile(hist_sd, p))) if len(hist_sd) > 0 else ref_fwd*0.85,
            "Annual P&L (k EUR)": pnl_v[p-1]
        } for p in range(1, 101)]).to_excel(w, sheet_name="Percentiles P1-P100", index=False)
        if scenarios_data:
            pd.DataFrame(scenarios_data).to_excel(w, sheet_name="Scenarios", index=False)
        monthly = hourly.groupby(["Year","Month"]).agg(
            spot_avg=("Spot","mean"), neg_hours=("Spot", lambda x: (x<0).sum())).reset_index()
        monthly.to_excel(w, sheet_name="Monthly Stats", index=False)
        hourly.head(8760).to_excel(w, sheet_name="Hourly Data 1yr", index=False)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("###   Dashboard")
    st.markdown(f'<div class="update-pill">{load_log().split(chr(10))[0]}</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### Market Settings")
    n_reg = st.slider("Regression Years", 2, 12, 3)
    ex22  = st.toggle("Exclude 2022", value=False)
    st.markdown("---")
    st.markdown("### PPA Parameters")
    imb_eur  = st.number_input("Imbalance Cost (EUR/MWh)", 0.0, 10.0, 1.9, 0.1)
    add_disc = st.slider("Additional Discount (%)", 0.0, 10.0, 0.0, 0.25) / 100
    st.markdown("---")
    st.markdown("### Sensitivity Analysis")
    chosen_pct = st.slider("Selected Percentile", 1, 100, 74)
    proj_n     = st.slider("Projection Horizon (years)", 1, 10, 5)
    vol_stress = st.slider("Volume Stress (±%)", 0, 30, 20)
    spot_stress= st.slider("Spot Stress (±%)", 0, 30, 20)
    st.markdown("---")
    st.markdown("### Load Curve Upload")
    uploaded = st.file_uploader("Hourly Production", type=["xlsx","csv"])
    st.caption("Columns: Date | Prod_MWh")
    st.markdown("---")
    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LOAD & COMPUTE
# ══════════════════════════════════════════════════════════════════════════════

nat_ref  = load_nat()
hourly   = load_hourly()
data_end   = pd.to_datetime(hourly["Date"]).max()
data_start = pd.to_datetime(hourly["Date"]).min()

partial_years = nat_ref[nat_ref["partial"] == True]["year"].tolist() if "partial" in nat_ref.columns else []
current_year  = pd.Timestamp.now().year

asset_ann  = None
asset_name = "Asset"
asset_raw  = None

if uploaded:
    try:
        asset_raw = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded))
        dc = next((c for c in asset_raw.columns if any(k in c.lower() for k in ["date","time"])), asset_raw.columns[0])
        pc = next((c for c in asset_raw.columns if any(k in c.lower() for k in ["prod","mwh","power","gen","kwh"])), asset_raw.columns[1])
        asset_raw[dc] = pd.to_datetime(asset_raw[dc], errors="coerce")
        asset_raw[pc] = pd.to_numeric(asset_raw[pc], errors="coerce")
        if asset_raw[pc].max() > 10000:
            asset_raw[pc] /= 1000
        df_a = asset_raw[[dc,pc]].rename(columns={dc:"Date", pc:"Prod_MWh"})
        asset_ann  = compute_asset_annual(hourly, df_a)
        asset_name = uploaded.name.rsplit(".",1)[0]
        st.sidebar.success(f"Loaded: {asset_name}")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

has_asset = asset_ann is not None and len(asset_ann) >= 2

nat_ref_complete = nat_ref[nat_ref["partial"] == False] if "partial" in nat_ref.columns else nat_ref
work_for_reg = nat_ref.rename(columns={"year":"Year"}).copy()
if has_asset:
    work_for_reg = asset_ann.copy()

sl,  ic,  r2  = fit_reg(work_for_reg, n_reg, False)
sl2, ic2, r22 = fit_reg(work_for_reg, n_reg, True)
sl_u = sl2 if ex22 else sl
ic_u = ic2 if ex22 else ic
r2_u = r22 if ex22 else r2

last_yr_complete = int(nat_ref_complete["year"].max()) if len(nat_ref_complete) > 0 else int(nat_ref["year"].max())
last_yr      = int(asset_ann["Year"].iloc[-1]) if has_asset else int(nat_ref["year"].max())
last_yr_proj = last_yr_complete

hist_sd = asset_ann["shape_disc"].dropna() if has_asset else nat_ref_complete["shape_disc"].dropna()
hist_sd_f = hist_sd
if has_asset and ex22:
    hist_sd_f = asset_ann[asset_ann["Year"] != 2022]["shape_disc"].dropna()
elif ex22:
    hist_sd_f = nat_ref_complete[nat_ref_complete["year"] != 2022]["shape_disc"].dropna()

sd_ch   = float(np.percentile(hist_sd_f, chosen_pct)) if len(hist_sd_f) > 0 else 0.15
vol_mwh = asset_ann["prod_mwh"].mean() if has_asset else 52000.0
proj    = project_cp(sl_u, ic_u, last_yr_proj, proj_n)
pcts    = list(range(1,101))
sd_vals = [float(np.percentile(hist_sd_f, p)) if len(hist_sd_f) > 0 else 0.15 for p in pcts]

fwd_rows_d = [{"year": yr, "forward": float(DEFAULT_FORWARD.get(yr, 52.0))}
              for yr in range(last_yr_proj+1, last_yr_proj+proj_n+1)]
fwd_df    = pd.DataFrame(fwd_rows_d)
fwd_curve = dict(zip(fwd_df["year"], fwd_df["forward"]))
ref_fwd   = fwd_df["forward"].iloc[0] if len(fwd_df) > 0 else 55.0
imb_pct   = imb_eur / ref_fwd if ref_fwd > 0 else 0.035
tot_disc  = sd_ch + imb_pct + add_disc
ppa       = ref_fwd*(1-tot_disc) - imb_eur
cp_vals   = [ref_fwd*(1-s) for s in sd_vals]
pnl_v     = [vol_mwh*(c-ppa)/1000 for c in cp_vals]
be        = next((p for p,v in zip(pcts,pnl_v) if v < 0), None)
scenarios_export = []

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Overview", "Forward Curve & Pricing", "Cannibalization & Market",
    "Sensitivity & Scenarios", "Price Waterfall", "Market Evolution",
    "Export & SPOT Extractor",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Overview
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.markdown("## PPA Pricing Dashboard — France Solar")
    ca, cb = st.columns([3,1])
    with ca:
        ytd_note = f" — <span class='ytd-badge'>2026 YTD included</span>" if current_year in partial_years else ""
        st.markdown(f'<span style="font-size:14px;color:#555;">Aggregator View — Fixed PPA Purchase / Spot Capture Sale — '
                    f'ENTSO-E {data_start.year}–{data_end.strftime("%Y-%m-%d")}{ytd_note}</span>',
                    unsafe_allow_html=True)
    with cb:
        st.markdown(f'<div class="update-pill" style="float:right">Data as of {data_end.strftime("%d/%m/%Y")}</div>',
                    unsafe_allow_html=True)
    st.markdown('<div class="status-msg">Automatic daily updates via GitHub Actions — ENTSO-E France data.</div>',
                unsafe_allow_html=True)
    st.markdown("---")

    k1,k2,k3,k4,k5 = st.columns(5)
    with k1:
        st.markdown(f'<div class="ppa-card"><div class="lbl">PPA Price (P{chosen_pct})</div>'
                    f'<div class="val">{ppa:.2f}</div><div class="lbl">EUR / MWh</div></div>',
                    unsafe_allow_html=True)
    with k2:
        cp_l_row = nat_ref_complete.iloc[-1] if len(nat_ref_complete) > 0 else nat_ref.iloc[-1]
        cp_l  = cp_l_row["cp_nat_pct"]*100 if not has_asset else asset_ann["cp_pct"].iloc[-1]*100
        kpi_yr= int(cp_l_row["year"]) if not has_asset else int(asset_ann["Year"].iloc[-1])
        c_kpi = C2 if cp_l > 80 else (C4 if cp_l > 65 else C5)
        st.markdown(f'<div class="kpi-card" style="border-left-color:{c_kpi}">'
                    f'<div class="kpi-lbl">Capture Rate — {kpi_yr}</div>'
                    f'<div class="kpi-val" style="color:{c_kpi}">{cp_l:.0f}%</div></div>',
                    unsafe_allow_html=True)
    with k3:
        sd_cur = (1-cp_l/100)*100
        c_sd   = C5 if sd_cur > 25 else (C3 if sd_cur > 15 else C2)
        st.markdown(f'<div class="kpi-card kpi-gold"><div class="kpi-lbl">Shape Discount</div>'
                    f'<div class="kpi-val" style="color:{c_sd}">{sd_cur:.1f}%</div></div>',
                    unsafe_allow_html=True)
    with k4:
        p50_pnl = vol_mwh*(ref_fwd*(1-float(np.percentile(hist_sd_f,50)))-ppa)/1000
        c_p = C2 if p50_pnl > 0 else C5
        st.markdown(f'<div class="kpi-card" style="border-left-color:{c_p}">'
                    f'<div class="kpi-lbl">P&L P50 (k EUR/yr)</div>'
                    f'<div class="kpi-val" style="color:{c_p}">{p50_pnl:+.0f}k</div></div>',
                    unsafe_allow_html=True)
    with k5:
        be_txt = f"P{be}" if be else ">P100"
        c_be   = C2 if be and be > 70 else C5
        st.markdown(f'<div class="kpi-card kpi-red"><div class="kpi-lbl">Break-even Cannibalization</div>'
                    f'<div class="kpi-val" style="color:{c_be}">{be_txt}</div></div>',
                    unsafe_allow_html=True)

    st.markdown("---")
    r1a, r1b = st.columns(2)

    with r1a:
        section("Historical Captured Price — 2014 onwards")
        desc("Bars: CP% by year. Gold bar = current year YTD (excluded from regression). Bottom panel: EUR/MWh.")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
                            subplot_titles=["CP% (% of spot average)","CP (EUR/MWh)"],
                            row_heights=[0.55,0.45])
        ny = nat_ref["year"].tolist(); ncp = nat_ref["cp_nat_pct"].tolist()
        ne = nat_ref["cp_nat"].tolist(); ns  = nat_ref["spot"].tolist()
        is_partial   = nat_ref["partial"].tolist() if "partial" in nat_ref.columns else [False]*len(ny)
        bar_colors   = ["rgba(255,215,0,0.55)" if p else "rgba(42,157,143,0.5)" for p in is_partial]
        bar_outlines = [C3 if p else C2 for p in is_partial]
        bar_texts    = [f"<b>{v*100:.0f}%</b>"+(" YTD" if p else "") for v,p in zip(ncp,is_partial)]
        fig.add_trace(go.Bar(x=ny, y=ncp, name="M0 National",
                             marker_color=bar_colors, marker_line_color=bar_outlines, marker_line_width=2,
                             text=bar_texts, textposition="outside",
                             textfont=dict(size=11, color=C1, family="Calibri")), row=1, col=1)
        if has_asset:
            ay=asset_ann["Year"].tolist(); acp=asset_ann["cp_pct"].tolist(); ae=asset_ann["cp_eur"].tolist()
            fig.add_trace(go.Bar(x=ay, y=acp, name=asset_name,
                                 marker_color=["rgba(231,111,81,0.6)"]*len(ay),
                                 marker_line_color=C5, marker_line_width=1.5,
                                 text=[f"<b>{v*100:.0f}%</b>" for v in acp], textposition="outside",
                                 textfont=dict(size=11,color=C5,family="Calibri")), row=1, col=1)
            fig.add_trace(go.Scatter(x=ay,y=ae,name=asset_name+" EUR",
                                     line=dict(color=C5,width=2.5),mode="lines+markers",
                                     marker=dict(size=8,color=C5,line=dict(width=1.5,color=WHT))), row=2, col=1)
        fig.add_trace(go.Scatter(x=ny,y=ncp,line=dict(color=C2,width=2.5,dash="dash"),
                                 mode="lines+markers",
                                 marker=dict(size=7,color=C2,symbol="square",line=dict(width=1.5,color=WHT)),
                                 showlegend=False), row=1, col=1)
        fig.add_hline(y=1.0, line=dict(color="#AAAAAA",width=1,dash="dot"), row=1, col=1)
        fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.25,line_width=0,row=1,col=1)
        fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.25,line_width=0,row=2,col=1)
        fig.add_annotation(x=2022,y=0.32,text="2022",showarrow=False,
                           font=dict(color=C3,size=13,family="Calibri"),row=1,col=1)
        fig.add_trace(go.Scatter(x=ny,y=ns,name="National Spot",
                                 line=dict(color="#555555",width=2,dash="dash"),mode="lines+markers",
                                 marker=dict(size=6,color="#555555")), row=2, col=1)
        fig.add_trace(go.Scatter(x=ny,y=ne,name="M0 National EUR",
                                 line=dict(color=C2,width=2.5),mode="lines+markers",
                                 marker=dict(size=7,color=C2,symbol="square",line=dict(width=1.5,color=WHT))),
                      row=2, col=1)
        fig.update_yaxes(tickformat=".0%", title_text="<b>CP% (% of spot average)</b>", row=1, col=1)
        fig.update_yaxes(title_text="<b>CP (EUR/MWh)</b>", row=2, col=1)
        fig.update_layout(barmode="group")
        plotly_base(fig, h=640)
        st.plotly_chart(fig, use_container_width=True)

    with r1b:
        section("Projection — Captured Price (%) with Uncertainty Bands")
        desc("Projection from last complete year. Regression excludes YTD.")
        fig2 = go.Figure()
        if has_asset:
            fig2.add_trace(go.Scatter(x=asset_ann["Year"].tolist(),y=asset_ann["cp_pct"].tolist(),
                                      name="Asset (historical)",mode="lines+markers+text",
                                      line=dict(color=C5,width=3),
                                      marker=dict(size=10,color=C5,line=dict(width=2,color=WHT)),
                                      text=[f"<b>{v*100:.0f}%</b>" for v in asset_ann["cp_pct"]],
                                      textposition="top center",
                                      textfont=dict(size=11,color=C5,family="Calibri")))
        fig2.add_trace(go.Scatter(x=nat_ref["year"].tolist(),y=nat_ref["cp_nat_pct"].tolist(),
                                  name="M0 National",mode="lines+markers",
                                  line=dict(color=C2,width=2.5,dash="dash"),
                                  marker=dict(size=8,color=C2,symbol="square",line=dict(width=1.5,color=WHT))))
        tx = list(range(2014, last_yr_proj+proj_n+1))
        fig2.add_trace(go.Scatter(x=tx,y=[1-(ic_u+sl_u*yr) for yr in tx],
                                  name="Trend",line=dict(color="#AAAAAA",width=2,dash="dot"),
                                  mode="lines",opacity=0.8))
        py_proj=proj["year"].tolist(); p10=proj["p10"].tolist(); p25=proj["p25"].tolist()
        p50=proj["p50"].tolist(); p75=proj["p75"].tolist(); p90=proj["p90"].tolist()
        fig2.add_trace(go.Scatter(x=py_proj+py_proj[::-1],y=p90+p10[::-1],
                                  fill="toself",fillcolor="rgba(255,215,0,0.20)",
                                  line=dict(color="rgba(0,0,0,0)"),name="P10-P90"))
        fig2.add_trace(go.Scatter(x=py_proj+py_proj[::-1],y=p75+p25[::-1],
                                  fill="toself",fillcolor="rgba(247,220,111,0.35)",
                                  line=dict(color="rgba(0,0,0,0)"),name="P25-P75"))
        hl = asset_ann["cp_pct"].iloc[-1] if has_asset else nat_ref_complete["cp_nat_pct"].iloc[-1]
        fig2.add_trace(go.Scatter(x=[last_yr_proj]+py_proj,y=[hl]+p50,
                                  name="P50 (central scenario)",mode="lines+markers",
                                  line=dict(color=C1,width=3),
                                  marker=dict(size=8,color=C1,line=dict(width=2,color=WHT))))
        for _,row in proj.iterrows():
            fig2.add_annotation(x=row["year"],y=row["p50"],
                                text=f"<b>P50:{row['p50']*100:.0f}%</b><br>P10:{row['p10']*100:.0f}%",
                                showarrow=True,arrowhead=2,arrowcolor=C1,arrowwidth=1.5,
                                font=dict(size=11,color=C1,family="Calibri"),
                                bgcolor="rgba(255,255,255,0.9)",bordercolor=C3,borderwidth=1,ax=32,ay=-40)
        fig2.add_vline(x=last_yr_proj+0.5,line=dict(color="#BBBBBB",width=1.5,dash="dot"))
        fig2.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.15,line_width=0)
        fig2.update_yaxes(tickformat=".0%")
        plotly_base(fig2, h=640)
        fig2.update_layout(
            title=dict(text=f"Slope: {-sl_u*100:.2f}%/yr — R²: {r2_u:.3f} {'(excl.2022)' if ex22 else ''} — excl. YTD",
                       font=dict(size=13,color=C2,family="Calibri"),x=0.5),
            yaxis=dict(range=[0.15,1.22]))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    section("Reference Table — Shape Discount and P&L by Percentile")
    desc("Complete years only — YTD excluded. P74 = WPD tender reference.")
    kp = [5,10,15,20,25,30,35,40,45,50,55,60,65,70,74,75,80,85,90,95,100]
    trows = []
    for p in kp:
        sdn = float(np.percentile(nat_ref_complete["shape_disc"].dropna(),p))
        sda = float(np.percentile(asset_ann["shape_disc"].dropna(),p)) if has_asset else None
        cpa = ref_fwd*(1-sda) if sda is not None else None
        pnla= vol_mwh*(cpa-ppa)/1000 if cpa is not None else None
        row = {"Pct":f"P{p}","Shape Disc National":f"{sdn*100:.1f}%","CP National":f"{(1-sdn)*100:.0f}%"}
        if has_asset:
            row["Shape Disc Asset"]=f"{sda*100:.1f}%"; row["CP Asset"]=f"{(1-sda)*100:.0f}%"
            row["P&L k EUR/yr"]=f"{pnla:+.0f}k"
        trows.append(row)
    tdf = pd.DataFrame(trows)
    def hi(row):
        p = int(row["Pct"][1:])
        if p == chosen_pct: return [f"background-color:{C2};color:white;font-weight:bold"]*len(row)
        if p in [10,50,90]:  return [f"background-color:{C2L}"]*len(row)
        if p == 74:          return [f"background-color:{C3L}"]*len(row)
        return [""]*len(row)
    st.dataframe(tdf.style.apply(hi, axis=1), use_container_width=True, height=440)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Forward Curve & Pricing
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    section("EEX Forward Curve — by Calendar Year")
    desc("Enter forward CAL prices. Formula: PPA = Forward × (1 - Shape Disc - Imbalance%) - Imbalance EUR.")
    col_i, col_r = st.columns([1,1.6])
    with col_i:
        fwd_rows_live = []
        for yr in range(last_yr_proj+1, last_yr_proj+proj_n+1):
            px = st.number_input(f"CAL {yr} (EUR/MWh)",10.0,200.0,
                                 float(DEFAULT_FORWARD.get(yr,52.0)),0.5,key=f"fwd_{yr}")
            fwd_rows_live.append({"year":yr,"forward":px})
        fwd_df_live = pd.DataFrame(fwd_rows_live)
        st.info("API connector coming soon.")
    with col_r:
        rows_ppa = []
        for _,row in fwd_df_live.iterrows():
            yr=row["year"]; fwd=row["forward"]; fsd=ic_u+sl_u*yr
            cp=fwd*(1-fsd); ppa_yr=fwd*(1-fsd-imb_eur/fwd)-imb_eur
            rows_ppa.append({"Year":int(yr),"Forward":f"{fwd:.2f}",
                             "Proj. Shape Disc":f"{fsd*100:.1f}%",
                             "Captured (EUR/MWh)":f"{cp:.2f}",
                             "PPA Price (EUR/MWh)":f"{ppa_yr:.2f}",
                             "P&L/MWh":f"{cp-ppa_yr:+.2f}"})
        st.dataframe(pd.DataFrame(rows_ppa), use_container_width=True, hide_index=True)
        fig_fwd = go.Figure()
        fig_fwd.add_trace(go.Bar(x=fwd_df_live["year"],y=fwd_df_live["forward"],
                                 marker_color="rgba(42,157,143,0.7)",marker_line_color=C2,marker_line_width=2,
                                 text=[f"<b>{v:.1f}</b>" for v in fwd_df_live["forward"]],
                                 textposition="outside",textfont=dict(size=14,color=C1,family="Calibri"),
                                 name="EEX Forward"))
        fig_fwd.update_yaxes(title_text="EUR/MWh")
        fig_fwd.update_xaxes(tickmode="array",tickvals=fwd_df_live["year"].tolist())
        plotly_base(fig_fwd, h=280, show_legend=False)
        fig_fwd.update_layout(title=dict(text="<b>Forward Price Curve</b>"))
        st.plotly_chart(fig_fwd, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Cannibalization & Market
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    section("Negative Price Hours — by Year")
    neg_ann = hourly[hourly["Spot"]<0].groupby("Year").size().reset_index(name="neg_hours")
    all_yrs = pd.DataFrame({"Year":sorted(hourly["Year"].unique())})
    neg_ann = all_yrs.merge(neg_ann,on="Year",how="left").fillna(0)
    neg_ann["neg_hours"] = neg_ann["neg_hours"].astype(int)
    bar_c = [C3 if yr in partial_years else (C5 if v>300 else (C4 if v>100 else C2))
             for v,yr in zip(neg_ann["neg_hours"],neg_ann["Year"])]
    fig_neg = go.Figure()
    fig_neg.add_trace(go.Bar(x=neg_ann["Year"],y=neg_ann["neg_hours"],
                             marker_color=bar_c,marker_line_color=WHT,marker_line_width=1,
                             text=[f"<b>{v}</b>"+(" YTD" if yr in partial_years else "")
                                   for v,yr in zip(neg_ann["neg_hours"],neg_ann["Year"])],
                             textposition="outside",textfont=dict(size=12,color=C1,family="Calibri"),
                             name="Negative Price Hours"))
    neg_c = neg_ann[~neg_ann["Year"].isin(partial_years)]
    if len(neg_c) >= 3:
        xn=neg_c["Year"].values.astype(float); yn=neg_c["neg_hours"].values.astype(float)
        sln,icn,*_ = stats.linregress(xn,yn)
        fut=list(range(int(xn.min()),int(xn.max())+4))
        fig_neg.add_trace(go.Scatter(x=fut,y=[max(0,icn+sln*yr) for yr in fut],
                                     mode="lines",line=dict(color=C5,width=2.5,dash="dash"),
                                     name=f"Trend ({sln:+.0f}h/yr)"))
    fig_neg.add_hline(y=15,line=dict(color=C2,width=1.5,dash="dot"),
                      annotation_text="CRE Threshold (15h)",
                      annotation_font=dict(color=C2,size=12,family="Calibri"))
    plotly_base(fig_neg, h=380)
    fig_neg.update_layout(title=dict(text="<b>Negative Price Hours by Year</b>"))
    st.plotly_chart(fig_neg, use_container_width=True)

    st.markdown("---")
    c3a, c3b = st.columns(2)
    with c3a:
        section("Monthly Cannibalization Profile")
        monthly = hourly.copy()
        monthly["Rev_nat"] = monthly["NatMW"]*monthly["Spot"]
        monthly_agg = monthly[monthly["Spot"]>0].groupby(["Year","Month"]).agg(
            spot_avg=("Spot","mean"),prod_nat=("NatMW","sum"),rev_nat=("Rev_nat","sum")).reset_index()
        monthly_agg["m0"]   = monthly_agg["rev_nat"]/monthly_agg["prod_nat"].replace(0,np.nan)
        monthly_agg["sd_m"] = 1-monthly_agg["m0"]/monthly_agg["spot_avg"]
        month_avg = monthly_agg.groupby("Month")["sd_m"].agg(["mean","std"]).reset_index()
        bar_c_m = [C5 if v>0.15 else (C4 if v>0.08 else C2) for v in month_avg["mean"]]
        fig_mo = go.Figure()
        fig_mo.add_trace(go.Bar(x=MONTH_NAMES,y=month_avg["mean"],
                                error_y=dict(type="data",array=month_avg["std"].tolist(),
                                             visible=True,color="#AAAAAA",thickness=2,width=5),
                                marker_color=bar_c_m,marker_line_color=WHT,marker_line_width=1,
                                text=[f"<b>{v*100:.1f}%</b>" for v in month_avg["mean"]],
                                textposition="outside",textfont=dict(size=11,color=C1,family="Calibri")))
        fig_mo.add_hline(y=0,line=dict(color="#AAAAAA",width=1))
        fig_mo.update_yaxes(tickformat=".0%",title_text="Average Shape Discount")
        plotly_base(fig_mo, h=380, show_legend=False)
        fig_mo.update_layout(title=dict(text="<b>Monthly Cannibalization Profile</b>"))
        st.plotly_chart(fig_mo, use_container_width=True)

    with c3b:
        section("Scatter — CP% vs National Solar Capacity")
        nat_mw_ann = hourly.groupby("Year")["NatMW"].mean().reset_index()
        sc_df = nat_ref.merge(nat_mw_ann.rename(columns={"Year":"year"}),on="year",how="inner")
        sc_df = sc_df[sc_df["NatMW"]>0]
        pt_col = [C3 if r.get("partial",False) else (C5 if r["year"]>=2024 else (C3 if r["year"]==2022 else C2))
                  for _,r in sc_df.iterrows()]
        fig_sc = go.Figure()
        fig_sc.add_trace(go.Scatter(x=sc_df["NatMW"],y=sc_df["cp_nat_pct"],
                                    mode="markers+text",marker=dict(size=16,color=pt_col,line=dict(width=2,color=WHT)),
                                    text=[f"<b>{int(y)}</b>" for y in sc_df["year"]],
                                    textposition="top center",textfont=dict(size=11,color=C1,family="Calibri"),
                                    name="M0 National"))
        sc_c = sc_df[~sc_df["year"].isin(partial_years)]
        if len(sc_c) >= 3:
            sl_sc,ic_sc,r_sc,_,_ = stats.linregress(sc_c["NatMW"].values,sc_c["cp_nat_pct"].values)
            xl = np.linspace(0,75000,200)
            fig_sc.add_trace(go.Scatter(x=xl,y=ic_sc+sl_sc*xl,mode="lines",
                                        line=dict(color="#AAAAAA",width=2,dash="dash"),
                                        name=f"Regression (R²={r_sc**2:.2f})"))
        for gw,lbl,col in [(48000,"PPE3 2030",C4),(65000,"PPE3 2035",C5)]:
            fig_sc.add_vline(x=gw,line=dict(color=col,width=2,dash="dot"))
            fig_sc.add_annotation(x=gw,y=sc_df["cp_nat_pct"].min()*0.94,text=f"<b>{lbl}</b>",
                                  font=dict(color=col,size=11,family="Calibri"),showarrow=False,xanchor="left")
        fig_sc.update_yaxes(tickformat=".0%",title_text="Captured Price (% of spot)")
        fig_sc.update_xaxes(title_text="National Solar Capacity (MW)")
        plotly_base(fig_sc, h=380)
        fig_sc.update_layout(title=dict(text="<b>CP% vs Solar Capacity</b>"))
        st.plotly_chart(fig_sc, use_container_width=True)

    st.markdown("---")
    section("Annual Shape Discount Change")
    sd_s = nat_ref[["year","shape_disc"]].dropna().sort_values("year")
    sd_s["delta"] = sd_s["shape_disc"].diff()
    sd_s = sd_s.dropna(subset=["delta"])
    fig_wfall = go.Figure()
    fig_wfall.add_trace(go.Bar(x=sd_s["year"],y=sd_s["delta"],
                               marker_color=[C5 if v>0 else C2 for v in sd_s["delta"]],
                               marker_line_color=WHT,marker_line_width=1,
                               text=[f"<b>{v*100:+.1f}pp</b>" for v in sd_s["delta"]],
                               textposition="outside",textfont=dict(size=12,color=C1,family="Calibri")))
    fig_wfall.add_hline(y=0,line=dict(color="#AAAAAA",width=1.5))
    fig_wfall.update_yaxes(tickformat=".1%",title_text="Delta Shape Discount (pp)")
    plotly_base(fig_wfall, h=340, show_legend=False)
    fig_wfall.update_layout(title=dict(text="<b>Annual Shape Discount Change</b>"))
    st.plotly_chart(fig_wfall, use_container_width=True)

    st.markdown("---")
    section("Heatmap — Monthly Shape Discount by Year")
    pivot = monthly_agg.pivot(index="Year",columns="Month",values="sd_m")
    pivot.columns = [MONTH_NAMES[c-1] for c in pivot.columns]
    fig_hm = go.Figure(data=go.Heatmap(
        z=pivot.values*100,x=pivot.columns.tolist(),y=pivot.index.tolist(),
        colorscale=[[0,C2],[0.5,C3],[1,C5]],
        text=[[f"<b>{v:.1f}%</b>" for v in row] for row in pivot.values*100],
        texttemplate="%{text}",textfont=dict(size=11,color=C1,family="Calibri"),
        colorbar=dict(title=dict(text="Shape Disc (%)",font=dict(size=12,color=C1)),
                      tickfont=dict(size=11,color=C1),thickness=14)))
    fig_hm.update_xaxes(title_text="Month"); fig_hm.update_yaxes(title_text="Year")
    plotly_base(fig_hm, h=400, show_legend=False)
    fig_hm.update_layout(title=dict(text="<b>Monthly Shape Discount Heatmap</b>"))
    st.plotly_chart(fig_hm, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Sensitivity & Scenarios
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    section("Annual P&L by Cannibalization Percentile")
    fig3 = go.Figure()
    px_=[p for p,v in zip(pcts,pnl_v) if v>=0]; py_=[v for v in pnl_v if v>=0]
    nx_=[p for p,v in zip(pcts,pnl_v) if v<0];  ny_=[v for v in pnl_v if v<0]
    if px_: fig3.add_trace(go.Scatter(x=px_,y=py_,fill="tozeroy",fillcolor="rgba(42,157,143,0.15)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    if nx_: fig3.add_trace(go.Scatter(x=nx_,y=ny_,fill="tozeroy",fillcolor="rgba(231,111,81,0.15)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    fig3.add_trace(go.Scatter(x=pcts,y=pnl_v,name="P&L (k EUR/yr)",mode="lines",line=dict(color=C1,width=3)))
    pc_=pnl_v[chosen_pct-1]
    fig3.add_trace(go.Scatter(x=[chosen_pct],y=[pc_],mode="markers+text",
                              marker=dict(size=16,color=C2 if pc_>=0 else C5,line=dict(width=2.5,color=WHT)),
                              text=[f"<b>P{chosen_pct}: {pc_:.0f}k</b>"],textposition="top right",
                              name=f"P{chosen_pct} Selected",textfont=dict(size=12,color=C1,family="Calibri")))
    pu =[vol_mwh*(1+vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    pd_=[vol_mwh*(1-vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    fig3.add_trace(go.Scatter(x=pcts+pcts[::-1],y=pu+pd_[::-1],
                              fill="toself",fillcolor="rgba(255,215,0,0.25)",
                              line=dict(color="rgba(0,0,0,0)"),name=f"±{vol_stress}% Volume"))
    fig3.add_hline(y=0,line=dict(color="#AAAAAA",width=2))
    if be:
        fig3.add_vline(x=be,line=dict(color=C5,width=2,dash="dot"),
                       annotation_text=f"<b>Break-even P{be}</b>",
                       annotation_font=dict(color=C5,size=12,family="Calibri"))
    fig3.update_layout(xaxis_title="Shape Discount Percentile",yaxis_title="Annual P&L (k EUR)")
    plotly_base(fig3, h=450)
    fig3.update_layout(title=dict(text="<b>P&L Distribution by Cannibalization Percentile</b>"))
    st.plotly_chart(fig3, use_container_width=True)
    if be: st.warning(f"Break-even at P{be}.")

    st.markdown("---")
    section(f"Stress Scenarios — Cumulative P&L over {proj_n} Years")
    sd_med = float(np.percentile(hist_sd_f,50)) if len(hist_sd_f)>0 else 0.15
    scens = [
        ("Base",1.00,0.00,0.00),
        (f"Cannib +{vol_stress}%",1.00,+vol_stress/100,0.00),
        (f"Cannib -{vol_stress}%",1.00,-vol_stress/100,0.00),
        (f"Spot +{spot_stress}%",1+spot_stress/100,0.00,0.00),
        (f"Spot -{spot_stress}%",1-spot_stress/100,0.00,0.00),
        (f"Vol +{vol_stress}%",1.00,0.00,+vol_stress/100),
        (f"Vol -{vol_stress}%",1.00,0.00,-vol_stress/100),
        ("Total Stress",1-spot_stress/100,+vol_stress/100,-vol_stress/100),
        ("Total Bull",1+spot_stress/100,-vol_stress/100,+vol_stress/100),
    ]
    sn,sv50,sv10,sv90=[],[],[],[]
    scenarios_export=[]
    for name,sm,da,va in scens:
        p50t=vol_mwh*(1+va)*(sm*ref_fwd*(1-(sd_med+da))-ppa)/1000*proj_n
        sdp10=float(np.percentile(hist_sd_f,10))+da if len(hist_sd_f)>0 else 0.1
        sdp90=float(np.percentile(hist_sd_f,90))+da if len(hist_sd_f)>0 else 0.3
        p10t=vol_mwh*(1+va)*(sm*ref_fwd*(1-sdp90)-ppa)/1000*proj_n
        p90t=vol_mwh*(1+va)*(sm*ref_fwd*(1-sdp10)-ppa)/1000*proj_n
        sn.append(name);sv50.append(p50t);sv10.append(p10t);sv90.append(p90t)
        scenarios_export.append({"Scenario":name,"P10 (k EUR)":f"{p10t:+.0f}k",
                                  "P50 (k EUR)":f"{p50t:+.0f}k","P90 (k EUR)":f"{p90t:+.0f}k"})
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(name="P50",x=sn,y=sv50,
                          marker_color=["rgba(42,157,143,0.80)" if v>=0 else "rgba(231,111,81,0.80)" for v in sv50],
                          marker_line_color=WHT,marker_line_width=1,
                          text=[f"<b>{v:+.0f}k</b>" for v in sv50],textposition="outside",
                          textfont=dict(size=12,color=C1,family="Calibri")))
    fig4.add_trace(go.Scatter(name="P10",x=sn,y=sv10,mode="markers",
                              marker=dict(symbol="triangle-down",size=14,color=C5,line=dict(width=2,color=WHT))))
    fig4.add_trace(go.Scatter(name="P90",x=sn,y=sv90,mode="markers",
                              marker=dict(symbol="triangle-up",size=14,color=C2,line=dict(width=2,color=WHT))))
    fig4.add_hline(y=0,line=dict(color="#AAAAAA",width=2))
    fig4.update_layout(xaxis_title="Scenario",yaxis_title=f"Cumulative P&L {proj_n}yr (k EUR)",bargap=0.35)
    plotly_base(fig4, h=420)
    fig4.update_layout(title=dict(text=f"<b>Stress Scenarios — {proj_n} Year P&L</b>"))
    st.plotly_chart(fig4, use_container_width=True)
    st.markdown("---")
    section("Scenario Details")
    st.dataframe(pd.DataFrame(scenarios_export), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Price Waterfall
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    section("PPA Price Waterfall — Component Breakdown")
    baseload=ref_fwd; shape_disc_eur=ref_fwd*sd_ch; vol_risk_eur=ref_fwd*0.025
    price_risk_eur=ref_fwd*0.03; cannib_risk_eur=ref_fwd*0.02; balancing=imb_eur; goo_value=3.0
    final_ppa=baseload-shape_disc_eur-vol_risk_eur-price_risk_eur-cannib_risk_eur-balancing+goo_value
    wf_data=[("Baseload Forward",baseload,"absolute"),("Shape Discount",-shape_disc_eur,"relative"),
             ("Volume Risk",-vol_risk_eur,"relative"),("Price Risk",-price_risk_eur,"relative"),
             ("Cannib. Risk",-cannib_risk_eur,"relative"),("Balancing Cost",-balancing,"relative"),
             ("GoO Value",goo_value,"relative"),("PPA Price",0,"total")]
    fig_wf2=go.Figure(go.Waterfall(name="",orientation="v",
        measure=[d[2] for d in wf_data],x=[d[0] for d in wf_data],y=[d[1] for d in wf_data],
        text=[f"{d[1]:+.1f}" if d[2]=="relative" else f"{d[1]:.1f}" if d[2]=="absolute" else "" for d in wf_data],
        textposition="outside",textfont=dict(size=13,color=C1,family="Calibri"),
        connector=dict(line=dict(color="#AAAAAA",width=1.5)),
        decreasing=dict(marker=dict(color=C5,line=dict(color=WHT,width=1))),
        increasing=dict(marker=dict(color=C2,line=dict(color=WHT,width=1))),
        totals=dict(marker=dict(color=C3,line=dict(color=WHT,width=2)))))
    fig_wf2.update_xaxes(tickangle=-30)
    plotly_base(fig_wf2, h=500, show_legend=False)
    fig_wf2.update_layout(title=dict(text="<b>PPA Price Waterfall — From Baseload to Contract</b>"),yaxis_title="EUR/MWh")
    st.plotly_chart(fig_wf2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — Market Evolution
# ══════════════════════════════════════════════════════════════════════════════

with tab6:
    st.markdown("## Market Evolution — Rolling Capture Rate")
    desc(
        "All metrics computed on RAW hourly data over rolling windows of 30, 90 and 365 days. "
        "For each day t:   M0(t) = sum(NatMW × Spot) / sum(NatMW)   over the last N×24 hours. "
        "Baseload(t) = sum(Spot) / count(hours)   over the same window. "
        "CP%(t) = M0(t) / Baseload(t). "
        "This is NOT a mean of daily ratios — every raw hourly observation counts."
    )

    with st.spinner("Computing rolling windows on hourly data — please wait..."):
        roll = compute_rolling_m0(hourly, windows=(30, 90, 365))

    if roll is None or len(roll) < 10:
        st.warning("Not enough data to compute rolling windows.")
    else:
        W_COLOR = {30: C2,       90: C3,      365: C1}
        W_DASH  = {30: "dot",    90: "dash",  365: "solid"}
        W_WIDTH = {30: 1.5,      90: 2.0,     365: 2.5}

        ann_x = [pd.Timestamp(f"{int(y)}-07-01") for y in nat_ref_complete["year"]]

        # ── Chart 1 — CP% ─────────────────────────────────────────────────────
        section("Rolling Capture Rate — M0 / Baseload (%)")
        desc(
            "Solar weighted-average price as % of simple average spot (baseload). "
            "100% = no cannibalization. "
            "30d (teal dotted) = short-term. 365d (dark blue solid) = structural trend. "
            "Diamond markers = annual M0 from complete years. Star = YTD."
        )

        fig_cp = go.Figure()
        fig_cp.add_hline(y=1.0, line=dict(color="#CCCCCC", width=1.5, dash="dot"),
                         annotation_text="100% — no cannibalization",
                         annotation_font=dict(color="#999999", size=11, family="Calibri"),
                         annotation_position="top left")

        for w in [365, 90, 30]:
            col = f"cp_{w}d"
            d = roll.dropna(subset=[col])
            if len(d) == 0:
                continue
            fig_cp.add_trace(go.Scatter(
                x=d["Date"], y=d[col],
                name=f"{w}d rolling",
                mode="lines",
                line=dict(color=W_COLOR[w], width=W_WIDTH[w], dash=W_DASH[w]),
            ))

        fig_cp.add_trace(go.Scatter(
            x=ann_x, y=nat_ref_complete["cp_nat_pct"].tolist(),
            name="Annual M0 (complete years)", mode="markers",
            marker=dict(size=11, color=C5, symbol="diamond", line=dict(width=2, color=WHT)),
        ))

        for _, ytd_row in nat_ref[nat_ref["partial"] == True].iterrows():
            fig_cp.add_trace(go.Scatter(
                x=[pd.Timestamp(f"{int(ytd_row['year'])}-04-01")],
                y=[ytd_row["cp_nat_pct"]],
                name=f"{int(ytd_row['year'])} YTD",
                mode="markers+text",
                marker=dict(size=13, color=C3, symbol="star", line=dict(width=2, color=C1)),
                text=[f"<b>{int(ytd_row['year'])} YTD: {ytd_row['cp_nat_pct']*100:.0f}%</b>"],
                textposition="top right",
                textfont=dict(size=11, color=C1, family="Calibri"),
            ))

        fig_cp.update_yaxes(tickformat=".0%", title_text="Capture Rate  M0 / Baseload")
        fig_cp.update_xaxes(title_text="Date")
        plotly_base(fig_cp, h=500)
        fig_cp.update_layout(title=dict(text="<b>Rolling Capture Rate — WAP / Baseload (%)</b>"))
        st.plotly_chart(fig_cp, use_container_width=True)

        st.markdown("---")

        # ── Chart 2 — EUR/MWh ─────────────────────────────────────────────────
        section("Rolling Captured Price — M0 (EUR/MWh)")
        desc(
            "Absolute M0 in EUR/MWh over rolling windows. "
            "Grey dashed = baseload 365d (for reference). "
            "Gap between baseload and M0 = shape discount in EUR/MWh. "
            "A widening gap even when spot rises signals growing cannibalization."
        )

        fig_eur = go.Figure()

        bl_365 = roll.dropna(subset=["bl_365d"])
        if len(bl_365) > 0:
            fig_eur.add_trace(go.Scatter(
                x=bl_365["Date"], y=bl_365["bl_365d"],
                name="Baseload 365d (ref)",
                mode="lines",
                line=dict(color="#AAAAAA", width=2, dash="dash"),
            ))

        for w in [365, 90, 30]:
            col = f"m0_{w}d"
            d = roll.dropna(subset=[col])
            if len(d) == 0:
                continue
            fig_eur.add_trace(go.Scatter(
                x=d["Date"], y=d[col],
                name=f"M0 {w}d",
                mode="lines",
                line=dict(color=W_COLOR[w], width=W_WIDTH[w], dash=W_DASH[w]),
            ))

        fig_eur.add_trace(go.Scatter(
            x=ann_x, y=nat_ref_complete["cp_nat"].tolist(),
            name="Annual M0 (complete years)", mode="markers",
            marker=dict(size=11, color=C5, symbol="diamond", line=dict(width=2, color=WHT)),
        ))

        fig_eur.update_yaxes(title_text="EUR/MWh")
        fig_eur.update_xaxes(title_text="Date")
        plotly_base(fig_eur, h=500)
        fig_eur.update_layout(title=dict(text="<b>Rolling Captured Price M0 (EUR/MWh)</b>"))
        st.plotly_chart(fig_eur, use_container_width=True)

        st.markdown("---")

        # ── Summary table ─────────────────────────────────────────────────────
        section("Recent Period Summary")
        desc("Values computed on raw hourly data for the last 30, 90 and 365 days.")

        latest_date = pd.to_datetime(hourly["Date"]).max().normalize()
        sum_rows = []
        for w in [30, 90, 365]:
            cutoff  = latest_date - pd.Timedelta(days=w)
            h_slice = hourly[pd.to_datetime(hourly["Date"]).dt.normalize() > cutoff]
            if len(h_slice) < w * 12:
                continue
            sum_rev  = (h_slice["NatMW"] * h_slice["Spot"]).sum()
            sum_prod = h_slice["NatMW"].sum()
            sum_spot = h_slice["Spot"].sum()
            n_h      = len(h_slice)
            m0_val   = sum_rev / sum_prod if sum_prod > 0 else np.nan
            bl_val   = sum_spot / n_h
            cp_val   = m0_val / bl_val if bl_val else np.nan
            sum_rows.append({
                "Window":                  f"Last {w} days",
                "From":                    cutoff.strftime("%d/%m/%Y"),
                "To":                      latest_date.strftime("%d/%m/%Y"),
                "Baseload (EUR/MWh)":      f"{bl_val:.2f}",
                "M0 Captured (EUR/MWh)":   f"{m0_val:.2f}",
                "Capture Rate":            f"{cp_val*100:.1f}%",
                "Shape Discount":          f"{(1-cp_val)*100:.1f}%",
            })

        if sum_rows:
            def hi_sum(row):
                if "365" in row["Window"]: return [f"background-color:{C2L}"]*len(row)
                if "90"  in row["Window"]: return [f"background-color:{C3L}"]*len(row)
                return [""]*len(row)
            st.dataframe(pd.DataFrame(sum_rows).style.apply(hi_sum, axis=1),
                         use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — Export & SPOT Extractor
# ══════════════════════════════════════════════════════════════════════════════

with tab7:
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        section("Excel Export — All Dashboard Data")
        if st.button("Generate Excel File"):
            with st.spinner("Generating..."):
                excel_buf = build_excel(nat_ref,hourly,asset_ann,has_asset,asset_name,
                                        proj,pnl_v,ppa,scenarios_export,fwd_curve,
                                        nat_ref_complete["shape_disc"].dropna().values)
                st.download_button(label="Download ppa_dashboard_export.xlsx",data=excel_buf,
                                   file_name="ppa_dashboard_export.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.success("File ready.")
    with col_e2:
        section("Expected Load Curve Format")
        st.code("Date,Prod_MWh\n2024-01-01 00:00:00,0.0\n2024-01-01 10:00:00,4.2", language="text")

    st.markdown("---")
    section("SPOT Data Extractor — ENTSO-E")
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        api_key_in = st.text_input("ENTSO-E API Key", type="password")
        country_c  = st.selectbox("Country",["FR","DE","ES","BE","NL","IT","GB"],index=0)
        d_start    = st.date_input("Start Date", value=pd.Timestamp("2024-01-01"))
        d_end      = st.date_input("End Date",   value=pd.Timestamp("2024-12-31"))
        incl_solar = st.checkbox("Include Solar Production (NatMW)", value=True)
    with col_ex2:
        st.code("Date,Year,Month,Hour,Spot,NatMW\n2024-01-01 00:00:00,2024,1,0,52.3,1250.0", language="text")
        if api_key_in and st.button("Extract Data", key="extract_btn"):
            with st.spinner("Connecting to ENTSO-E..."):
                try:
                    from entsoe import EntsoePandasClient
                    import time
                    client=EntsoePandasClient(api_key=api_key_in)
                    start=pd.Timestamp(d_start,tz="Europe/Paris")
                    end  =pd.Timestamp(d_end,tz="Europe/Paris")+pd.Timedelta(days=1)
                    prices=client.query_day_ahead_prices(country_c,start=start,end=end)
                    prices=prices.resample("1h").mean()
                    df_out=pd.DataFrame({"Spot":prices}).reset_index()
                    df_out.columns=["Date","Spot"]
                    df_out["Date"]=df_out["Date"].dt.tz_localize(None)
                    df_out["Year"]=df_out["Date"].dt.year; df_out["Month"]=df_out["Date"].dt.month
                    df_out["Hour"]=df_out["Date"].dt.hour; df_out["NatMW"]=0.0
                    if incl_solar:
                        try:
                            time.sleep(1)
                            solar=client.query_generation(country_c,start=start,end=end,psr_type="B16")
                            if isinstance(solar,pd.DataFrame): solar=solar.sum(axis=1)
                            solar=solar.resample("1h").mean(); solar.index=solar.index.tz_localize(None)
                            df_out=df_out.set_index("Date").join(solar.rename("NatMW_n"),how="left")
                            df_out["NatMW"]=df_out["NatMW_n"].fillna(0)
                            df_out=df_out.drop(columns=["NatMW_n"]).reset_index()
                        except Exception as e2: st.warning(f"Solar unavailable: {e2}")
                    df_out=df_out[["Date","Year","Month","Hour","Spot","NatMW"]].dropna(subset=["Spot"])
                    st.success(f"{len(df_out):,} hours extracted")
                    st.dataframe(df_out.head(24), use_container_width=True)
                    st.download_button("Download CSV",data=df_out.to_csv(index=False).encode("utf-8"),
                                       file_name=f"spot_{country_c}_{d_start}_{d_end}.csv",mime="text/csv")
                except ImportError: st.error("entsoe-py not installed.")
                except Exception as e: st.error(f"ENTSO-E Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("---")
ytd_note = " — 2026 YTD included (excl. regression)" if partial_years else ""
st.markdown(
    f'<span style="font-size:12px;color:#888;font-family:Calibri,Arial,sans-serif;">'
    f' v2.2 — ENTSO-E France {data_start.year}–{data_end.strftime("%Y-%m-%d")} '
    f'— {len(hourly):,} hours{ytd_note} — '
    f'Daily automatic updates (GitHub Actions) — '
    f'Rolling M0: sum(NatMW×Spot)/sum(NatMW) on raw hourly windows'
    f'</span>', unsafe_allow_html=True)
