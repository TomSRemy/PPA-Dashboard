"""
PPA Pricing Dashboard — France Solaire  v5
Palette retro : #1D3A4A #2A9D8F #E9C46A #F4A261 #E76F51
Contrast rules strictes — texte lisible partout.
Font Calibri 14px base.
Pas d'emojis. Description sous chaque graphique.
"""

import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import io

st.set_page_config(page_title="PPA Pricing Dashboard",
                   layout="wide", initial_sidebar_state="expanded")

# ── Palette ────────────────────────────────────────────────────────────────────
C1  = "#E9C46A"   # jaune doré"      → sidebar, headers, texte sur fond clair
C2  = "#2A9D8F"   # teal           → positif, PPA price, section titles
C3  = "#1D3A4A"   # bleu nuit     → warnings, highlights → texte C1 obligatoire
C4  = "#F4A261"   # orange         → attention, stress → texte C1 obligatoire
C5  = "#E76F51"   # rouge brique   → pertes, négatif → texte blanc

# Fonds dérivés (très clairs pour les cartes)
BG  = "#F7F4F0"   # fond page
C2L = "#D4EDEA"   # teal clair
C3L = "#FBF3D9"   # jaune clair
C4L = "#FDE8D4"   # orange clair
C5L = "#FAEAE6"   # rouge clair
WHT = "#FFFFFF"

# Règle stricte : texte sur fond coloré
# Fond C1(dark)/C2(dark)/C5(dark) → texte blanc
# Fond C3(light)/C4(light) → texte C1 (bleu nuit, très lisible)

st.markdown(f"""<style>
html, body, [class*="css"] {{
    font-family: Calibri, 'Segoe UI', Arial, sans-serif !important;
    font-size: 15px !important;
    background-color: {BG} !important;
}}
h1 {{ font-size: 22px !important; font-weight: 700 !important;
      color: {C1} !important; font-family: Calibri, Arial, sans-serif !important; }}
h2 {{ font-size: 17px !important; font-weight: 700 !important; color: {C1} !important; }}
h3 {{ font-size: 15px !important; font-weight: 700 !important; color: {C1} !important; }}
p, li, label, .stMarkdown, td, th {{
    font-family: Calibri, Arial, sans-serif !important;
    font-size: 14px !important;
    color: {C1} !important;
}}
.section-title {{
    font-size: 13px !important; font-weight: 700;
    color: {WHT}; background: {C1};
    padding: 6px 12px; border-radius: 4px;
    margin: 20px 0 8px 0; letter-spacing: 0.05em;
    text-transform: uppercase; display: block;
}}
.chart-desc {{
    font-size: 13px !important; color: {C1} !important;
    background: {C3L}; border-left: 4px solid {C3};
    padding: 8px 12px; border-radius: 0 4px 4px 0;
    margin: 0 0 14px 0; line-height: 1.6;
    font-family: Calibri, Arial, sans-serif;
}}
.ppa-card {{
    background: {C2}; color: {WHT};
    padding: 18px 20px; border-radius: 8px; text-align: center;
}}
.ppa-card .val {{
    font-size: 28px; font-weight: 700; color: {WHT} !important;
    font-family: Calibri, Arial, sans-serif;
}}
.ppa-card .lbl {{
    font-size: 12px; color: {WHT} !important; opacity: 0.9;
    text-transform: uppercase; letter-spacing: 0.05em;
}}
.kpi-card {{
    background: {WHT}; border-left: 5px solid {C2};
    padding: 12px 16px; border-radius: 4px;
    border-top: 1px solid #E0E0E0;
    border-right: 1px solid #E0E0E0;
    border-bottom: 1px solid #E0E0E0;
}}
.kpi-val {{
    font-size: 22px; font-weight: 700;
    color: {C1}; font-family: Calibri, Arial, sans-serif;
}}
.kpi-lbl {{
    font-size: 11px; color: #555;
    text-transform: uppercase; letter-spacing: 0.04em;
}}
.kpi-red {{ border-left-color: {C5} !important; }}
.kpi-ora {{ border-left-color: {C4} !important; }}
.kpi-yel {{ border-left-color: {C3} !important; }}
.update-pill {{
    background: {C2L}; border: 1px solid {C2};
    border-radius: 20px; padding: 4px 14px;
    font-size: 12px; color: {C1}; display: inline-block;
    font-family: Calibri, Arial, sans-serif;
}}
.tbl-note {{
    font-size: 12px; color: #555; font-style: italic; margin-top: 4px;
    font-family: Calibri, Arial, sans-serif;
}}
[data-testid="stSidebar"] {{
    background: {C1} !important;
}}
[data-testid="stSidebar"] * {{
    color: {WHT} !important;
    font-family: Calibri, Arial, sans-serif !important;
}}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] p {{
    color: #C8DCE6 !important;
    font-size: 13px !important;
}}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    color: {WHT} !important;
    font-size: 15px !important;
}}
[data-testid="stSidebar"] .stSlider [data-testid="stThumbValue"] {{
    color: {C1} !important;
}}
.stTabs [data-baseweb="tab"] {{
    font-family: Calibri, Arial, sans-serif !important;
    font-size: 14px !important; font-weight: 600;
    color: {C1} !important;
}}
.stTabs [aria-selected="true"] {{
    border-bottom: 3px solid {C2} !important;
    color: {C2} !important;
}}
div[data-testid="stDataFrame"] td,
div[data-testid="stDataFrame"] th {{
    font-family: Calibri, Arial, sans-serif !important;
    font-size: 13px !important;
    color: {C1} !important;
}}
.stButton > button {{
    background: {C2} !important; color: {WHT} !important;
    border: none !important; border-radius: 4px !important;
    font-family: Calibri, Arial, sans-serif !important;
    font-size: 14px !important; font-weight: 600 !important;
    padding: 8px 20px !important;
}}
.stButton > button:hover {{
    background: {C1} !important;
}}
.stDownloadButton > button {{
    background: {C4} !important; color: {C1} !important;
    border: none !important; font-weight: 700 !important;
}}
</style>""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_FORWARD = {2026:55.0,2027:54.0,2028:53.0,2029:52.0,2030:51.0}
MONTH_NAMES     = ["Jan","Fev","Mar","Avr","Mai","Jun",
                   "Jul","Aou","Sep","Oct","Nov","Dec"]

def section(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)

def desc(text):
    st.markdown(f'<div class="chart-desc">{text}</div>', unsafe_allow_html=True)

def plotly_base(fig, h=400, show_legend=True):
    """Apply consistent Calibri styling to all Plotly charts."""
    fig.update_layout(
        height=h,
        plot_bgcolor=WHT,
        paper_bgcolor=BG,
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Calibri, Arial, sans-serif", size=14, color=C1),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=13, color=C1),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#DDDDDD", borderwidth=1,
        ) if show_legend else dict(visible=False),
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#EEEEEE", gridwidth=1,
        linecolor="#CCCCCC", linewidth=1,
        tickfont=dict(family="Calibri, Arial", size=13, color=C1),
        title_font=dict(family="Calibri, Arial", size=14, color=C1),
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="#EEEEEE", gridwidth=1,
        linecolor="#CCCCCC", linewidth=1,
        tickfont=dict(family="Calibri, Arial", size=13, color=C1),
        title_font=dict(family="Calibri, Arial", size=14, color=C1),
    )

# ══════════════════════════════════════════════════════════════════════════════
#  DATA
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)
def load_nat():
    return pd.read_csv(DATA_DIR / "nat_reference.csv")

@st.cache_data(ttl=3600)
def load_hourly():
    df = pd.read_csv(DATA_DIR / "hourly_spot.csv", parse_dates=["Date"])
    df["Month"] = df["Date"].dt.month
    return df

def load_log():
    p = DATA_DIR / "last_update.txt"
    return p.read_text() if p.exists() else "Donnees initiales."

def compute_asset_annual(hourly, asset_df):
    a = asset_df.copy()
    a["Date"] = pd.to_datetime(a["Date"])
    a = a.set_index("Date").resample("1h").mean().reset_index()
    m = hourly.merge(a[["Date","Prod_MWh"]], on="Date", how="inner")
    m = m[m["Spot"]>0].copy()
    m["Rev"] = m["Prod_MWh"] * m["Spot"]
    ann = m.groupby("Year").agg(
        prod_mwh  =("Prod_MWh","sum"), revenue=("Rev","sum"),
        spot_avg  =("Spot","mean"),
        prod_hours=("Prod_MWh",lambda x:(x>0).sum()),
        neg_hours =("Spot",lambda x:(x<0).sum()),
        nat_mw    =("NatMW","mean"),
    ).reset_index()
    ann["prod_gwh"]   = ann["prod_mwh"]/1000
    ann["cp_eur"]     = ann["revenue"]/ann["prod_mwh"].replace(0,np.nan)
    ann["cp_pct"]     = ann["cp_eur"]/ann["spot_avg"]
    ann["shape_disc"] = 1-ann["cp_pct"]
    return ann.dropna(subset=["cp_pct"])

def fit_reg(ann, n, ex22):
    d = ann.copy()
    if ex22: d = d[d["Year"]!=2022]
    d = d.tail(n).dropna(subset=["shape_disc"])
    if len(d)<2: d = ann.dropna(subset=["shape_disc"])
    if len(d)<2: return 0.0, ann["shape_disc"].mean() if len(ann) else 0.15, 0.0
    x=d["Year"].values.astype(float); y=d["shape_disc"].values
    sl,ic,r,_,_=stats.linregress(x,y)
    return sl,ic,r**2

def project_cp(sl,ic,last_yr,n=5,sig=0.04):
    rows=[]
    for t,yr in enumerate(range(last_yr+1,last_yr+n+1)):
        fsd=ic+sl*yr; cs=sig*np.sqrt(t+1)
        rows.append({"year":yr,"fsd":fsd,
                     "p10":1-(fsd+1.28*cs),"p25":1-(fsd+0.674*cs),
                     "p50":1-fsd,
                     "p75":1-(fsd-0.674*cs),"p90":1-(fsd-1.28*cs)})
    return pd.DataFrame(rows)

def build_excel(nat_ref,hourly,asset_ann,has_asset,asset_name,
                proj,pnl_v,ppa,scenarios_data,fwd_curve,hist_sd):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        nat_ref.rename(columns={"year":"Annee","spot":"Spot avg",
            "cp_nat":"M0 (EUR/MWh)","cp_nat_pct":"M0 (%)","shape_disc":"Shape Discount"}
        ).to_excel(w,sheet_name="Historique National",index=False)
        if has_asset and asset_ann is not None:
            asset_ann.to_excel(w,sheet_name="Historique Asset",index=False)
        pd.DataFrame([{"Annee":yr,"Forward (EUR/MWh)":px}
                       for yr,px in fwd_curve.items()]
        ).to_excel(w,sheet_name="Courbe Forward",index=False)
        proj.to_excel(w,sheet_name="Projection",index=False)
        ref_fwd=list(fwd_curve.values())[0] if fwd_curve else 55.0
        pd.DataFrame([{
            "Percentile":p,
            "Shape Discount":float(np.percentile(hist_sd,p)) if len(hist_sd)>0 else 0.15,
            "Captured Price (EUR/MWh)":ref_fwd*(1-float(np.percentile(hist_sd,p))) if len(hist_sd)>0 else ref_fwd*0.85,
            "P&L annuel (k EUR)":pnl_v[p-1]
        } for p in range(1,101)]).to_excel(w,sheet_name="Percentiles P1-P100",index=False)
        if scenarios_data:
            pd.DataFrame(scenarios_data).to_excel(w,sheet_name="Scenarios",index=False)
        monthly=hourly.groupby(["Year","Month"]).agg(
            spot_avg=("Spot","mean"),neg_hours=("Spot",lambda x:(x<0).sum())
        ).reset_index()
        monthly.to_excel(w,sheet_name="Stats mensuelles",index=False)
        hourly.head(8760).to_excel(w,sheet_name="Donnees horaires 1an",index=False)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### PPA Dashboard")
    st.markdown(f'<div class="update-pill">{load_log().split(chr(10))[0]}</div>',
                unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### Marche")
    n_reg       = st.slider("Annees de regression", 2, 12, 3)
    ex22        = st.toggle("Exclure 2022", value=False)
    st.markdown("---")
    st.markdown("### Parametres PPA")
    imb_eur     = st.number_input("Imbalance (EUR/MWh)", 0.0, 10.0, 1.9, 0.1)
    add_disc    = st.slider("Decote additionnelle (%)", 0.0, 10.0, 0.0, 0.25)/100
    st.markdown("---")
    st.markdown("### Sensibilite")
    chosen_pct  = st.slider("Percentile choisi", 1, 100, 74)
    proj_n      = st.slider("Horizon projection (ans)", 1, 10, 5)
    vol_stress  = st.slider("Stress volume (+-%%)", 0, 30, 20)
    spot_stress = st.slider("Stress spot (+-%%)", 0, 30, 20)
    st.markdown("---")
    st.markdown("### Courbe de charge")
    uploaded    = st.file_uploader("Production horaire", type=["xlsx","csv"])
    st.caption("Colonnes : Date | Prod_MWh")
    st.markdown("---")
    if st.button("Vider le cache"):
        st.cache_data.clear(); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD & COMPUTE
# ══════════════════════════════════════════════════════════════════════════════
nat_ref    = load_nat()
hourly     = load_hourly()
data_end   = pd.to_datetime(hourly["Date"]).max()
data_start = pd.to_datetime(hourly["Date"]).min()

asset_ann=None; asset_name="Asset"; asset_raw=None
if uploaded:
    try:
        asset_raw=(pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                   else pd.read_excel(uploaded))
        dc=next((c for c in asset_raw.columns
                 if any(k in c.lower() for k in ["date","time"])),asset_raw.columns[0])
        pc=next((c for c in asset_raw.columns
                 if any(k in c.lower() for k in ["prod","mwh","power","gen","kwh"])),
                asset_raw.columns[1])
        asset_raw[dc]=pd.to_datetime(asset_raw[dc],errors="coerce")
        asset_raw[pc]=pd.to_numeric(asset_raw[pc],errors="coerce")
        if asset_raw[pc].max()>10000: asset_raw[pc]/=1000
        df_a=asset_raw[[dc,pc]].rename(columns={dc:"Date",pc:"Prod_MWh"})
        asset_ann  =compute_asset_annual(hourly,df_a)
        asset_name =uploaded.name.rsplit(".",1)[0]
        st.sidebar.success(f"Charge : {asset_name}")
    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

has_asset  = asset_ann is not None and len(asset_ann)>=2
work       = asset_ann if has_asset else nat_ref.rename(columns={"year":"Year"})
sl,ic,r2   = fit_reg(work,n_reg,False)
sl2,ic2,r22= fit_reg(work,n_reg,True)
sl_u       = sl2  if ex22 else sl
ic_u       = ic2  if ex22 else ic
r2_u       = r22  if ex22 else r2
last_yr    = int(asset_ann["Year"].iloc[-1]) if has_asset else int(nat_ref["year"].max())
hist_sd    = asset_ann["shape_disc"].dropna() if has_asset else nat_ref["shape_disc"].dropna()
hist_sd_f  = (work[work["Year"]!=2022]["shape_disc"].dropna() if ex22 else hist_sd)
sd_ch      = float(np.percentile(hist_sd_f,chosen_pct)) if len(hist_sd_f)>0 else 0.15
vol_mwh    = asset_ann["prod_mwh"].mean() if has_asset else 52000.0
proj       = project_cp(sl_u,ic_u,last_yr,proj_n)
pcts       = list(range(1,101))
sd_vals    = [float(np.percentile(hist_sd_f,p)) if len(hist_sd_f)>0 else 0.15 for p in pcts]

# Default forward — overridden in tab "Courbe forward"
fwd_rows_d = [{"year":yr,"forward":float(DEFAULT_FORWARD.get(yr,52.0))}
               for yr in range(last_yr+1,last_yr+proj_n+1)]
fwd_df     = pd.DataFrame(fwd_rows_d)
fwd_curve  = dict(zip(fwd_df["year"],fwd_df["forward"]))
ref_fwd    = fwd_df["forward"].iloc[0] if len(fwd_df)>0 else 55.0
imb_pct    = imb_eur/ref_fwd if ref_fwd>0 else 0.035
tot_disc   = sd_ch+imb_pct+add_disc
ppa        = ref_fwd*(1-tot_disc)-imb_eur
cp_vals    = [ref_fwd*(1-s) for s in sd_vals]
pnl_v      = [vol_mwh*(c-ppa)/1000 for c in cp_vals]
be         = next((p for p,v in zip(pcts,pnl_v) if v<0),None)
scenarios_export = []

# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "Vue generale",
    "Courbe forward & pricing",
    "Cannibalisation & marche",
    "Sensibilite & scenarios",
    "Export & extracteur SPOT",
])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Vue generale
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## PPA Pricing Dashboard — France Solaire")
    ca,cb=st.columns([3,1])
    with ca:
        st.markdown(
            f'<span style="font-size:14px;color:#555;">'
            f'Agregateur — Achat PPA fixe / Vente spot capture — '
            f'ENTSO-E {data_start.year}–{data_end.strftime("%Y-%m-%d")}'
            f'</span>', unsafe_allow_html=True)
    with cb:
        st.markdown(
            f'<div class="update-pill" style="float:right">'
            f'Donnees au {data_end.strftime("%d/%m/%Y")}</div>',
            unsafe_allow_html=True)
    st.markdown("---")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1,k2,k3,k4,k5=st.columns(5)
    with k1:
        st.markdown(
            f'<div class="ppa-card">'
            f'<div class="lbl">PPA Price (P{chosen_pct})</div>'
            f'<div class="val">{ppa:.2f}</div>'
            f'<div class="lbl">EUR / MWh</div>'
            f'</div>', unsafe_allow_html=True)
    with k2:
        cp_l=(asset_ann["cp_pct"].iloc[-1]*100 if has_asset
              else nat_ref["cp_nat_pct"].iloc[-1]*100)
        c_kpi=C2 if cp_l>80 else (C4 if cp_l>65 else C5)
        st.markdown(
            f'<div class="kpi-card" style="border-left-color:{c_kpi}">'
            f'<div class="kpi-lbl">CP% — {last_yr}</div>'
            f'<div class="kpi-val" style="color:{c_kpi}">{cp_l:.0f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k3:
        sd_cur=(1-cp_l/100)*100
        c_sd=C5 if sd_cur>25 else (C4 if sd_cur>15 else C2)
        st.markdown(
            f'<div class="kpi-card kpi-ora">'
            f'<div class="kpi-lbl">Shape Discount</div>'
            f'<div class="kpi-val" style="color:{c_sd}">{sd_cur:.1f}%</div>'
            f'</div>', unsafe_allow_html=True)
    with k4:
        p50_pnl=vol_mwh*(ref_fwd*(1-float(np.percentile(hist_sd_f,50)))-ppa)/1000
        c_p=C2 if p50_pnl>0 else C5
        st.markdown(
            f'<div class="kpi-card" style="border-left-color:{c_p}">'
            f'<div class="kpi-lbl">P&L P50 (k EUR/an)</div>'
            f'<div class="kpi-val" style="color:{c_p}">{p50_pnl:+.0f}k</div>'
            f'</div>', unsafe_allow_html=True)
    with k5:
        be_txt=f"P{be}" if be else ">P100"
        c_be=C2 if be and be>70 else C5
        st.markdown(
            f'<div class="kpi-card kpi-red">'
            f'<div class="kpi-lbl">Break-even cannibalisation</div>'
            f'<div class="kpi-val" style="color:{c_be}">{be_txt}</div>'
            f'</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Historique + Projection ───────────────────────────────────────────────
    r1a,r1b=st.columns(2)
    with r1a:
        section("Captured Price historique — 2014-2025")
        desc(
            "Barres : Captured Price en % du spot par annee, compare au M0 national (reference solaire France). "
            "100% = l'asset a vendu exactement au spot moyen. En dessous = cannibalisation. "
            "Zone jaune = annee 2022 (crise energetique, atypique). "
            "Bas du graphique : memes donnees en EUR/MWh pour evaluer l'impact en valeur absolue."
        )
        fig=make_subplots(rows=2,cols=1,shared_xaxes=True,
                          vertical_spacing=0.08,
                          subplot_titles=["CP% (% du spot moyen)","CP (EUR/MWh)"],
                          row_heights=[0.55,0.45])
        ny=nat_ref["year"].tolist()
        ncp=nat_ref["cp_nat_pct"].tolist()
        ne=nat_ref["cp_nat"].tolist()
        ns=nat_ref["spot"].tolist()
        # Bars CP%
        fig.add_trace(go.Bar(
            x=ny, y=ncp, name="M0 National",
            marker_color=[f"rgba(42,157,143,0.5)" for _ in ny],
            marker_line_color=C2, marker_line_width=1.5,
            text=[f"<b>{v*100:.0f}%</b>" for v in ncp],
            textposition="outside",
            textfont=dict(size=12, color=C1, family="Calibri")),
            row=1,col=1)
        if has_asset:
            ay=asset_ann["Year"].tolist()
            acp=asset_ann["cp_pct"].tolist()
            ae=asset_ann["cp_eur"].tolist()
            fig.add_trace(go.Bar(
                x=ay, y=acp, name=asset_name,
                marker_color=[f"rgba(231,111,81,0.6)" for _ in ay],
                marker_line_color=C5, marker_line_width=1.5,
                text=[f"<b>{v*100:.0f}%</b>" for v in acp],
                textposition="outside",
                textfont=dict(size=12, color=C5, family="Calibri")),
                row=1,col=1)
            fig.add_trace(go.Scatter(
                x=ay, y=ae, name=asset_name+" EUR",
                line=dict(color=C5, width=2.5),
                mode="lines+markers",
                marker=dict(size=8, color=C5, line=dict(width=1.5,color=WHT))),
                row=2,col=1)
        fig.add_trace(go.Scatter(
            x=ny, y=ncp, line=dict(color=C2,width=2.5,dash="dash"),
            mode="lines+markers",
            marker=dict(size=7,color=C2,symbol="square",line=dict(width=1.5,color=WHT)),
            showlegend=False),row=1,col=1)
        fig.add_hline(y=1.0,line=dict(color="#AAAAAA",width=1,dash="dot"),row=1,col=1)
        fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.25,line_width=0,row=1,col=1)
        fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.25,line_width=0,row=2,col=1)
        fig.add_annotation(x=2022,y=0.32,text="2022",showarrow=False,
            font=dict(color=C4,size=13,family="Calibri"),row=1,col=1)
        fig.add_trace(go.Scatter(
            x=ny, y=ns, name="Spot national",
            line=dict(color="#555555",width=2,dash="dash"),
            mode="lines+markers",
            marker=dict(size=6,color="#555555")),row=2,col=1)
        fig.add_trace(go.Scatter(
            x=ny, y=ne, name="M0 national EUR",
            line=dict(color=C2,width=2.5),
            mode="lines+markers",
            marker=dict(size=7,color=C2,symbol="square",line=dict(width=1.5,color=WHT))),
            row=2,col=1)
        fig.update_yaxes(tickformat=".0%",tickfont=dict(size=13,color=C1),row=1,col=1)
        fig.update_yaxes(tickfont=dict(size=13,color=C1),row=2,col=1)
        fig.update_layout(barmode="group")
        plotly_base(fig,h=560)
        st.plotly_chart(fig,use_container_width=True)

    with r1b:
        section("Projection — Captured Price (%) avec bandes d'incertitude")
        desc(
            "Projection de la CP% par annee en prolongeant la tendance historique du shape discount. "
            "Bande large (claire) = P10-P90 : 80% de probabilite d'etre dans cet intervalle. "
            "Bande etroite (foncee) = P25-P75 : 50% de probabilite. "
            "La ligne centrale P50 est le scenario median. "
            "L'incertitude augmente avec l'horizon car la regression s'ecarte de plus en plus."
        )
        fig2=go.Figure()
        if has_asset:
            fig2.add_trace(go.Scatter(
                x=asset_ann["Year"].tolist(),
                y=asset_ann["cp_pct"].tolist(),
                name="Asset (historique)",
                mode="lines+markers+text",
                line=dict(color=C5,width=3),
                marker=dict(size=10,color=C5,line=dict(width=2,color=WHT)),
                text=[f"<b>{v*100:.0f}%</b>" for v in asset_ann["cp_pct"]],
                textposition="top center",
                textfont=dict(size=12,color=C5,family="Calibri")))
        fig2.add_trace(go.Scatter(
            x=nat_ref["year"].tolist(),
            y=nat_ref["cp_nat_pct"].tolist(),
            name="M0 national",
            mode="lines+markers",
            line=dict(color=C2,width=2.5,dash="dash"),
            marker=dict(size=8,color=C2,symbol="square",line=dict(width=1.5,color=WHT))))
        # Trend line
        tx=list(range(2014,last_yr+proj_n+1))
        fig2.add_trace(go.Scatter(
            x=tx, y=[1-(ic_u+sl_u*yr) for yr in tx],
            name="Tendance",
            line=dict(color="#AAAAAA",width=2,dash="dot"),
            mode="lines",opacity=0.8))
        # Bands — use palette colors with opacity
        py=proj["year"].tolist()
        p10=proj["p10"].tolist(); p25=proj["p25"].tolist()
        p50=proj["p50"].tolist(); p75=proj["p75"].tolist(); p90=proj["p90"].tolist()
        fig2.add_trace(go.Scatter(
            x=py+py[::-1],y=p90+p10[::-1],
            fill="toself",fillcolor="rgba(233,196,106,0.30)",
            line=dict(color="rgba(0,0,0,0)"),name="P10-P90"))
        fig2.add_trace(go.Scatter(
            x=py+py[::-1],y=p75+p25[::-1],
            fill="toself",fillcolor="rgba(244,162,97,0.35)",
            line=dict(color="rgba(0,0,0,0)"),name="P25-P75"))
        # P50 line
        hl=(asset_ann["cp_pct"].iloc[-1] if has_asset
            else nat_ref["cp_nat_pct"].iloc[-1])
        fig2.add_trace(go.Scatter(
            x=[last_yr]+py, y=[hl]+p50,
            name="P50 (scenario central)",
            mode="lines+markers",
            line=dict(color=C1,width=3),
            marker=dict(size=8,color=C1,line=dict(width=2,color=WHT))))
        for _,row in proj.iterrows():
            fig2.add_annotation(
                x=row["year"],y=row["p50"],
                text=(f"<b>P50:{row['p50']*100:.0f}%</b><br>"
                      f"P10:{row['p10']*100:.0f}%"),
                showarrow=True,arrowhead=2,arrowcolor=C1,arrowwidth=1.5,
                font=dict(size=12,color=C1,family="Calibri"),
                bgcolor="rgba(255,255,255,0.85)",bordercolor=C3,borderwidth=1,
                ax=32,ay=-40)
        fig2.add_vline(x=last_yr+0.5,line=dict(color="#BBBBBB",width=1.5,dash="dot"))
        fig2.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.20,line_width=0)
        fig2.update_yaxes(tickformat=".0%")
        plotly_base(fig2,h=560)
        fig2.update_layout(
            title=dict(
                text=f"Pente: {-sl_u*100:.2f}%/an  —  R2: {r2_u:.3f}  "
                     f"{'(excl. 2022)' if ex22 else '(incl. 2022)'}",
                font=dict(size=13,color=C2,family="Calibri"),x=0.01),
            yaxis=dict(range=[0.15,1.22]))
        st.plotly_chart(fig2,use_container_width=True)

    st.markdown("---")

    # ── Percentile table ──────────────────────────────────────────────────────
    section("Table de reference — Shape Discount et P&L par percentile")
    desc(
        "Distribution historique des shape discounts. "
        "Percentile bas (P10, P25) = bonne annee, peu de cannibalisation. "
        "Percentile haut (P75, P90) = mauvaise annee. "
        "P74 = percentile utilise dans le tender WPD comme reference de pricing. "
        "La ligne en surbrillance correspond au percentile selectionne dans la sidebar."
    )
    kp=[5,10,15,20,25,30,35,40,45,50,55,60,65,70,74,75,80,85,90,95,100]
    trows=[]
    for p in kp:
        sdn=float(np.percentile(nat_ref["shape_disc"].dropna(),p))
        sda=(float(np.percentile(asset_ann["shape_disc"].dropna(),p))
             if has_asset else None)
        cpa=ref_fwd*(1-sda) if sda is not None else None
        pnla=vol_mwh*(cpa-ppa)/1000 if cpa is not None else None
        row={"Pct":f"P{p}",
             "Shape Disc national":f"{sdn*100:.1f}%",
             "CP national":f"{(1-sdn)*100:.0f}%"}
        if has_asset:
            row["Shape Disc asset"]=f"{sda*100:.1f}%"
            row["CP asset"]=f"{(1-sda)*100:.0f}%"
            row["P&L k EUR/an"]=f"{pnla:+.0f}k"
        trows.append(row)
    tdf=pd.DataFrame(trows)
    def hi(row):
        p=int(row["Pct"][1:])
        if p==chosen_pct:
            return [f"background-color:{C2};color:white;font-weight:bold"]*len(row)
        if p in [10,50,90]:
            return [f"background-color:{C2L}"]*len(row)
        if p==74:
            return [f"background-color:{C3L}"]*len(row)
        return [""]*len(row)
    st.dataframe(tdf.style.apply(hi,axis=1),use_container_width=True,height=440)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Forward curve & pricing
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    section("Courbe forward EEX — par annee calendaire")
    desc(
        "Entrez les prix forward CAL pour chaque annee du PPA. "
        "Ces prix servent de reference pour calculer le PPA price et le P&L annuel projete. "
        "Formule : PPA = Forward x (1 - Shape Disc projete - Imbalance%) - Imbalance EUR."
    )
    col_i,col_r=st.columns([1,1.6])
    with col_i:
        fwd_rows_live=[]
        for yr in range(last_yr+1,last_yr+proj_n+1):
            px=st.number_input(
                f"CAL {yr} (EUR/MWh)",10.0,200.0,
                float(DEFAULT_FORWARD.get(yr,52.0)),0.5,key=f"fwd_{yr}")
            fwd_rows_live.append({"year":yr,"forward":px})
        fwd_df_live=pd.DataFrame(fwd_rows_live)
        fwd_curve_live=dict(zip(fwd_df_live["year"],fwd_df_live["forward"]))
        st.info(
            "Connecteur API a venir : envoyez la documentation de votre source "
            "de prix forward (Bloomberg, ICE, courtier) pour automatiser le chargement."
        )
    with col_r:
        ref_fwd_live=fwd_df_live["forward"].iloc[0] if len(fwd_df_live)>0 else 55.0
        imb_pct_l=imb_eur/ref_fwd_live if ref_fwd_live>0 else 0.035
        rows_ppa=[]
        for _,row in fwd_df_live.iterrows():
            yr=row["year"]; fwd=row["forward"]
            fsd=ic_u+sl_u*yr; cp=fwd*(1-fsd)
            ppa_yr=fwd*(1-fsd-imb_eur/fwd)-imb_eur
            pnl_mwh=cp-ppa_yr
            rows_ppa.append({
                "Annee":int(yr),
                "Forward":f"{fwd:.2f}",
                "Fwd Shape Disc":f"{fsd*100:.1f}%",
                "Captured (EUR/MWh)":f"{cp:.2f}",
                "PPA Price (EUR/MWh)":f"{ppa_yr:.2f}",
                "P&L/MWh":f"{pnl_mwh:+.2f}",
            })
        st.dataframe(pd.DataFrame(rows_ppa),use_container_width=True,hide_index=True)
        st.markdown('<p class="tbl-note">P&L/MWh = Captured - PPA Price. '
                    'Shape Disc projete = regression lineaire sur historique.</p>',
                    unsafe_allow_html=True)
        # Forward chart
        fig_fwd=go.Figure()
        fig_fwd.add_trace(go.Bar(
            x=fwd_df_live["year"],y=fwd_df_live["forward"],
            marker_color=[f"rgba(42,157,143,0.7)" for _ in fwd_df_live["year"]],
            marker_line_color=C2,marker_line_width=2,
            text=[f"<b>{v:.1f}</b>" for v in fwd_df_live["forward"]],
            textposition="outside",
            textfont=dict(size=14,color=C1,family="Calibri"),
            name="Forward EEX"))
        fig_fwd.update_yaxes(title_text="EUR/MWh")
        fig_fwd.update_xaxes(tickmode="array",tickvals=fwd_df_live["year"].tolist())
        plotly_base(fig_fwd,h=250,show_legend=False)
        st.plotly_chart(fig_fwd,use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — Cannibalisation & marche
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    # Neg hours
    section("Heures a prix negatifs — par annee")
    desc(
        "Nombre d'heures par an ou le prix spot EPEX France est inferieur a 0 EUR/MWh. "
        "Cette metrique est un indicateur direct de l'exces de production renouvelable sur la consommation. "
        "Vert = moins de 100h (impact limite). Orange = 100-300h. Rouge = plus de 300h (fort impact sur cannibalisation). "
        "La ligne de tendance montre l'acceleration du phenomene."
    )
    neg_ann=hourly[hourly["Spot"]<0].groupby("Year").size().reset_index(name="neg_hours")
    all_yrs=pd.DataFrame({"Year":sorted(hourly["Year"].unique())})
    neg_ann=all_yrs.merge(neg_ann,on="Year",how="left").fillna(0)
    neg_ann["neg_hours"]=neg_ann["neg_hours"].astype(int)
    bar_c=[C5 if v>300 else (C4 if v>100 else C2) for v in neg_ann["neg_hours"]]
    fig_neg=go.Figure()
    fig_neg.add_trace(go.Bar(
        x=neg_ann["Year"],y=neg_ann["neg_hours"],
        marker_color=bar_c,marker_line_color=WHT,marker_line_width=1,
        text=[f"<b>{v}</b>" for v in neg_ann["neg_hours"]],
        textposition="outside",textfont=dict(size=13,color=C1,family="Calibri"),
        name="Heures prix negatifs"))
    if len(neg_ann)>=3:
        xn=neg_ann["Year"].values.astype(float)
        yn=neg_ann["neg_hours"].values.astype(float)
        sln,icn,_,_,_=stats.linregress(xn,yn)
        fut=list(range(int(xn.min()),int(xn.max())+4))
        fig_neg.add_trace(go.Scatter(
            x=fut,y=[max(0,icn+sln*yr) for yr in fut],
            mode="lines",line=dict(color=C5,width=2.5,dash="dash"),
            name=f"Tendance ({sln:+.0f}h/an)"))
    fig_neg.add_hline(y=15,line=dict(color=C2,width=1.5,dash="dot"),
        annotation_text="Seuil CRE (15h)",
        annotation_font=dict(color=C2,size=13,family="Calibri"))
    fig_neg.update_layout(xaxis_title="Annee",yaxis_title="Heures (spot < 0 EUR/MWh)")
    plotly_base(fig_neg,h=360)
    st.plotly_chart(fig_neg,use_container_width=True)

    st.markdown("---")

    c3a,c3b=st.columns(2)
    with c3a:
        section("Profil mensuel de cannibalisation — moyenne historique")
        desc(
            "Shape discount moyen par mois, calcule sur l'ensemble des annees disponibles. "
            "Les mois d'ete (avril a aout) concentrent la production solaire : "
            "c'est la que la cannibalisation est la plus forte. "
            "Les barres d'erreur (+/-1 ecart-type) montrent la variabilite d'une annee a l'autre."
        )
        monthly=hourly.copy()
        monthly["Rev_nat"]=monthly["NatMW"]*monthly["Spot"]
        monthly_agg=monthly[monthly["Spot"]>0].groupby(["Year","Month"]).agg(
            spot_avg=("Spot","mean"),
            prod_nat=("NatMW","sum"),
            rev_nat=("Rev_nat","sum"),
        ).reset_index()
        monthly_agg["m0"]=monthly_agg["rev_nat"]/monthly_agg["prod_nat"].replace(0,np.nan)
        monthly_agg["sd_m"]=1-monthly_agg["m0"]/monthly_agg["spot_avg"]
        month_avg=monthly_agg.groupby("Month")["sd_m"].agg(["mean","std"]).reset_index()
        bar_c_m=[C5 if v>0.15 else (C4 if v>0.08 else C2) for v in month_avg["mean"]]
        fig_mo=go.Figure()
        fig_mo.add_trace(go.Bar(
            x=MONTH_NAMES,y=month_avg["mean"],
            error_y=dict(type="data",array=month_avg["std"].tolist(),
                         visible=True,color="#AAAAAA",thickness=2,width=5),
            marker_color=bar_c_m,marker_line_color=WHT,marker_line_width=1,
            text=[f"<b>{v*100:.1f}%</b>" for v in month_avg["mean"]],
            textposition="outside",textfont=dict(size=12,color=C1,family="Calibri"),
            name="Shape discount mensuel"))
        fig_mo.add_hline(y=0,line=dict(color="#AAAAAA",width=1))
        fig_mo.update_yaxes(tickformat=".0%",title_text="Shape Discount moyen")
        plotly_base(fig_mo,h=360,show_legend=False)
        st.plotly_chart(fig_mo,use_container_width=True)

    with c3b:
        section("Scatter — CP% vs capacite solaire nationale")
        desc(
            "Chaque point represente une annee. "
            "L'axe horizontal est la capacite solaire nationale moyenne installee (MW). "
            "La droite de regression confirme la relation negative : "
            "plus la capacite installee augmente, plus le Captured Price baisse. "
            "Les lignes verticales representent les objectifs PPE3 pour 2030 (48 GW) et 2035 (65 GW)."
        )
        nat_mw_ann=hourly.groupby("Year")["NatMW"].mean().reset_index()
        sc_df=nat_ref.merge(nat_mw_ann.rename(columns={"Year":"year"}),on="year",how="inner")
        sc_df=sc_df[sc_df["NatMW"]>0]
        pt_col=[C5 if y>=2024 else (C3 if y==2022 else C2) for y in sc_df["year"]]
        fig_sc=go.Figure()
        fig_sc.add_trace(go.Scatter(
            x=sc_df["NatMW"],y=sc_df["cp_nat_pct"],
            mode="markers+text",
            marker=dict(size=16,color=pt_col,line=dict(width=2,color=WHT)),
            text=[f"<b>{y}</b>" for y in sc_df["year"]],
            textposition="top center",
            textfont=dict(size=12,color=C1,family="Calibri"),
            name="M0 national"))
        if len(sc_df)>=3:
            xs=sc_df["NatMW"].values; ys=sc_df["cp_nat_pct"].values
            sl_sc,ic_sc,r_sc,_,_=stats.linregress(xs,ys)
            xl=np.linspace(0,75000,200)
            fig_sc.add_trace(go.Scatter(
                x=xl,y=ic_sc+sl_sc*xl,
                mode="lines",line=dict(color="#AAAAAA",width=2,dash="dash"),
                name=f"Regression (R2={r_sc**2:.2f})"))
        for gw,lbl,col in [(48000,"PPE3 2030",C4),(65000,"PPE3 2035",C5)]:
            fig_sc.add_vline(x=gw,line=dict(color=col,width=2,dash="dot"))
            fig_sc.add_annotation(x=gw,y=sc_df["cp_nat_pct"].min()*0.94,text=f"<b>{lbl}</b>",
                font=dict(color=col,size=12,family="Calibri"),showarrow=False,xanchor="left")
        fig_sc.update_yaxes(tickformat=".0%",title_text="Captured Price (% du spot)")
        fig_sc.update_xaxes(title_text="Capacite solaire nationale moyenne (MW)")
        plotly_base(fig_sc,h=360)
        st.plotly_chart(fig_sc,use_container_width=True)

    st.markdown("---")

    section("Variation annuelle du Shape Discount")
    desc(
        "Variation d'une annee sur l'autre du shape discount national, exprimee en points de pourcentage. "
        "Rouge = la cannibalisation s'est aggravement aggravee par rapport a l'annee precedente. "
        "Teal = amelioration (rare). La tendance de long terme est structurellement a la hausse."
    )
    sd_s=nat_ref[["year","shape_disc"]].dropna().sort_values("year")
    sd_s["delta"]=sd_s["shape_disc"].diff()
    sd_s=sd_s.dropna(subset=["delta"])
    fig_wf=go.Figure()
    fig_wf.add_trace(go.Bar(
        x=sd_s["year"],y=sd_s["delta"],
        marker_color=[C5 if v>0 else C2 for v in sd_s["delta"]],
        marker_line_color=WHT,marker_line_width=1,
        text=[f"<b>{v*100:+.1f}pp</b>" for v in sd_s["delta"]],
        textposition="outside",textfont=dict(size=13,color=C1,family="Calibri"),
        name="Variation annuelle"))
    fig_wf.add_hline(y=0,line=dict(color="#AAAAAA",width=1.5))
    fig_wf.update_yaxes(tickformat=".1%",title_text="Delta Shape Discount (pp)")
    fig_wf.update_xaxes(title_text="Annee")
    plotly_base(fig_wf,h=320,show_legend=False)
    st.plotly_chart(fig_wf,use_container_width=True)

    st.markdown("---")
    section("Heatmap — Shape Discount mensuel par annee")
    desc(
        "Representation en grille : chaque cellule montre le shape discount pour un mois et une annee donnee. "
        "Teal = faible cannibalisation. Rouge brique = forte cannibalisation. "
        "Permet d'identifier rapidement les periodes les plus critiques."
    )
    pivot=monthly_agg.pivot(index="Year",columns="Month",values="sd_m")
    pivot.columns=[MONTH_NAMES[c-1] for c in pivot.columns]
    fig_hm=go.Figure(data=go.Heatmap(
        z=pivot.values*100,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0,C2],[0.5,C3],[1,C5]],
        text=[[f"<b>{v:.1f}%</b>" for v in row] for row in pivot.values*100],
        texttemplate="%{text}",
        textfont=dict(size=12,color=C1,family="Calibri"),
        colorbar=dict(title=dict(text="Shape Disc (%)",font=dict(size=13,color=C1)),
                      tickfont=dict(size=12,color=C1),thickness=14)))
    fig_hm.update_xaxes(title_text="Mois",tickfont=dict(size=13,color=C1))
    fig_hm.update_yaxes(title_text="Annee",tickfont=dict(size=13,color=C1))
    plotly_base(fig_hm,h=350,show_legend=False)
    st.plotly_chart(fig_hm,use_container_width=True)

    if has_asset and asset_raw is not None:
        st.markdown("---")
        section("Profil horaire — Production asset vs Spot moyen")
        desc(
            "Production moyenne de l'asset (barres, axe gauche) et prix spot moyen (ligne, axe droit) "
            "par heure de la journee. La production se concentre entre 10h et 16h, "
            "exactement quand le spot est au plus bas a cause de la saturation solaire nationale. "
            "C'est le mecanisme fondamental de la cannibalisation."
        )
        try:
            dc=next((c for c in asset_raw.columns if any(k in c.lower() for k in ["date","time"])),asset_raw.columns[0])
            pc=next((c for c in asset_raw.columns if any(k in c.lower() for k in ["prod","mwh","power","gen"])),asset_raw.columns[1])
            dfh=asset_raw[[dc,pc]].copy(); dfh.columns=["Date","Prod"]
            dfh["Date"]=pd.to_datetime(dfh["Date"],errors="coerce")
            dfh["Prod"]=pd.to_numeric(dfh["Prod"],errors="coerce").fillna(0)
            dfh["Hour"]=dfh["Date"].dt.hour
            hp=dfh.groupby("Hour")["Prod"].mean().reset_index()
            sph=hourly.copy(); sph["Hour"]=pd.to_datetime(sph["Date"]).dt.hour
            sph=sph.groupby("Hour")["Spot"].mean().reset_index()
            hp=hp.merge(sph,on="Hour")
            fig5=make_subplots(specs=[[{"secondary_y":True}]])
            fig5.add_trace(go.Bar(
                x=hp["Hour"],y=hp["Prod"],
                name="Production moy. (MWh/h)",
                marker_color=f"rgba(42,157,143,0.60)",
                marker_line_color=C2,marker_line_width=1),secondary_y=False)
            fig5.add_trace(go.Scatter(
                x=hp["Hour"],y=hp["Spot"],
                name="Spot moyen (EUR/MWh)",
                mode="lines+markers",
                line=dict(color=C5,width=3),
                marker=dict(size=8,color=C5,line=dict(width=2,color=WHT))),secondary_y=True)
            fig5.update_xaxes(
                tickvals=list(range(0,24,2)),
                ticktext=[f"{h:02d}h" for h in range(0,24,2)],
                tickfont=dict(size=13,color=C1))
            fig5.update_yaxes(title_text="Production (MWh/h)",secondary_y=False,
                              tickfont=dict(size=13,color=C1))
            fig5.update_yaxes(title_text="Spot moyen (EUR/MWh)",secondary_y=True,
                              tickfont=dict(size=13,color=C1))
            plotly_base(fig5,h=320)
            st.plotly_chart(fig5,use_container_width=True)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — Sensibilite & scenarios
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    section("P&L annuel en fonction du percentile de cannibalisation")
    desc(
        f"Pour chaque percentile de l'historique des shape discounts (de P1 = meilleure annee a P100 = pire), "
        f"le graphique montre le P&L annuel de l'agregateur en k EUR. "
        f"Zone teal = profit. Zone rouge = perte. "
        f"Le marqueur indique le percentile P{chosen_pct} selectionne dans la sidebar. "
        f"La bande translucide montre l'impact d'un stress volume de +/-{vol_stress}% "
        f"sur le meme percentile."
    )
    fig3=go.Figure()
    px_=[p for p,v in zip(pcts,pnl_v) if v>=0]
    py_=[v for v in pnl_v if v>=0]
    nx_=[p for p,v in zip(pcts,pnl_v) if v<0]
    ny_=[v for v in pnl_v if v<0]
    if px_:
        fig3.add_trace(go.Scatter(
            x=px_,y=py_,fill="tozeroy",
            fillcolor="rgba(42,157,143,0.15)",
            line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    if nx_:
        fig3.add_trace(go.Scatter(
            x=nx_,y=ny_,fill="tozeroy",
            fillcolor="rgba(231,111,81,0.15)",
            line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    fig3.add_trace(go.Scatter(
        x=pcts,y=pnl_v,name="P&L (k EUR/an)",
        mode="lines",line=dict(color=C1,width=3)))
    pc_=pnl_v[chosen_pct-1]
    fig3.add_trace(go.Scatter(
        x=[chosen_pct],y=[pc_],
        mode="markers+text",
        marker=dict(size=16,color=C2 if pc_>=0 else C5,
                    line=dict(width=2.5,color=WHT)),
        text=[f"<b>P{chosen_pct} : {pc_:.0f}k</b>"],
        textposition="top right",
        name=f"P{chosen_pct} choisi",
        textfont=dict(size=13,color=C1,family="Calibri")))
    pu=[vol_mwh*(1+vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    pd_=[vol_mwh*(1-vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    fig3.add_trace(go.Scatter(
        x=pcts+pcts[::-1],y=pu+pd_[::-1],
        fill="toself",fillcolor="rgba(233,196,106,0.30)",
        line=dict(color="rgba(0,0,0,0)"),
        name=f"+/-{vol_stress}% volume"))
    fig3.add_hline(y=0,line=dict(color="#AAAAAA",width=2))
    if be:
        fig3.add_vline(x=be,line=dict(color=C5,width=2,dash="dot"),
            annotation_text=f"<b>Break-even P{be}</b>",
            annotation_font=dict(color=C5,size=13,family="Calibri"))
    fig3.update_layout(xaxis_title="Percentile de shape discount (1=meilleure annee, 100=pire)",
                       yaxis_title="P&L annuel (k EUR)")
    plotly_base(fig3,h=420)
    st.plotly_chart(fig3,use_container_width=True)
    if be:
        st.warning(
            f"Break-even a P{be} — l'agregateur perd de l'argent si la cannibalisation "
            f"depasse le P{be} de l'historique.")

    st.markdown("---")
    section(f"Scenarios de stress — P&L cumule sur {proj_n} ans")
    desc(
        f"P&L cumule sur {proj_n} ans pour 9 scenarios de stress combines. "
        f"Les barres montrent le scenario median (P50). "
        f"Les triangles vers le bas = P10 (scenario pessimiste), "
        f"triangles vers le haut = P90 (scenario optimiste). "
        f"'Stress total' combine spot -{spot_stress}%, cannibalisation +{vol_stress}%, volume -{vol_stress}%."
    )
    sd_med=float(np.percentile(hist_sd_f,50)) if len(hist_sd_f)>0 else 0.15
    scens=[
        ("Base",1.00,0.00,0.00),
        (f"Cannib +{vol_stress}%",1.00,+vol_stress/100,0.00),
        (f"Cannib -{vol_stress}%",1.00,-vol_stress/100,0.00),
        (f"Spot +{spot_stress}%",1+spot_stress/100,0.00,0.00),
        (f"Spot -{spot_stress}%",1-spot_stress/100,0.00,0.00),
        (f"Vol +{vol_stress}%",1.00,0.00,+vol_stress/100),
        (f"Vol -{vol_stress}%",1.00,0.00,-vol_stress/100),
        ("Stress total",1-spot_stress/100,+vol_stress/100,-vol_stress/100),
        ("Bull total",1+spot_stress/100,-vol_stress/100,+vol_stress/100),
    ]
    sn,sv50,sv10,sv90=[],[],[],[]
    scenarios_export=[]
    for name,sm,da,va in scens:
        p50t=vol_mwh*(1+va)*(sm*ref_fwd*(1-(sd_med+da))-ppa)/1000*proj_n
        sdp10=float(np.percentile(hist_sd_f,10))+da if len(hist_sd_f)>0 else 0.1
        sdp90=float(np.percentile(hist_sd_f,90))+da if len(hist_sd_f)>0 else 0.3
        p10t=vol_mwh*(1+va)*(sm*ref_fwd*(1-sdp90)-ppa)/1000*proj_n
        p90t=vol_mwh*(1+va)*(sm*ref_fwd*(1-sdp10)-ppa)/1000*proj_n
        sn.append(name); sv50.append(p50t)
        sv10.append(p10t); sv90.append(p90t)
        scenarios_export.append({"Scenario":name,
                                   "P10 (k EUR)":f"{p10t:+.0f}k",
                                   "P50 (k EUR)":f"{p50t:+.0f}k",
                                   "P90 (k EUR)":f"{p90t:+.0f}k"})
    fig4=go.Figure()
    fig4.add_trace(go.Bar(
        name="P50 (median)",x=sn,y=sv50,
        marker_color=[f"rgba(42,157,143,0.80)" if v>=0
                      else f"rgba(231,111,81,0.80)" for v in sv50],
        marker_line_color=WHT,marker_line_width=1,
        text=[f"<b>{v:+.0f}k</b>" for v in sv50],
        textposition="outside",
        textfont=dict(size=13,color=C1,family="Calibri")))
    fig4.add_trace(go.Scatter(
        name="P10 (pessimiste)",x=sn,y=sv10,
        mode="markers",
        marker=dict(symbol="triangle-down",size=14,color=C5,
                    line=dict(width=2,color=WHT))))
    fig4.add_trace(go.Scatter(
        name="P90 (optimiste)",x=sn,y=sv90,
        mode="markers",
        marker=dict(symbol="triangle-up",size=14,color=C2,
                    line=dict(width=2,color=WHT))))
    fig4.add_hline(y=0,line=dict(color="#AAAAAA",width=2))
    fig4.update_layout(
        xaxis_title="Scenario",
        yaxis_title=f"P&L cumule {proj_n} ans (k EUR)",
        bargap=0.35)
    plotly_base(fig4,h=400)
    st.plotly_chart(fig4,use_container_width=True)

    st.markdown("---")
    section("Detail des scenarios — tableau")
    desc("Memes valeurs que le graphique. P10 = cannibalisation au 90eme percentile historique. P90 = cannibalisation au 10eme percentile.")
    st.dataframe(pd.DataFrame(scenarios_export),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 5 — Export & extracteur SPOT
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    col_e1,col_e2=st.columns(2)

    with col_e1:
        section("Export Excel — toutes les donnees du dashboard")
        desc(
            "Genere un fichier .xlsx avec 8 feuilles : "
            "historique national, historique asset (si charge), courbe forward, "
            "projection P10-P90, table des percentiles P1-P100, scenarios de stress, "
            "stats mensuelles et donnees horaires (1 an)."
        )
        if st.button("Generer le fichier Excel"):
            with st.spinner("Generation..."):
                excel_buf=build_excel(
                    nat_ref,hourly,asset_ann,has_asset,asset_name,
                    proj,pnl_v,ppa,scenarios_export,fwd_curve,
                    nat_ref["shape_disc"].dropna().values)
                st.download_button(
                    label="Telecharger ppa_dashboard_export.xlsx",
                    data=excel_buf,
                    file_name="ppa_dashboard_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.success("Fichier pret.")

    with col_e2:
        section("Format courbe de charge attendu")
        desc("Uploader un fichier avec ces deux colonnes dans la sidebar.")
        st.code("Date,Prod_MWh\n2024-01-01 00:00:00,0.0\n2024-01-01 10:00:00,4.2\n2024-01-01 11:00:00,7.8", language="text")
        ex_file=DATA_DIR.parent/"exemple_courbe_charge.csv"
        if ex_file.exists():
            with open(ex_file,"rb") as f:
                st.download_button("Telecharger exemple CSV",data=f.read(),
                    file_name="exemple_courbe_charge.csv",mime="text/csv")

    st.markdown("---")
    section("Extracteur de donnees SPOT — ENTSO-E Transparency Platform")
    desc(
        "Telechargez les prix spot horaires et la production solaire nationale depuis ENTSO-E "
        "dans le format exact attendu par ce dashboard (Date, Year, Month, Hour, Spot, NatMW). "
        "Entrez votre cle API, selectionnez le pays et la periode, puis lancez l'extraction."
    )
    col_ex1,col_ex2=st.columns(2)
    with col_ex1:
        api_key_in=st.text_input("Cle API ENTSO-E",type="password",
            help="transparency.entsoe.eu — My Account — Web API Security Token")
        country_c=st.selectbox("Pays",["FR","DE","ES","BE","NL","IT","GB"],index=0)
        d_start=st.date_input("Date debut",value=pd.Timestamp("2024-01-01"))
        d_end  =st.date_input("Date fin",  value=pd.Timestamp("2024-12-31"))
        incl_solar=st.checkbox("Inclure production solaire (NatMW)",value=True)
    with col_ex2:
        st.markdown("**Format de sortie**")
        st.code("Date,Year,Month,Hour,Spot,NatMW\n2024-01-01 00:00:00,2024,1,0,52.3,1250.0",language="text")
        if not api_key_in:
            st.info(
                "Pas encore de cle API ENTSO-E ?\n\n"
                "1. Aller sur transparency.entsoe.eu\n"
                "2. My Account Settings\n"
                "3. Web API Security Token — Generate")
        else:
            if st.button("Extraire les donnees", key="extract_btn"):
                with st.spinner("Connexion a ENTSO-E..."):
                    try:
                        from entsoe import EntsoePandasClient
                        import time
                        client=EntsoePandasClient(api_key=api_key_in)
                        start=pd.Timestamp(d_start,tz="Europe/Paris")
                        end  =pd.Timestamp(d_end,  tz="Europe/Paris")+pd.Timedelta(days=1)
                        prices=client.query_day_ahead_prices(country_c,start=start,end=end)
                        prices=prices.resample("1h").mean()
                        df_out=pd.DataFrame({"Spot":prices})
                        df_out.index.name="Date"
                        df_out=df_out.reset_index()
                        df_out["Date"] =df_out["Date"].dt.tz_localize(None)
                        df_out["Year"] =df_out["Date"].dt.year
                        df_out["Month"]=df_out["Date"].dt.month
                        df_out["Hour"] =df_out["Date"].dt.hour
                        df_out["NatMW"]=0.0
                        if incl_solar:
                            try:
                                time.sleep(1)
                                solar=client.query_generation(country_c,start=start,end=end,psr_type="B16")
                                if isinstance(solar,pd.DataFrame): solar=solar.sum(axis=1)
                                solar=solar.resample("1h").mean()
                                solar.index=solar.index.tz_localize(None)
                                df_out=df_out.set_index("Date").join(solar.rename("NatMW_n"),how="left")
                                df_out["NatMW"]=df_out["NatMW_n"].fillna(0)
                                df_out=df_out.drop(columns=["NatMW_n"]).reset_index()
                            except Exception as e2:
                                st.warning(f"Production solaire non disponible : {e2}")
                        df_out=df_out[["Date","Year","Month","Hour","Spot","NatMW"]].dropna(subset=["Spot"])
                        st.success(f"{len(df_out):,} heures extraites — {d_start} a {d_end}")
                        st.dataframe(df_out.head(24),use_container_width=True)
                        st.download_button("Telecharger le CSV",
                            data=df_out.to_csv(index=False).encode("utf-8"),
                            file_name=f"spot_{country_c}_{d_start}_{d_end}.csv",
                            mime="text/csv")
                    except ImportError:
                        st.error("entsoe-py non installe. Ajouter dans requirements.txt.")
                    except Exception as e:
                        st.error(f"Erreur ENTSO-E : {e}")

st.markdown("---")
st.markdown(
    f'<span style="font-size:12px;color:#888;font-family:Calibri,Arial,sans-serif;">'
    f'ENTSO-E France {data_start.year}–{data_end.strftime("%Y-%m-%d")} '
    f'— {len(hourly):,} heures — '
    f'Mise a jour quotidienne automatique (GitHub Actions) — '
    f'Logique pricing : WPD Tender format — Shape Discount = 1 - CP%%'
    f'</span>',
    unsafe_allow_html=True)
