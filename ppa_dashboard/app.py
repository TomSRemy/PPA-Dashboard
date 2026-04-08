"""
PPA Pricing Dashboard — France Solaire  v4
Palette : #D9293B #F2916D #F1D194 #3B5145 #243A2E
Font    : Calibri 11px
No emojis. Descriptions sous chaque graphique.
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
    page_title="PPA Pricing Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Palette ────────────────────────────────────────────────────────────────────
C1 = "#D9293B"   # rouge         — pertes, négatif
C2 = "#F2916D"   # orange saumon — shape discount, attention
C3 = "#F1D194"   # jaune sable   — highlights, fond cartes
C4 = "#3B5145"   # vert sapin    — PPA price, positif, sidebar
C5 = "#243A2E"   # vert nuit     — headers, titres

# Dérivés clairs pour fonds
C4L = "#E6EDE9"  # vert très clair
C1L = "#FCECED"  # rouge très clair
C3L = "#FDF8EC"  # jaune très clair

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Calibri&display=swap');
html, body, [class*="css"], .stMarkdown, p, li, td, th, label {{
    font-family: Calibri, 'Segoe UI', sans-serif !important;
    font-size: 14px !important;
}}
h1 {{ font-size: 20px !important; font-weight: 700; color: {C5}; font-family: Calibri, sans-serif !important; }}
h2 {{ font-size: 16px !important; font-weight: 700; color: {C5}; font-family: Calibri, sans-serif !important; }}
h3 {{ font-size: 14px !important; font-weight: 700; color: {C5}; font-family: Calibri, sans-serif !important; }}
.section-title {{
    font-size: 13px !important; font-weight: 700; color: {C5};
    border-bottom: 2px solid {C4}; padding-bottom: 4px; margin: 18px 0 6px 0;
    font-family: Calibri, sans-serif; text-transform: uppercase; letter-spacing: 0.04em;
}}
.chart-desc {{
    font-size: 12px !important; color: #555; font-style: italic;
    margin: 2px 0 14px 0; font-family: Calibri, sans-serif;
    padding: 6px 10px; background: {C3L}; border-left: 3px solid {C3};
    border-radius: 0 4px 4px 0;
}}
.ppa-card {{
    background: {C4}; color: white; padding: 18px 22px;
    border-radius: 8px; text-align: center; margin: 4px 0;
}}
.ppa-card .val {{ font-size: 26px; font-weight: 700; font-family: Calibri, sans-serif; }}
.ppa-card .lbl {{ font-size: 11px; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-card {{
    background: white; border-left: 4px solid {C4};
    padding: 12px 16px; border-radius: 4px; margin: 4px 0;
    border: 0.5px solid #DDD; border-left-width: 4px;
}}
.kpi-val {{ font-size: 20px; font-weight: 700; color: {C5}; font-family: Calibri, sans-serif; }}
.kpi-lbl {{ font-size: 11px; color: #777; text-transform: uppercase; letter-spacing: 0.04em; }}
.kpi-red {{ border-left-color: {C1} !important; }}
.kpi-ora {{ border-left-color: {C2} !important; }}
.tbl-note {{
    font-size: 11px; color: #666; font-style: italic;
    margin-top: 4px; font-family: Calibri, sans-serif;
}}
[data-testid="stSidebar"] {{ background: {C5}; }}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSlider label {{
    color: #C8D8CC !important; font-size: 13px !important;
}}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    color: white !important;
}}
.stTabs [data-baseweb="tab"] {{
    font-family: Calibri, sans-serif !important;
    font-size: 13px !important; font-weight: 600;
    color: {C5} !important;
}}
.stTabs [aria-selected="true"] {{
    border-bottom: 3px solid {C4} !important;
    color: {C4} !important;
}}
.update-pill {{
    background: {C4L}; border: 1px solid {C4};
    border-radius: 20px; padding: 3px 12px;
    font-size: 11px; color: {C5}; display: inline-block;
    font-family: Calibri, sans-serif;
}}
div[data-testid="stDataFrame"] {{
    font-family: Calibri, sans-serif !important;
    font-size: 13px !important;
}}
</style>""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_FORWARD = {2026:55.0,2027:54.0,2028:53.0,2029:52.0,2030:51.0}
MONTH_NAMES = ["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"]

def pfmt(v): return f'<span style="color:{C4};font-weight:700">{v}</span>'
def rfmt(v): return f'<span style="color:{C1};font-weight:700">{v}</span>'

def chart_desc(text):
    st.markdown(f'<div class="chart-desc">{text}</div>', unsafe_allow_html=True)

def section(text):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)

def layout_plotly(fig, h=380, legend_bottom=False):
    fig.update_layout(
        height=h, plot_bgcolor="#FAFAFA", paper_bgcolor="white",
        margin=dict(l=0,r=0,t=20,b=0),
        font=dict(family="Calibri, Segoe UI, sans-serif", size=13),
        legend=dict(orientation="h",
                    yanchor="bottom" if legend_bottom else "top",
                    y=1.02 if legend_bottom else 1.0,
                    xanchor="right", x=1),
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
    m["Rev"] = m["Prod_MWh"]*m["Spot"]
    ann = m.groupby("Year").agg(
        prod_mwh=("Prod_MWh","sum"), revenue=("Rev","sum"),
        spot_avg=("Spot","mean"),
        prod_hours=("Prod_MWh",lambda x:(x>0).sum()),
        neg_hours=("Spot",lambda x:(x<0).sum()),
        nat_mw=("NatMW","mean"),
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
                proj,pcts,sd_vals,pnl_v,ppa,scenarios_data,fwd_curve):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        nat_ref.rename(columns={"year":"Annee","spot":"Spot avg","cp_nat":"M0 (EUR/MWh)",
            "cp_nat_pct":"M0 (%)","shape_disc":"Shape Discount"}
        ).to_excel(w,sheet_name="Historique National",index=False)
        if has_asset and asset_ann is not None:
            asset_ann.to_excel(w,sheet_name=f"Historique Asset",index=False)
        pd.DataFrame([{"Annee":yr,"Forward (EUR/MWh)":px} for yr,px in fwd_curve.items()]
        ).to_excel(w,sheet_name="Courbe Forward",index=False)
        proj.rename(columns={"year":"Annee","fsd":"Shape Disc tendance",
            "p10":"P10","p25":"P25","p50":"P50","p75":"P75","p90":"P90"}
        ).to_excel(w,sheet_name="Projection",index=False)
        hist_sd = nat_ref["shape_disc"].dropna().values
        ref_fwd = list(fwd_curve.values())[0] if fwd_curve else 55.0
        pd.DataFrame([{
            "Percentile":p,
            "Shape Discount":float(np.percentile(hist_sd,p)) if len(hist_sd) else 0.15,
            "Captured Price":ref_fwd*(1-float(np.percentile(hist_sd,p))) if len(hist_sd) else ref_fwd*0.85,
            "PnL annuel (Ek)":pnl_v[p-1]
        } for p in range(1,101)]).to_excel(w,sheet_name="Percentiles",index=False)
        if scenarios_data:
            pd.DataFrame(scenarios_data).to_excel(w,sheet_name="Scenarios",index=False)
        monthly=hourly.groupby(["Year","Month"]).agg(
            spot_avg=("Spot","mean"),neg_hours=("Spot",lambda x:(x<0).sum())
        ).reset_index()
        monthly.to_excel(w,sheet_name="Stats mensuelles",index=False)
        hourly.head(8760).to_excel(w,sheet_name="Donnees horaires (1an)",index=False)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### PPA Dashboard")
    log = load_log()
    st.markdown(f'<div class="update-pill">{log.split(chr(10))[0]}</div>',
                unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### Marche")
    n_reg       = st.slider("Annees de regression (N)", 2, 12, 3)
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
    uploaded    = st.file_uploader("Production horaire", type=["xlsx","csv"],
                                    help="Colonnes : Date | Prod_MWh")
    st.markdown("---")
    if st.button("Vider le cache"):
        st.cache_data.clear(); st.rerun()

# ── Load ───────────────────────────────────────────────────────────────────────
nat_ref = load_nat()
hourly  = load_hourly()
data_end   = pd.to_datetime(hourly["Date"]).max()
data_start = pd.to_datetime(hourly["Date"]).min()

asset_ann=None; asset_name="Asset"; asset_raw=None
if uploaded:
    try:
        asset_raw=(pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                   else pd.read_excel(uploaded))
        dc=next((c for c in asset_raw.columns if "date" in c.lower() or "time" in c.lower()),asset_raw.columns[0])
        pc=next((c for c in asset_raw.columns if any(k in c.lower() for k in ["prod","mwh","power","gen","kwh"])),asset_raw.columns[1])
        asset_raw[dc]=pd.to_datetime(asset_raw[dc],errors="coerce")
        asset_raw[pc]=pd.to_numeric(asset_raw[pc],errors="coerce")
        if asset_raw[pc].max()>10000: asset_raw[pc]/=1000
        df_a=asset_raw[[dc,pc]].rename(columns={dc:"Date",pc:"Prod_MWh"})
        asset_ann=compute_asset_annual(hourly,df_a)
        asset_name=uploaded.name.rsplit(".",1)[0]
        st.sidebar.success(f"OK : {asset_name}")
    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

has_asset = asset_ann is not None and len(asset_ann)>=2
work      = asset_ann if has_asset else nat_ref.rename(columns={"year":"Year"})
sl,ic,r2  = fit_reg(work,n_reg,False)
sl2,ic2,r22=fit_reg(work,n_reg,True)
sl_u=sl2 if ex22 else sl; ic_u=ic2 if ex22 else ic; r2_u=r22 if ex22 else r2
last_yr   = int(asset_ann["Year"].iloc[-1]) if has_asset else int(nat_ref["year"].max())
hist_sd   = asset_ann["shape_disc"].dropna() if has_asset else nat_ref["shape_disc"].dropna()
hist_sd_f = work[work["Year"]!=2022]["shape_disc"].dropna() if ex22 else hist_sd
sd_ch     = float(np.percentile(hist_sd_f,chosen_pct)) if len(hist_sd_f) else 0.15
vol_mwh   = asset_ann["prod_mwh"].mean() if has_asset else 52000.0
proj      = project_cp(sl_u,ic_u,last_yr,proj_n)
pcts      = list(range(1,101))
sd_vals   = [float(np.percentile(hist_sd_f,p)) if len(hist_sd_f) else 0.15 for p in pcts]

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
#  TAB 2 — Forward curve (must compute fwd_curve early, used everywhere)
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    section("Courbe forward EEX — par annee calendaire")
    chart_desc(
        "Entrez les prix CAL forward pour chaque annee de la duree du PPA. "
        "Ces prix servent de reference pour calculer le prix PPA et le P&L projete par annee. "
        "La formule appliquee est : PPA = Forward x (1 - Shape Disc - Imbalance%) - Imbalance EUR."
    )
    col_inp, col_res = st.columns([1,1.6])
    with col_inp:
        fwd_rows=[]
        for yr in range(last_yr+1, last_yr+proj_n+1):
            px = st.number_input(f"CAL {yr} (EUR/MWh)",10.0,200.0,
                                  float(DEFAULT_FORWARD.get(yr,52.0)),0.5,key=f"fwd_{yr}")
            fwd_rows.append({"year":yr,"forward":px})
        fwd_df   = pd.DataFrame(fwd_rows)
        fwd_curve= dict(zip(fwd_df["year"],fwd_df["forward"]))
        st.info(
            "Connecteur API a venir — envoyez la documentation de votre source "
            "forward (Bloomberg, ICE, courtier) pour automatiser le chargement."
        )
    with col_res:
        # PPA per year table
        ref_fwd  = fwd_df["forward"].iloc[0] if len(fwd_df) else 55.0
        imb_pct  = imb_eur/ref_fwd if ref_fwd>0 else 0.035
        tot_disc = sd_ch+imb_pct+add_disc
        ppa      = ref_fwd*(1-tot_disc)-imb_eur
        cp_vals  = [ref_fwd*(1-s) for s in sd_vals]
        pnl_v    = [vol_mwh*(c-ppa)/1000 for c in cp_vals]
        be       = next((p for p,v in zip(pcts,pnl_v) if v<0),None)
        rows_ppa=[]
        for _,row in fwd_df.iterrows():
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
        st.markdown('<p class="tbl-note">Captured = Forward x (1 - Shape Discount projete). P&L = Captured - PPA Price.</p>',unsafe_allow_html=True)

        # Forward chart
        fig_fwd=go.Figure()
        fig_fwd.add_trace(go.Scatter(
            x=fwd_df["year"],y=fwd_df["forward"],
            mode="lines+markers+text",
            line=dict(color=C4,width=3),marker=dict(size=10,color=C4),
            text=[f"{v:.1f}" for v in fwd_df["forward"]],
            textposition="top center",textfont=dict(size=12,family="Calibri"),
            name="Forward EEX"))
        layout_plotly(fig_fwd,h=220)
        fig_fwd.update_xaxes(tickmode="array",tickvals=fwd_df["year"].tolist())
        fig_fwd.update_yaxes(title_text="EUR/MWh")
        st.plotly_chart(fig_fwd,use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Vue generale
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown(f"## PPA Pricing Dashboard — France Solaire")
    c_ttl,c_badge=st.columns([3,1])
    with c_ttl:
        st.markdown(f'<span style="font-size:13px;color:#666;">Agregateur — '
                    f'Achat PPA fixe / Vente spot capture — '
                    f'ENTSO-E {data_start.year}–{data_end.strftime("%Y-%m-%d")}</span>',
                    unsafe_allow_html=True)
    with c_badge:
        st.markdown(f'<div class="update-pill" style="float:right">Donnees au {data_end.strftime("%d/%m/%Y")}</div>',
                    unsafe_allow_html=True)
    st.markdown("---")

    # KPIs
    k1,k2,k3,k4,k5=st.columns(5)
    with k1:
        st.markdown(f'<div class="ppa-card"><div class="lbl">PPA Price (P{chosen_pct})</div>'
                    f'<div class="val">{ppa:.2f}</div><div class="lbl">EUR / MWh</div></div>',
                    unsafe_allow_html=True)
    with k2:
        cp_l=(asset_ann["cp_pct"].iloc[-1]*100 if has_asset
              else nat_ref["cp_nat_pct"].iloc[-1]*100)
        cl=C4 if cp_l>80 else (C2 if cp_l>65 else C1)
        st.markdown(f'<div class="kpi-card"><div class="kpi-lbl">CP% — {last_yr}</div>'
                    f'<div class="kpi-val" style="color:{cl}">{cp_l:.0f}%</div></div>',
                    unsafe_allow_html=True)
    with k3:
        sd_cur=(1-cp_l/100)*100
        cl2=C1 if sd_cur>25 else (C2 if sd_cur>15 else C4)
        st.markdown(f'<div class="kpi-card kpi-ora"><div class="kpi-lbl">Shape Discount</div>'
                    f'<div class="kpi-val" style="color:{cl2}">{sd_cur:.1f}%</div></div>',
                    unsafe_allow_html=True)
    with k4:
        p50_pnl=vol_mwh*(ref_fwd*(1-float(np.percentile(hist_sd_f,50)))-ppa)/1000
        cl3=C4 if p50_pnl>0 else C1
        st.markdown(f'<div class="kpi-card"><div class="kpi-lbl">P&L P50 (Ek/an)</div>'
                    f'<div class="kpi-val" style="color:{cl3}">{p50_pnl:+.0f}k</div></div>',
                    unsafe_allow_html=True)
    with k5:
        be_txt=f"P{be}" if be else ">P100"
        cl4=C4 if be and be>70 else C1
        st.markdown(f'<div class="kpi-card kpi-red"><div class="kpi-lbl">Break-even</div>'
                    f'<div class="kpi-val" style="color:{cl4}">{be_txt}</div></div>',
                    unsafe_allow_html=True)
    st.markdown("---")

    # Row 1: CP% history + projection
    r1a,r1b=st.columns(2)
    with r1a:
        section("Captured Price historique — 2014 a 2025")
        chart_desc(
            "Haut : Captured Price en % du spot (barres groupees). "
            "Une barre a 100% signifie que l'asset a vendu exactement au prix spot moyen. "
            "En dessous de 100%, l'asset a subi la cannibalisation solaire. "
            "Bas : memes valeurs en EUR/MWh avec le spot national pour reference."
        )
        fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=0.06,
            subplot_titles=["CP% (% du spot)","CP (EUR/MWh)"],row_heights=[0.55,0.45])
        ny=nat_ref["year"].tolist(); ncp=nat_ref["cp_nat_pct"].tolist()
        ne=nat_ref["cp_nat"].tolist(); ns=nat_ref["spot"].tolist()
        fig.add_trace(go.Bar(x=ny,y=ncp,name="M0 National",
            marker_color="rgba(59,81,69,0.45)",marker_line_color=C4,marker_line_width=1,
            text=[f"{v*100:.0f}%" for v in ncp],textposition="outside",
            textfont=dict(size=11,color=C4,family="Calibri")),row=1,col=1)
        if has_asset:
            ay=asset_ann["Year"].tolist(); acp=asset_ann["cp_pct"].tolist(); ae=asset_ann["cp_eur"].tolist()
            fig.add_trace(go.Bar(x=ay,y=acp,name=asset_name,
                marker_color="rgba(217,41,59,0.65)",marker_line_color=C1,marker_line_width=1,
                text=[f"{v*100:.0f}%" for v in acp],textposition="outside",
                textfont=dict(size=11,color=C1,family="Calibri")),row=1,col=1)
            fig.add_trace(go.Scatter(x=ay,y=ae,name=asset_name+" EUR",
                line=dict(color=C1,width=2.5),mode="lines+markers",marker=dict(size=7)),row=2,col=1)
        fig.add_trace(go.Scatter(x=ny,y=ncp,line=dict(color=C4,width=2,dash="dash"),
            mode="lines+markers",marker=dict(size=6,symbol="square"),showlegend=False),row=1,col=1)
        fig.add_hline(y=1.0,line=dict(color="#AAAAAA",width=1,dash="dot"),row=1,col=1)
        fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.25,line_width=0,row=1,col=1)
        fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.25,line_width=0,row=2,col=1)
        fig.add_annotation(x=2022,y=0.35,text="2022",showarrow=False,
            font=dict(color=C2,size=11,family="Calibri"),row=1,col=1)
        fig.add_trace(go.Scatter(x=ny,y=ns,name="Spot national",
            line=dict(color="#555",width=2,dash="dash"),mode="lines+markers",marker=dict(size=5)),row=2,col=1)
        fig.add_trace(go.Scatter(x=ny,y=ne,name="M0 national EUR",
            line=dict(color=C4,width=2),mode="lines+markers",marker=dict(size=5,symbol="square")),row=2,col=1)
        fig.update_yaxes(tickformat=".0%",row=1,col=1)
        layout_plotly(fig,h=540,legend_bottom=True)
        fig.update_layout(barmode="group")
        st.plotly_chart(fig,use_container_width=True)

    with r1b:
        section("Projection — Captured Price (%) avec incertitude")
        chart_desc(
            "Projection du Captured Price en % par annee en appliquant la tendance de regression "
            "sur le shape discount historique. Les bandes colorees representent l'incertitude : "
            "bande claire = P10-P90 (80% des cas), bande foncee = P25-P75 (50% des cas). "
            "La ligne P50 est le scenario central. Plus l'horizon est loin, plus la bande s'elargit."
        )
        fig2=go.Figure()
        if has_asset:
            fig2.add_trace(go.Scatter(x=asset_ann["Year"].tolist(),y=asset_ann["cp_pct"].tolist(),
                name="Asset (hist.)",mode="lines+markers",line=dict(color=C1,width=2.5),
                marker=dict(size=9,color=C1),
                text=[f"{v*100:.0f}%" for v in asset_ann["cp_pct"]],
                textposition="top center",textfont=dict(size=11,color=C1,family="Calibri")))
        fig2.add_trace(go.Scatter(x=nat_ref["year"].tolist(),y=nat_ref["cp_nat_pct"].tolist(),
            name="M0 national",mode="lines+markers",
            line=dict(color=C4,width=2,dash="dash"),marker=dict(size=7,symbol="square",color=C4)))
        tx=list(range(2014,last_yr+proj_n+1))
        fig2.add_trace(go.Scatter(x=tx,y=[1-(ic_u+sl_u*yr) for yr in tx],name="Tendance",
            line=dict(color="#AAAAAA",width=1.5,dash="dot"),mode="lines",opacity=0.8))
        py=proj["year"].tolist()
        p10=proj["p10"].tolist(); p25=proj["p25"].tolist()
        p50=proj["p50"].tolist(); p75=proj["p75"].tolist(); p90=proj["p90"].tolist()
        fig2.add_trace(go.Scatter(x=py+py[::-1],y=p90+p10[::-1],fill="toself",
            fillcolor="rgba(241,209,148,0.35)",line=dict(color="rgba(0,0,0,0)"),name="P10-P90"))
        fig2.add_trace(go.Scatter(x=py+py[::-1],y=p75+p25[::-1],fill="toself",
            fillcolor="rgba(242,145,109,0.35)",line=dict(color="rgba(0,0,0,0)"),name="P25-P75"))
        hl=asset_ann["cp_pct"].iloc[-1] if has_asset else nat_ref["cp_nat_pct"].iloc[-1]
        fig2.add_trace(go.Scatter(x=[last_yr]+py,y=[hl]+p50,name="P50",mode="lines+markers",
            line=dict(color=C4,width=3),marker=dict(size=8,color=C4)))
        for _,row in proj.iterrows():
            fig2.add_annotation(x=row["year"],y=row["p50"],
                text=f"P50:{row['p50']*100:.0f}%  P10:{row['p10']*100:.0f}%",
                showarrow=True,arrowhead=2,arrowcolor=C4,
                font=dict(size=10,color=C5,family="Calibri"),ax=30,ay=-35)
        fig2.add_vline(x=last_yr+0.5,line=dict(color="#BBBBBB",width=1,dash="dot"))
        fig2.add_vrect(x0=2021.5,x1=2022.5,fillcolor=C3,opacity=0.20,line_width=0)
        fig2.update_yaxes(tickformat=".0%")
        layout_plotly(fig2,h=540,legend_bottom=True)
        fig2.update_layout(
            title=dict(text=f"Pente : {-sl_u*100:.2f}%/an  —  R2 : {r2_u:.3f}  {'(excl. 2022)' if ex22 else ''}",
                       font=dict(size=12,color=C4,family="Calibri"),x=0.01),
            yaxis=dict(range=[0.15,1.22]))
        st.plotly_chart(fig2,use_container_width=True)

    st.markdown("---")

    # Row 2: Shape discount table + regression details
    section("Table de reference — Shape Discount et P&L par percentile")
    chart_desc(
        "Chaque ligne correspond a un percentile de l'historique des shape discounts. "
        "P10 = bonne annee (peu de cannibalisation). P90 = mauvaise annee. "
        "P74 = percentile utilise dans le tender WPD pour le pricing. "
        "La ligne coloree en vert correspond au percentile selectionne dans la sidebar."
    )
    kp=[5,10,15,20,25,30,35,40,45,50,55,60,65,70,74,75,80,85,90,95,100]
    trows=[]
    for p in kp:
        sdn=float(np.percentile(nat_ref["shape_disc"].dropna(),p))
        sda=(float(np.percentile(asset_ann["shape_disc"].dropna(),p)) if has_asset else None)
        cpa=ref_fwd*(1-sda) if sda is not None else None
        pnla=vol_mwh*(cpa-ppa)/1000 if cpa is not None else None
        row={"Pct":f"P{p}","Disc. national":f"{sdn*100:.1f}%","CP national":f"{(1-sdn)*100:.0f}%"}
        if has_asset:
            row["Disc. asset"]=f"{sda*100:.1f}%"
            row["CP asset"]=f"{(1-sda)*100:.0f}%"
            row["P&L Ek/an"]=f"{pnla:+.0f}k"
        trows.append(row)
    tdf=pd.DataFrame(trows)
    def hi(row):
        p=int(row["Pct"][1:])
        if p==chosen_pct: return [f"background-color:{C4};color:white;font-weight:bold"]*len(row)
        if p in [10,50,90]: return [f"background-color:{C4L}"]*len(row)
        if p==74: return [f"background-color:{C3L}"]*len(row)
        return [""]*len(row)
    st.dataframe(tdf.style.apply(hi,axis=1),use_container_width=True,height=420)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — Cannibalisation & marche
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    section("Heures a prix negatifs — par annee")
    chart_desc(
        "Nombre d'heures par an ou le prix spot EPEX est inferieur a 0 EUR/MWh. "
        "Cette metrique reflete l'excedent de production renouvelable. "
        "La tendance hausse est directement liee a la croissance du parc solaire et eolien. "
        "Au-dela de 300h/an (rouge), l'impact sur la cannibalisation devient significatif."
    )
    neg_ann=hourly[hourly["Spot"]<0].groupby("Year").size().reset_index(name="neg_hours")
    all_yrs=pd.DataFrame({"Year":sorted(hourly["Year"].unique())})
    neg_ann=all_yrs.merge(neg_ann,on="Year",how="left").fillna(0)
    neg_ann["neg_hours"]=neg_ann["neg_hours"].astype(int)
    fig_neg=go.Figure()
    bar_colors=[C1 if v>300 else (C2 if v>100 else C4) for v in neg_ann["neg_hours"]]
    fig_neg.add_trace(go.Bar(x=neg_ann["Year"],y=neg_ann["neg_hours"],
        marker_color=bar_colors,marker_line_color="white",marker_line_width=0.5,
        text=neg_ann["neg_hours"].astype(str),textposition="outside",
        textfont=dict(size=12,family="Calibri"),name="Heures prix negatifs"))
    if len(neg_ann)>=3:
        x=neg_ann["Year"].values.astype(float); y=neg_ann["neg_hours"].values.astype(float)
        sl_neg,ic_neg,_,_,_=stats.linregress(x,y)
        fut=list(range(int(neg_ann["Year"].min()),int(neg_ann["Year"].max())+4))
        fig_neg.add_trace(go.Scatter(x=fut,y=[max(0,ic_neg+sl_neg*yr) for yr in fut],
            mode="lines",line=dict(color=C1,width=2,dash="dash"),
            name=f"Tendance (+{sl_neg:.0f}h/an)"))
    fig_neg.add_hline(y=15,line=dict(color=C4,width=1.5,dash="dot"),
        annotation_text="Seuil CRE (15h)",annotation_font=dict(color=C4,size=11,family="Calibri"))
    fig_neg.update_layout(xaxis_title="Annee",yaxis_title="Heures spot < 0")
    layout_plotly(fig_neg,h=360,legend_bottom=True)
    st.plotly_chart(fig_neg,use_container_width=True)

    st.markdown("---")

    col3a,col3b=st.columns(2)
    with col3a:
        section("Profil mensuel de cannibalisation")
        chart_desc(
            "Shape discount moyen par mois calcule sur l'ensemble de l'historique. "
            "Les mois d'ete (avril a aout) presentent la cannibalisation la plus forte "
            "en raison du pic de production solaire nationale. "
            "Les barres d'erreur indiquent la variabilite inter-annuelle."
        )
        monthly=hourly.copy()
        monthly["Rev_nat"]=monthly["NatMW"]*monthly["Spot"]
        monthly_agg=monthly[monthly["Spot"]>0].groupby(["Year","Month"]).agg(
            spot_avg=("Spot","mean"),
            prod_nat=("NatMW","sum"),
            rev_nat=("Rev_nat","sum"),
        ).reset_index()
        monthly_agg["m0"]=monthly_agg["rev_nat"]/monthly_agg["prod_nat"].replace(0,np.nan)
        monthly_agg["shape_disc_m"]=1-monthly_agg["m0"]/monthly_agg["spot_avg"]
        month_avg=monthly_agg.groupby("Month")["shape_disc_m"].agg(["mean","std"]).reset_index()
        fig_mo=go.Figure()
        fig_mo.add_trace(go.Bar(x=MONTH_NAMES,y=month_avg["mean"],
            error_y=dict(type="data",array=month_avg["std"].tolist(),visible=True,
                         color="#AAAAAA",thickness=1.5),
            marker_color=[C1 if v>0.15 else (C2 if v>0.08 else C4) for v in month_avg["mean"]],
            text=[f"{v*100:.1f}%" for v in month_avg["mean"]],
            textposition="outside",textfont=dict(size=11,family="Calibri"),
            name="Shape discount mensuel"))
        fig_mo.add_hline(y=0,line=dict(color="#AAAAAA",width=1))
        fig_mo.update_yaxes(tickformat=".0%",title_text="Shape Discount moyen")
        layout_plotly(fig_mo,h=350)
        st.plotly_chart(fig_mo,use_container_width=True)

    with col3b:
        section("Scatter — CP% vs capacite solaire nationale")
        chart_desc(
            "Chaque point est une annee. L'axe horizontal represente la capacite solaire "
            "nationale moyenne installee (MW). La regression confirme la relation negative : "
            "plus la capacite est elevee, plus le Captured Price baisse. "
            "Les lignes verticales indiquent les objectifs PPE3 (2030 : 48 GW, 2035 : 65 GW)."
        )
        nat_mw_ann=hourly.groupby("Year")["NatMW"].mean().reset_index()
        sc_df=nat_ref.merge(nat_mw_ann.rename(columns={"Year":"year"}),on="year",how="inner")
        sc_df=sc_df[sc_df["NatMW"]>0]
        fig_sc=go.Figure()
        pt_colors=[C1 if y>=2024 else (C3 if y==2022 else C4) for y in sc_df["year"]]
        fig_sc.add_trace(go.Scatter(x=sc_df["NatMW"],y=sc_df["cp_nat_pct"],
            mode="markers+text",
            marker=dict(size=14,color=pt_colors,line=dict(width=1.5,color="white")),
            text=sc_df["year"].astype(str),textposition="top center",
            textfont=dict(size=11,family="Calibri"),name="National M0"))
        if len(sc_df)>=3:
            x=sc_df["NatMW"].values; y=sc_df["cp_nat_pct"].values
            sl_sc,ic_sc,r_sc,_,_=stats.linregress(x,y)
            x_line=np.linspace(0,75000,200)
            fig_sc.add_trace(go.Scatter(x=x_line,y=ic_sc+sl_sc*x_line,
                mode="lines",line=dict(color="#AAAAAA",width=2,dash="dash"),
                name=f"Regression (R2={r_sc**2:.2f})"))
        for gw,lbl,col in [(48000,"PPE3 2030",C2),(65000,"PPE3 2035",C1)]:
            fig_sc.add_vline(x=gw,line=dict(color=col,width=2,dash="dot"))
            fig_sc.add_annotation(x=gw,y=sc_df["cp_nat_pct"].min()*0.95,text=lbl,
                font=dict(color=col,size=11,family="Calibri"),showarrow=False,xanchor="left")
        fig_sc.update_yaxes(tickformat=".0%",title_text="Captured Price (%)")
        fig_sc.update_xaxes(title_text="Capacite solaire nationale (MW)")
        layout_plotly(fig_sc,h=350,legend_bottom=True)
        st.plotly_chart(fig_sc,use_container_width=True)

    st.markdown("---")

    section("Evolution annuelle du Shape Discount — variation d'une annee a l'autre")
    chart_desc(
        "Variation du shape discount d'une annee a la suivante, exprimee en points de pourcentage. "
        "Une barre rouge signifie que la cannibalisation s'est aggravee par rapport a l'annee precedente. "
        "Une barre verte indique une amelioration (rare, souvent due a la meteo ou a 2022). "
        "La tendance longue terme est clairement haussiere."
    )
    sd_s=nat_ref[["year","shape_disc"]].dropna().sort_values("year")
    sd_s["delta"]=sd_s["shape_disc"].diff()
    sd_s=sd_s.dropna(subset=["delta"])
    fig_wf=go.Figure()
    fig_wf.add_trace(go.Bar(x=sd_s["year"],y=sd_s["delta"],
        marker_color=[C1 if v>0 else C4 for v in sd_s["delta"]],
        text=[f"{v*100:+.1f}pp" for v in sd_s["delta"]],
        textposition="outside",textfont=dict(size=11,family="Calibri"),
        name="Variation annuelle shape discount"))
    fig_wf.add_hline(y=0,line=dict(color="#AAAAAA",width=1.5))
    fig_wf.update_yaxes(tickformat=".1%",title_text="Delta Shape Discount")
    layout_plotly(fig_wf,h=320)
    st.plotly_chart(fig_wf,use_container_width=True)

    # Monthly heatmap
    st.markdown("---")
    section("Heatmap — Shape Discount mensuel par annee")
    chart_desc(
        "Representation matricielle du shape discount : lignes = annees, colonnes = mois. "
        "Rouge = forte cannibalisation, vert = faible cannibalisation. "
        "Permet d'identifier les annees et mois les plus impactes."
    )
    pivot=monthly_agg.pivot(index="Year",columns="Month",values="shape_disc_m")
    pivot.columns=[MONTH_NAMES[c-1] for c in pivot.columns]
    fig_hm=go.Figure(data=go.Heatmap(
        z=pivot.values*100,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0,C4],[0.5,C3],[1,C1]],
        text=[[f"{v:.1f}%" for v in row] for row in pivot.values*100],
        texttemplate="%{text}",textfont=dict(size=10,family="Calibri"),
        colorbar=dict(title="Shape Disc (%)",thickness=12)))
    layout_plotly(fig_hm,h=340)
    fig_hm.update_xaxes(title_text="Mois")
    fig_hm.update_yaxes(title_text="Annee")
    st.plotly_chart(fig_hm,use_container_width=True)

    # Profil horaire
    if has_asset and asset_raw is not None:
        st.markdown("---")
        section("Profil horaire — Production vs Spot moyen")
        chart_desc(
            "Production moyenne de l'asset par heure de la journee (barres) et prix spot moyen correspondant (ligne). "
            "La concentration de la production entre 10h et 16h coincide avec les heures de spot le plus bas, "
            "ce qui explique mecaniquement pourquoi le Captured Price est inferieur au spot moyen."
        )
        try:
            dc=next((c for c in asset_raw.columns if "date" in c.lower()),asset_raw.columns[0])
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
            fig5.add_trace(go.Bar(x=hp["Hour"],y=hp["Prod"],name="Production moy. (MWh/h)",
                marker_color=f"rgba(59,81,69,0.55)"),secondary_y=False)
            fig5.add_trace(go.Scatter(x=hp["Hour"],y=hp["Spot"],name="Spot moy. (EUR/MWh)",
                mode="lines+markers",line=dict(color=C5,width=3),marker=dict(size=7)),secondary_y=True)
            fig5.update_xaxes(tickvals=list(range(0,24,2)),ticktext=[f"{h:02d}h" for h in range(0,24,2)])
            fig5.update_yaxes(title_text="Production (MWh/h)",secondary_y=False)
            fig5.update_yaxes(title_text="Spot moyen (EUR/MWh)",secondary_y=True)
            layout_plotly(fig5,h=300,legend_bottom=True)
            st.plotly_chart(fig5,use_container_width=True)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — Sensibilite & scenarios
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    # PnL sensitivity
    section("P&L annuel en fonction du percentile de cannibalisation")
    chart_desc(
        "Pour chaque percentile de shape discount historique (axe horizontal), "
        "ce graphique montre le P&L annuel de l'agregateur en EUR k. "
        "Zone verte = profit. Zone rouge = perte. "
        "La ligne verticale rouge indique le percentile de break-even. "
        "La bande translucide montre l'impact d'un stress volume +/-" + str(vol_stress) + "%%."
    )
    fig3=go.Figure()
    px_=[p for p,v in zip(pcts,pnl_v) if v>=0]; py_=[v for v in pnl_v if v>=0]
    nx_=[p for p,v in zip(pcts,pnl_v) if v<0]; ny_=[v for v in pnl_v if v<0]
    if px_: fig3.add_trace(go.Scatter(x=px_,y=py_,fill="tozeroy",
        fillcolor=f"rgba(59,81,69,0.12)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    if nx_: fig3.add_trace(go.Scatter(x=nx_,y=ny_,fill="tozeroy",
        fillcolor=f"rgba(217,41,59,0.10)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    fig3.add_trace(go.Scatter(x=pcts,y=pnl_v,name="P&L (Ek/an)",
        mode="lines",line=dict(color=C4,width=2.5)))
    pc_=pnl_v[chosen_pct-1]
    fig3.add_trace(go.Scatter(x=[chosen_pct],y=[pc_],mode="markers+text",
        marker=dict(size=14,color=C4 if pc_>=0 else C1,line=dict(width=2,color="white")),
        text=[f"P{chosen_pct} : {pc_:.0f}k"],textposition="top right",
        name=f"P{chosen_pct} choisi",textfont=dict(size=12,color=C5,family="Calibri")))
    pu=[vol_mwh*(1+vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    pd_=[vol_mwh*(1-vol_stress/100)*(c-ppa)/1000 for c in cp_vals]
    fig3.add_trace(go.Scatter(x=pcts+pcts[::-1],y=pu+pd_[::-1],fill="toself",
        fillcolor="rgba(241,209,148,0.30)",line=dict(color="rgba(0,0,0,0)"),
        name=f"+/-{vol_stress}%% volume"))
    fig3.add_hline(y=0,line=dict(color="#AAAAAA",width=1.5))
    if be:
        fig3.add_vline(x=be,line=dict(color=C1,width=2,dash="dot"),
            annotation_text=f"Break-even P{be}",
            annotation_font=dict(color=C1,size=12,family="Calibri"))
    fig3.update_layout(xaxis_title="Percentile de shape discount",yaxis_title="P&L annuel (Ek)")
    layout_plotly(fig3,h=400,legend_bottom=True)
    st.plotly_chart(fig3,use_container_width=True)
    if be:
        st.warning(f"Break-even a P{be} — l'agregateur perd de l'argent si la cannibalisation depasse le P{be} de l'historique.")

    st.markdown("---")
    section("Scenarios de stress — P&L cumule sur la duree du PPA")
    chart_desc(
        "Chaque barre represente le P&L cumule sur " + str(proj_n) + " ans pour un scenario donne. "
        "Les triangles indiquent le P10 (scenario pessimiste) et P90 (scenario optimiste). "
        "Stress total = spot -" + str(spot_stress) + "%% + cannib +" + str(vol_stress) + "%% + vol -" + str(vol_stress) + "%%."
    )
    sd_med=float(np.percentile(hist_sd_f,50)) if len(hist_sd_f) else 0.15
    scens=[
        ("Base",1.00,0.00,0.00),
        (f"Cannib +{vol_stress}%%",1.00,+vol_stress/100,0.00),
        (f"Cannib -{vol_stress}%%",1.00,-vol_stress/100,0.00),
        (f"Spot +{spot_stress}%%",1+spot_stress/100,0.00,0.00),
        (f"Spot -{spot_stress}%%",1-spot_stress/100,0.00,0.00),
        (f"Vol +{vol_stress}%%",1.00,0.00,+vol_stress/100),
        (f"Vol -{vol_stress}%%",1.00,0.00,-vol_stress/100),
        ("Stress total",1-spot_stress/100,+vol_stress/100,-vol_stress/100),
        ("Bull total",1+spot_stress/100,-vol_stress/100,+vol_stress/100),
    ]
    sn,sv50,sv10,sv90=[],[],[],[]
    scenarios_export=[]
    for name,sm,da,va in scens:
        p50t=vol_mwh*(1+va)*(sm*ref_fwd*(1-(sd_med+da))-ppa)/1000*proj_n
        sdp10=float(np.percentile(hist_sd_f,10))+da if len(hist_sd_f) else 0.1
        sdp90=float(np.percentile(hist_sd_f,90))+da if len(hist_sd_f) else 0.3
        p10t=vol_mwh*(1+va)*(sm*ref_fwd*(1-sdp90)-ppa)/1000*proj_n
        p90t=vol_mwh*(1+va)*(sm*ref_fwd*(1-sdp10)-ppa)/1000*proj_n
        sn.append(name); sv50.append(p50t); sv10.append(p10t); sv90.append(p90t)
        scenarios_export.append({"Scenario":name,"P10 (Ek)":p10t,"P50 (Ek)":p50t,"P90 (Ek)":p90t})
    fig4=go.Figure()
    fig4.add_trace(go.Bar(name="P50",x=sn,y=sv50,
        marker_color=[f"rgba(59,81,69,0.80)" if v>=0 else f"rgba(217,41,59,0.80)" for v in sv50],
        text=[f"{v:+.0f}k" for v in sv50],textposition="outside",
        textfont=dict(size=12,family="Calibri")))
    fig4.add_trace(go.Scatter(name="P10 (pessimiste)",x=sn,y=sv10,
        mode="markers",marker=dict(symbol="triangle-down",size=12,color=C1)))
    fig4.add_trace(go.Scatter(name="P90 (optimiste)",x=sn,y=sv90,
        mode="markers",marker=dict(symbol="triangle-up",size=12,color=C4)))
    fig4.add_hline(y=0,line=dict(color="#AAAAAA",width=1.5))
    fig4.update_layout(xaxis_title="Scenario",yaxis_title=f"P&L cumule {proj_n} ans (Ek)",bargap=0.3)
    layout_plotly(fig4,h=380,legend_bottom=True)
    st.plotly_chart(fig4,use_container_width=True)

    # Scenarios table
    st.markdown("---")
    section("Detail des scenarios — tableau")
    chart_desc("Memes donnees que le graphique ci-dessus. P10 = 10eme percentile historique de cannibalisation. P90 = 90eme percentile.")
    sc_df_tbl=pd.DataFrame(scenarios_export)
    sc_df_tbl["P10 (Ek)"]=sc_df_tbl["P10 (Ek)"].apply(lambda x:f"{x:+.0f}k")
    sc_df_tbl["P50 (Ek)"]=sc_df_tbl["P50 (Ek)"].apply(lambda x:f"{x:+.0f}k")
    sc_df_tbl["P90 (Ek)"]=sc_df_tbl["P90 (Ek)"].apply(lambda x:f"{x:+.0f}k")
    st.dataframe(sc_df_tbl,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 5 — Export & extracteur SPOT
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    col_ex1,col_ex2=st.columns(2)

    with col_ex1:
        section("Export Excel — toutes les donnees")
        chart_desc(
            "Genere un fichier Excel contenant toutes les tables visibles dans le dashboard : "
            "historique national, historique asset, courbe forward, projection P10-P90, "
            "table des percentiles P1-P100, scenarios de stress, stats mensuelles, donnees horaires."
        )
        if st.button("Generer le fichier Excel", type="primary"):
            with st.spinner("Generation en cours..."):
                excel_buf=build_excel(nat_ref,hourly,asset_ann,has_asset,
                    asset_name,proj,pcts,sd_vals,pnl_v,ppa,
                    scenarios_export,fwd_curve)
                st.download_button(
                    label="Telecharger ppa_dashboard_export.xlsx",
                    data=excel_buf,
                    file_name="ppa_dashboard_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.success("Fichier pret.")

    with col_ex2:
        section("Format du fichier courbe de charge")
        chart_desc("Format attendu pour uploader votre production horaire dans la sidebar.")
        st.code("Date,Prod_MWh\n2024-01-01 00:00:00,0.0\n2024-01-01 10:00:00,4.2\n2024-01-01 11:00:00,7.8", language="text")
        with open(DATA_DIR.parent / "exemple_courbe_charge.csv","rb") as f:
            st.download_button("Telecharger l'exemple CSV",data=f.read(),
                file_name="exemple_courbe_charge.csv",mime="text/csv")

    st.markdown("---")
    section("Extracteur de donnees SPOT — ENTSO-E Transparency Platform")
    chart_desc(
        "Telechargez les prix spot horaires et la production solaire nationale directement depuis ENTSO-E "
        "dans le format exact attendu par ce dashboard. "
        "Le fichier CSV genere peut etre utilise pour mettre a jour manuellement les donnees de reference."
    )
    col_e1,col_e2=st.columns(2)
    with col_e1:
        api_key_in=st.text_input("Cle API ENTSO-E",type="password",
            help="Obtenir sur transparency.entsoe.eu — My Account — Web API Security Token")
        country_c=st.selectbox("Pays",["FR","DE","ES","BE","NL","IT","GB"],index=0)
        d_start=st.date_input("Date debut",value=pd.Timestamp("2024-01-01"))
        d_end=st.date_input("Date fin",value=pd.Timestamp("2024-12-31"))
        incl_solar=st.checkbox("Inclure production solaire (NatMW)",value=True)
    with col_e2:
        st.markdown("**Format de sortie**")
        st.code("Date,Year,Month,Hour,Spot,NatMW\n2024-01-01 00:00:00,2024,1,0,52.3,1250.0\n...",language="text")
        if not api_key_in:
            st.info("Entrez votre cle API ENTSO-E pour activer l'extracteur.\n\n"
                    "1. transparency.entsoe.eu\n2. My Account Settings\n3. Web API Security Token")
        else:
            if st.button("Extraire les donnees", type="primary"):
                with st.spinner("Connexion a ENTSO-E..."):
                    try:
                        from entsoe import EntsoePandasClient
                        import time
                        client=EntsoePandasClient(api_key=api_key_in)
                        start=pd.Timestamp(d_start,tz="Europe/Paris")
                        end=pd.Timestamp(d_end,tz="Europe/Paris")+pd.Timedelta(days=1)
                        prices=client.query_day_ahead_prices(country_c,start=start,end=end)
                        prices=prices.resample("1h").mean()
                        df_out=pd.DataFrame({"Spot":prices}); df_out.index.name="Date"
                        df_out=df_out.reset_index()
                        df_out["Date"]=df_out["Date"].dt.tz_localize(None)
                        df_out["Year"]=df_out["Date"].dt.year
                        df_out["Month"]=df_out["Date"].dt.month
                        df_out["Hour"]=df_out["Date"].dt.hour
                        df_out["NatMW"]=0.0
                        if incl_solar:
                            try:
                                time.sleep(1)
                                solar=client.query_generation(country_c,start=start,end=end,psr_type="B16")
                                if isinstance(solar,pd.DataFrame): solar=solar.sum(axis=1)
                                solar=solar.resample("1h").mean()
                                solar.index=solar.index.tz_localize(None)
                                df_out=df_out.set_index("Date").join(solar.rename("NatMW_n"),how="left")
                                df_out["NatMW"]=df_out["NatMW_n"].fillna(0); df_out=df_out.drop(columns=["NatMW_n"]).reset_index()
                            except Exception as e2:
                                st.warning(f"Production solaire non disponible : {e2}")
                        df_out=df_out[["Date","Year","Month","Hour","Spot","NatMW"]].dropna(subset=["Spot"])
                        st.success(f"{len(df_out):,} heures extraites — {d_start} a {d_end}")
                        st.dataframe(df_out.head(24),use_container_width=True)
                        st.download_button("Telecharger CSV",
                            data=df_out.to_csv(index=False).encode("utf-8"),
                            file_name=f"spot_{country_c}_{d_start}_{d_end}.csv",
                            mime="text/csv")
                    except ImportError:
                        st.error("entsoe-py non installe. Ajouter dans requirements.txt.")
                    except Exception as e:
                        st.error(f"Erreur ENTSO-E : {e}")

st.markdown("---")
st.markdown(
    f'<span style="font-size:11px;color:#888;font-family:Calibri,sans-serif;">'
    f'ENTSO-E France {data_start.year}–{data_end.strftime("%Y-%m-%d")} '
    f'— {len(hourly):,} heures — Mise a jour quotidienne automatique (GitHub Actions) '
    f'— Logique WPD Tender format — Shape Discount = 1 - CP%%'
    f'</span>',
    unsafe_allow_html=True
)
