"""
PPA Pricing Dashboard — France Solaire  v2
===========================================
Streamlit app with auto-refresh from GitHub Actions daily updates.
Data source: ENTSO-E Transparency Platform (2014 → yesterday).
"""

import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

st.set_page_config(page_title="PPA Pricing Dashboard", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.metric-card{background:#f0f4f8;border-left:4px solid #2E75B6;padding:12px 16px;border-radius:6px;margin:4px 0}
.metric-value{font-size:1.6rem;font-weight:700;color:#1F3864}
.metric-label{font-size:0.8rem;color:#666;text-transform:uppercase}
.ppa-output{background:linear-gradient(135deg,#1A6B3A,#2E9E5A);color:white;padding:20px 24px;border-radius:10px;text-align:center;margin:10px 0}
.ppa-output .value{font-size:2.2rem;font-weight:800}
.ppa-output .label{font-size:0.85rem;opacity:0.85}
.update-badge{background:#E8F4FB;border:1px solid #2E75B6;border-radius:20px;padding:4px 12px;font-size:0.78rem;color:#1F3864;display:inline-block}
.section-title{font-size:1.05rem;font-weight:700;color:#1F3864;border-bottom:2px solid #2E75B6;padding-bottom:4px;margin:18px 0 10px 0}
[data-testid="stSidebar"]{background:#1F3864}
</style>""", unsafe_allow_html=True)

BLUE="#2E75B6"; GREEN="#1A6B3A"; ORANGE="#C55A11"; RED="#C00000"; GREY="#888888"
DATA_DIR = Path(__file__).parent / "data"


@st.cache_data(ttl=3600)
def load_nat():
    return pd.read_csv(DATA_DIR / "nat_reference.csv")

@st.cache_data(ttl=3600)
def load_hourly():
    return pd.read_csv(DATA_DIR / "hourly_spot.csv", parse_dates=["Date"])

def load_update_log():
    p = DATA_DIR / "last_update.txt"
    return p.read_text() if p.exists() else "Données initiales."

def compute_asset_annual(hourly, asset_df):
    a = asset_df.copy()
    a["Date"] = pd.to_datetime(a["Date"])
    a = a.set_index("Date").resample("1h").mean().reset_index()
    m = hourly.merge(a[["Date","Prod_MWh"]], on="Date", how="inner")
    m = m[m["Spot"]>0].copy()
    m["Rev"] = m["Prod_MWh"]*m["Spot"]
    ann = m.groupby("Year").agg(
        prod_mwh=("Prod_MWh","sum"), revenue=("Rev","sum"),
        spot_avg=("Spot","mean"), prod_hours=("Prod_MWh",lambda x:(x>0).sum()),
        neg_hours=("Spot",lambda x:(x<0).sum()), nat_mw=("NatMW","mean"),
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
    yrs=list(range(last_yr+1,last_yr+n+1))
    rows=[]
    for t,yr in enumerate(yrs):
        fsd=ic+sl*yr; cs=sig*np.sqrt(t+1)
        rows.append({"year":yr,"fsd":fsd,
                     "p10":1-(fsd+1.28*cs),"p25":1-(fsd+0.674*cs),
                     "p50":1-fsd,
                     "p75":1-(fsd-0.674*cs),"p90":1-(fsd-1.28*cs)})
    return pd.DataFrame(rows)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ PPA Dashboard")
    upd = load_update_log()
    st.markdown(f'<div class="update-badge">🔄 {upd.split(chr(10))[0]}</div>',
                unsafe_allow_html=True)
    with st.expander("Détails"):
        st.text(upd)
    st.markdown("---")
    st.markdown("### 📈 Marché")
    fwd_price    = st.number_input("CAL Forward (EUR/MWh)", 30.0, 150.0, 55.0, 0.5)
    n_reg        = st.slider("Années de régression (N)", 2, 12, 3)
    ex22         = st.toggle("Exclure 2022", value=False)
    st.markdown("---")
    st.markdown("### 💰 PPA")
    margin_eur   = st.number_input("Marge cible (EUR/MWh)", 0.0, 20.0, 2.0, 0.25)
    imb_eur      = st.number_input("Coût imbalance (EUR/MWh)", 0.0, 10.0, 1.9, 0.1)
    add_disc     = st.slider("Décote additionnelle (%)", 0.0, 10.0, 0.0, 0.25)/100
    st.markdown("---")
    st.markdown("### 📊 Sensibilité")
    chosen_pct   = st.slider("Percentile choisi", 1, 100, 74)
    proj_yrs     = st.slider("Horizon projection (ans)", 1, 10, 5)
    vol_stress   = st.slider("Stress volume (±%)", 0, 30, 20)
    spot_stress  = st.slider("Stress spot (±%)", 0, 30, 20)
    st.markdown("---")
    st.markdown("### 📁 Courbe de charge")
    uploaded     = st.file_uploader("Production horaire", type=["xlsx","csv"],
                                     help="Colonnes : Date | Prod_MWh")
    st.caption("Date (YYYY-MM-DD HH:00) | Prod_MWh")
    st.markdown("---")
    if st.button("♻️ Vider le cache"):
        st.cache_data.clear(); st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────────
nat_ref = load_nat()
hourly  = load_hourly()
data_end   = pd.to_datetime(hourly["Date"]).max()
data_start = pd.to_datetime(hourly["Date"]).min()

asset_ann=None; asset_name=None; asset_raw=None
if uploaded:
    try:
        asset_raw = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                     else pd.read_excel(uploaded))
        dc=next((c for c in asset_raw.columns if "date" in c.lower() or "time" in c.lower()),asset_raw.columns[0])
        pc=next((c for c in asset_raw.columns if any(k in c.lower() for k in ["prod","mwh","power","gen","kwh"])),asset_raw.columns[1])
        asset_raw[dc]=pd.to_datetime(asset_raw[dc],errors="coerce")
        asset_raw[pc]=pd.to_numeric(asset_raw[pc],errors="coerce")
        if asset_raw[pc].max()>10000: asset_raw[pc]/=1000
        df_a=asset_raw[[dc,pc]].rename(columns={dc:"Date",pc:"Prod_MWh"})
        asset_ann=compute_asset_annual(hourly,df_a)
        asset_name=uploaded.name.rsplit(".",1)[0]
        st.sidebar.success(f"✅ {asset_name}\n{len(asset_ann)} ans • {asset_ann['prod_gwh'].mean():.1f} GWh/yr")
    except Exception as e:
        st.sidebar.error(f"❌ {e}")

has_asset = asset_ann is not None and len(asset_ann)>=2
work      = asset_ann if has_asset else nat_ref.rename(columns={"year":"Year"})
sl,ic,r2  = fit_reg(work,n_reg,False)
sl2,ic2,r22=fit_reg(work,n_reg,True)
sl_u=sl2 if ex22 else sl; ic_u=ic2 if ex22 else ic; r2_u=r22 if ex22 else r2
last_yr = int(asset_ann["Year"].iloc[-1]) if has_asset else int(nat_ref["year"].max())
hist_sd = asset_ann["shape_disc"].dropna() if has_asset else nat_ref["shape_disc"].dropna()
hist_sd_f = (work[work["Year"]!=2022]["shape_disc"].dropna() if ex22 else hist_sd)
sd_ch    = float(np.percentile(hist_sd_f,chosen_pct)) if len(hist_sd_f) else 0.15
imb_pct  = imb_eur/fwd_price
tot_disc = sd_ch+imb_pct+add_disc
mult     = 1-tot_disc
ppa      = fwd_price*mult-imb_eur
vol_mwh  = asset_ann["prod_mwh"].mean() if has_asset else 52000.0
proj     = project_cp(sl_u,ic_u,last_yr,proj_yrs)
pcts     = list(range(1,101))
sd_v     = [float(np.percentile(hist_sd_f,p)) if len(hist_sd_f) else 0.15 for p in pcts]
cp_v     = [fwd_price*(1-s) for s in sd_v]
pnl_v    = [vol_mwh*(c-ppa)/1000 for c in cp_v]
be       = next((p for p,v in zip(pcts,pnl_v) if v<0),None)

# ── Title + KPIs ──────────────────────────────────────────────────────────────
st.title("⚡ PPA Pricing Dashboard — France Solaire")
tc,bc=st.columns([3,1])
with tc: st.caption(f"Agrégateur • Achat PPA fixe / Vente spot capturé • ENTSO-E {data_start.year}–{data_end.strftime('%Y-%m-%d')}")
with bc: st.markdown(f'<div class="update-badge" style="float:right">📡 Au {data_end.strftime("%d/%m/%Y")}</div>',unsafe_allow_html=True)

k1,k2,k3,k4,k5=st.columns(5)
with k1:
    st.markdown(f'<div class="ppa-output"><div class="label">PPA Price (P{chosen_pct})</div><div class="value">{ppa:.2f}</div><div class="label">EUR / MWh</div></div>',unsafe_allow_html=True)
with k2:
    cp_l=(asset_ann["cp_pct"].iloc[-1]*100 if has_asset else nat_ref["cp_nat_pct"].iloc[-1]*100)
    col=GREEN if cp_l>80 else (ORANGE if cp_l>65 else RED)
    st.markdown(f'<div class="metric-card" style="border-color:{col}"><div class="metric-label">CP% — {last_yr}</div><div class="metric-value" style="color:{col}">{cp_l:.0f}%</div></div>',unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="metric-card" style="border-color:{ORANGE}"><div class="metric-label">Shape Discount</div><div class="metric-value" style="color:{ORANGE}">{(1-cp_l/100)*100:.1f}%</div></div>',unsafe_allow_html=True)
with k4:
    p50_pnl=vol_mwh*(fwd_price*(1-float(np.percentile(hist_sd_f,50)))-ppa)/1000
    col=GREEN if p50_pnl>0 else RED
    st.markdown(f'<div class="metric-card" style="border-color:{col}"><div class="metric-label">P&L P50 (EUR k/an)</div><div class="metric-value" style="color:{col}">{p50_pnl:+.0f}k</div></div>',unsafe_allow_html=True)
with k5:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Formule PPA</div><div style="font-size:0.9rem;font-weight:700;color:#1F3864">{mult:.4f} × {fwd_price:.0f} − {imb_eur:.1f}</div><div style="font-size:0.75rem;color:#666">Décote totale: {tot_disc*100:.1f}% (P{chosen_pct})</div></div>',unsafe_allow_html=True)

st.markdown("---")

# ── Row 1: Historique + Projection ───────────────────────────────────────────
c1,c2=st.columns(2)
with c1:
    st.markdown('<div class="section-title">📊 Historique — Captured Price</div>',unsafe_allow_html=True)
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=0.08,
        subplot_titles=["CP% (% of spot)","CP (EUR/MWh)"],row_heights=[0.55,0.45])
    ny=nat_ref["year"].tolist(); ncp=nat_ref["cp_nat_pct"].tolist()
    ne=nat_ref["cp_nat"].tolist(); ns=nat_ref["spot"].tolist()
    fig.add_trace(go.Bar(x=ny,y=ncp,name="National M0",marker_color="rgba(150,150,150,0.6)",
        marker_line_color="rgba(100,100,100,0.8)",marker_line_width=1,
        text=[f"{v*100:.0f}%" for v in ncp],textposition="outside",textfont=dict(size=9,color=GREY)),row=1,col=1)
    if has_asset:
        ay=asset_ann["Year"].tolist(); acp=asset_ann["cp_pct"].tolist(); ae=asset_ann["cp_eur"].tolist()
        fig.add_trace(go.Bar(x=ay,y=acp,name=asset_name or "Asset",
            marker_color="rgba(46,117,182,0.75)",marker_line_color=BLUE,marker_line_width=1,
            text=[f"{v*100:.0f}%" for v in acp],textposition="outside",textfont=dict(size=9,color=BLUE)),row=1,col=1)
        fig.add_trace(go.Scatter(x=ay,y=acp,mode="lines+markers",line=dict(color=BLUE,width=2.5),
            marker=dict(size=7),showlegend=False),row=1,col=1)
        fig.add_trace(go.Scatter(x=ay,y=ae,name=asset_name,line=dict(color=BLUE,width=2.5),
            mode="lines+markers",marker=dict(size=7)),row=2,col=1)
    fig.add_trace(go.Scatter(x=ny,y=ncp,line=dict(color=GREY,width=2,dash="dash"),
        mode="lines+markers",marker=dict(size=6,symbol="square"),showlegend=False),row=1,col=1)
    fig.add_hline(y=1.0,line=dict(color=GREY,width=1,dash="dot"),row=1,col=1)
    fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor="orange",opacity=0.07,line_width=0,row=1,col=1)
    fig.add_trace(go.Scatter(x=ny,y=ns,name="Nat spot",line=dict(color="#333",width=2,dash="dash"),
        mode="lines+markers",marker=dict(size=5)),row=2,col=1)
    fig.add_trace(go.Scatter(x=ny,y=ne,name="Nat M0 EUR",line=dict(color=GREY,width=2),
        mode="lines+markers",marker=dict(size=5,symbol="square")),row=2,col=1)
    fig.add_vrect(x0=2021.5,x1=2022.5,fillcolor="orange",opacity=0.07,line_width=0,row=2,col=1)
    fig.update_yaxes(tickformat=".0%",row=1,col=1)
    fig.update_layout(height=520,barmode="group",
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
        plot_bgcolor="#FAFAFA",paper_bgcolor="white",margin=dict(l=0,r=0,t=40,b=0),
        font=dict(family="Arial",size=11))
    st.plotly_chart(fig,use_container_width=True)

with c2:
    st.markdown('<div class="section-title">🔮 Projection — Captured Price (%)</div>',unsafe_allow_html=True)
    fig2=go.Figure()
    if has_asset:
        fig2.add_trace(go.Scatter(x=asset_ann["Year"].tolist(),y=asset_ann["cp_pct"].tolist(),
            name="Asset (hist.)",mode="lines+markers",line=dict(color=BLUE,width=2.5),marker=dict(size=8),
            text=[f"{v*100:.0f}%" for v in asset_ann["cp_pct"]],textposition="top center",textfont=dict(size=8,color=BLUE)))
    fig2.add_trace(go.Scatter(x=nat_ref["year"].tolist(),y=nat_ref["cp_nat_pct"].tolist(),
        name="National M0",mode="lines+markers",line=dict(color=GREY,width=2,dash="dash"),marker=dict(size=6,symbol="square")))
    tx=list(range(2014,last_yr+proj_yrs+1))
    fig2.add_trace(go.Scatter(x=tx,y=[1-(ic_u+sl_u*yr) for yr in tx],name="Tendance",
        line=dict(color=GREY,width=1.5,dash="dash"),mode="lines",opacity=0.7))
    py=proj["year"].tolist()
    p10=proj["cp_p10"].tolist(); p25=proj["cp_p25"].tolist()
    p50=proj["cp_p50"].tolist(); p75=proj["cp_p75"].tolist(); p90=proj["cp_p90"].tolist()
    fig2.add_trace(go.Scatter(x=py+py[::-1],y=p90+p10[::-1],fill="toself",
        fillcolor="rgba(46,117,182,0.12)",line=dict(color="rgba(0,0,0,0)"),name="P10–P90"))
    fig2.add_trace(go.Scatter(x=py+py[::-1],y=p75+p25[::-1],fill="toself",
        fillcolor="rgba(46,117,182,0.25)",line=dict(color="rgba(0,0,0,0)"),name="P25–P75"))
    hl=asset_ann["cp_pct"].iloc[-1] if has_asset else nat_ref["cp_nat_pct"].iloc[-1]
    fig2.add_trace(go.Scatter(x=[last_yr]+py,y=[hl]+p50,name="P50",mode="lines+markers",
        line=dict(color=BLUE,width=2.5),marker=dict(size=6)))
    for _,row in proj.iterrows():
        fig2.add_annotation(x=row["year"],y=row["cp_p50"],
            text=f"P50:{row['cp_p50']*100:.0f}%<br>P10:{row['cp_p10']*100:.0f}%",
            showarrow=True,arrowhead=2,arrowcolor=BLUE,font=dict(size=8,color=BLUE),ax=25,ay=-35)
    fig2.add_vline(x=last_yr+0.5,line=dict(color=GREY,width=1,dash="dot"))
    fig2.add_vrect(x0=2021.5,x1=2022.5,fillcolor="orange",opacity=0.07,line_width=0)
    fig2.update_yaxes(tickformat=".0%")
    fig2.update_layout(height=520,
        title=dict(text=f"slope: {-sl_u*100:.2f}%/yr  |  R²: {r2_u:.3f}  |  {'Excl.' if ex22 else 'Incl.'} 2022",
                   font=dict(size=10,color=BLUE),x=0.01),
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
        plot_bgcolor="#FAFAFA",paper_bgcolor="white",margin=dict(l=0,r=0,t=60,b=0),
        yaxis=dict(range=[0.15,1.22]),font=dict(family="Arial",size=11))
    st.plotly_chart(fig2,use_container_width=True)

st.markdown("---")

# ── Row 2: PnL sensitivity + Percentile table ─────────────────────────────────
cp2,cp3=st.columns([1.1,1])
with cp2:
    st.markdown('<div class="section-title">💶 P&L — Sensibilité cannibalisation</div>',unsafe_allow_html=True)
    fig3=go.Figure()
    px_=[p for p,v in zip(pcts,pnl_v) if v>=0]; py_=[v for v in pnl_v if v>=0]
    nx_=[p for p,v in zip(pcts,pnl_v) if v<0];  ny_=[v for v in pnl_v if v<0]
    if px_: fig3.add_trace(go.Scatter(x=px_,y=py_,fill="tozeroy",fillcolor="rgba(26,107,58,0.15)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    if nx_: fig3.add_trace(go.Scatter(x=nx_,y=ny_,fill="tozeroy",fillcolor="rgba(192,0,0,0.12)",line=dict(color="rgba(0,0,0,0)"),showlegend=False))
    fig3.add_trace(go.Scatter(x=pcts,y=pnl_v,name="P&L (EUR k/an)",mode="lines",line=dict(color=BLUE,width=2.5)))
    pc_=pnl_v[chosen_pct-1]
    fig3.add_trace(go.Scatter(x=[chosen_pct],y=[pc_],mode="markers+text",
        marker=dict(size=14,color=GREEN if pc_>=0 else RED,line=dict(width=2,color="white")),
        text=[f"P{chosen_pct}: {pc_:.0f}k"],textposition="top right",
        name=f"P{chosen_pct}",textfont=dict(size=10,color=GREEN if pc_>=0 else RED)))
    pu=[vol_mwh*(1+vol_stress/100)*(c-ppa)/1000 for c in cp_v]
    pd_=[vol_mwh*(1-vol_stress/100)*(c-ppa)/1000 for c in cp_v]
    fig3.add_trace(go.Scatter(x=pcts+pcts[::-1],y=pu+pd_[::-1],fill="toself",
        fillcolor="rgba(46,117,182,0.08)",line=dict(color="rgba(0,0,0,0)"),name=f"±{vol_stress}% vol"))
    fig3.add_hline(y=0,line=dict(color=GREY,width=1.5))
    if be: fig3.add_vline(x=be,line=dict(color=RED,width=1.5,dash="dot"),
            annotation_text=f"Break-even P{be}",annotation_font=dict(color=RED,size=10))
    fig3.update_layout(height=400,xaxis_title="Percentile (1=meilleur, 100=pire)",
        yaxis_title="P&L annuel (EUR k)",
        legend=dict(orientation="h",yanchor="bottom",y=1.01,x=0),
        plot_bgcolor="#FAFAFA",paper_bgcolor="white",margin=dict(l=0,r=0,t=10,b=0),
        font=dict(family="Arial",size=11))
    st.plotly_chart(fig3,use_container_width=True)
    if be: st.info(f"**Break-even à P{be}** — perte si cannibalisation > P{be} historique.")

with cp3:
    st.markdown('<div class="section-title">📋 Table percentiles (WPD format)</div>',unsafe_allow_html=True)
    kp=[5,10,15,20,25,30,35,40,45,50,55,60,65,70,74,75,80,85,90,95,100]
    trows=[]
    for p in kp:
        sdn=float(np.percentile(nat_ref["shape_disc"].dropna(),p))
        sda=(float(np.percentile(asset_ann["shape_disc"].dropna(),p)) if has_asset else None)
        cpa=fwd_price*(1-sda) if sda else None
        pnla=vol_mwh*(cpa-ppa)/1000 if cpa else None
        row={"Pct":f"P{p}","Nat disc":f"{sdn*100:.1f}%","Nat CP":f"{(1-sdn)*100:.0f}%"}
        if has_asset:
            row["Asset disc"]=f"{sda*100:.1f}%"; row["Asset CP"]=f"{(1-sda)*100:.0f}%"
            row["P&L €k"]=f"{pnla:+.0f}k"
        trows.append(row)
    tdf=pd.DataFrame(trows)
    def hi(row):
        p=int(row["Pct"][1:])
        if p==chosen_pct: return [f"background-color:{GREEN};color:white;font-weight:bold"]*len(row)
        if p in [10,50,90]: return ["background-color:#EBF4FB;font-weight:600"]*len(row)
        if p==74: return ["background-color:#FFF3CD"]*len(row)
        return [""]*len(row)
    st.dataframe(tdf.style.apply(hi,axis=1),use_container_width=True,height=420)

st.markdown("---")

# ── Row 3: Scenarios ──────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🎯 Scénarios — P&L cumulé sur la durée du PPA</div>',unsafe_allow_html=True)
sd_med=float(np.percentile(hist_sd_f,50)) if len(hist_sd_f) else 0.15
scens=[
    ("Base",1.00,0.00,0.00),
    (f"Cannib +{vol_stress}%",1.00,+vol_stress/100,0.00),
    (f"Cannib −{vol_stress}%",1.00,-vol_stress/100,0.00),
    (f"Spot +{spot_stress}%",1+spot_stress/100,0.00,0.00),
    (f"Spot −{spot_stress}%",1-spot_stress/100,0.00,0.00),
    (f"Vol +{vol_stress}%",1.00,0.00,+vol_stress/100),
    (f"Vol −{vol_stress}%",1.00,0.00,-vol_stress/100),
    ("Stress total",1-spot_stress/100,+vol_stress/100,-vol_stress/100),
    ("Bull total",1+spot_stress/100,-vol_stress/100,+vol_stress/100),
]
sn,sv50,sv10,sv90=[],[],[],[]
for name,sm,da,va in scens:
    p50t=vol_mwh*(1+va)*(sm*fwd_price*(1-(sd_med+da))-ppa)/1000*proj_yrs
    sdp10=float(np.percentile(hist_sd_f,10))+da if len(hist_sd_f) else 0.1
    sdp90=float(np.percentile(hist_sd_f,90))+da if len(hist_sd_f) else 0.3
    p10t=vol_mwh*(1+va)*(sm*fwd_price*(1-sdp90)-ppa)/1000*proj_yrs
    p90t=vol_mwh*(1+va)*(sm*fwd_price*(1-sdp10)-ppa)/1000*proj_yrs
    sn.append(name); sv50.append(p50t); sv10.append(p10t); sv90.append(p90t)
fig4=go.Figure()
fig4.add_trace(go.Bar(name="P50",x=sn,y=sv50,
    marker_color=["rgba(26,107,58,0.75)" if v>=0 else "rgba(192,0,0,0.75)" for v in sv50],
    text=[f"{v:+.0f}k" for v in sv50],textposition="outside",textfont=dict(size=9)))
fig4.add_trace(go.Scatter(name="P10 (bear)",x=sn,y=sv10,mode="markers",
    marker=dict(symbol="triangle-down",size=10,color=RED)))
fig4.add_trace(go.Scatter(name="P90 (bull)",x=sn,y=sv90,mode="markers",
    marker=dict(symbol="triangle-up",size=10,color=GREEN)))
fig4.add_hline(y=0,line=dict(color=GREY,width=1.5))
fig4.update_layout(height=360,xaxis_title="Scénario",
    yaxis_title=f"P&L cumulé {proj_yrs} ans (EUR k)",
    legend=dict(orientation="h",yanchor="bottom",y=1.01,x=0),
    plot_bgcolor="#FAFAFA",paper_bgcolor="white",margin=dict(l=0,r=0,t=10,b=0),
    font=dict(family="Arial",size=11),bargap=0.3)
st.plotly_chart(fig4,use_container_width=True)

# ── Hourly profile ────────────────────────────────────────────────────────────
if has_asset and asset_raw is not None:
    st.markdown("---")
    st.markdown('<div class="section-title">🕐 Profil horaire — Production vs Spot</div>',unsafe_allow_html=True)
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
            marker_color="rgba(46,117,182,0.55)"),secondary_y=False)
        fig5.add_trace(go.Scatter(x=hp["Hour"],y=hp["Spot"],name="Spot moy. (EUR/MWh)",
            mode="lines+markers",line=dict(color="#1F3864",width=2.5),marker=dict(size=6)),secondary_y=True)
        fig5.update_xaxes(tickvals=list(range(0,24,2)),ticktext=[f"{h:02d}h" for h in range(0,24,2)])
        fig5.update_yaxes(title_text="Production (MWh/h)",secondary_y=False)
        fig5.update_yaxes(title_text="Spot moyen (EUR/MWh)",secondary_y=True)
        fig5.update_layout(height=300,plot_bgcolor="#FAFAFA",paper_bgcolor="white",
            margin=dict(l=0,r=0,t=10,b=0),legend=dict(orientation="h",y=1.05),
            font=dict(family="Arial",size=11))
        st.plotly_chart(fig5,use_container_width=True)
        st.caption("🔍 Heures solaires (10h–16h) = spot le plus bas → mécanisme de cannibalisation.")
    except Exception:
        pass

st.markdown("---")
st.caption(f"ENTSO-E France {data_start.year}–{data_end.strftime('%Y-%m-%d')} "
           f"• {len(hourly):,} heures • Mise à jour auto quotidienne (GitHub Actions) "
           f"• Logique WPD Tender format")
