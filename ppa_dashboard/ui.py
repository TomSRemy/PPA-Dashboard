"""
ui.py — KAL-EL PPA Dashboard
Reusable UI components: section headers, description boxes, KPI cards, plotly base.
v2: plotly_base now returns fig so it can be used as st.plotly_chart(plotly_base(fig,...))
"""
import streamlit as st
import plotly.graph_objects as go
from config import C1, C2, C3, C4, C5, BG, WHT, C2L, C3L


def section(text: str):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def desc(text: str):
    st.markdown(f'<div class="chart-desc">{text}</div>', unsafe_allow_html=True)


def status_msg(text: str, kind: str = "default"):
    cls = "wind-msg" if kind == "wind" else "status-msg"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def ppa_card(label: str, value: str, unit: str = "EUR / MWh"):
    st.markdown(
        f'<div class="ppa-card">'
        f'<div class="lbl">{label}</div>'
        f'<div class="val">{value}</div>'
        f'<div class="lbl">{unit}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def kpi_card(label: str, value: str, color: str = C2, extra_cls: str = ""):
    st.markdown(
        f'<div class="kpi-card {extra_cls}" style="border-left-color:{color}">'
        f'<div class="kpi-lbl">{label}</div>'
        f'<div class="kpi-val" style="color:{color}">{value}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def tech_badge(tech_label: str) -> str:
    cls = "tech-badge-solar" if tech_label == "Solar" else "tech-badge-wind"
    return f'<span class="{cls}">{tech_label.upper()}</span>'


def plotly_base(fig: go.Figure, h: int = 400,
                show_legend: bool = True, legend_below: bool = True) -> go.Figure:
    """
    Apply standard KAL-EL styling to a Plotly figure.
    Returns fig so it can be used as:
        st.plotly_chart(plotly_base(fig, h=400))
    or:
        plotly_base(fig, h=400)
        st.plotly_chart(fig)
    """
    legend_cfg = dict(
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
        legend=legend_cfg,
        title=dict(
            font=dict(size=16, color=C1, family="Calibri, Arial"),
            x=0.5, xanchor="center", y=0.98, yanchor="top"
        )
    )
    axis_style = dict(
        showgrid=True, gridcolor="#EEEEEE", gridwidth=1,
        linecolor="#CCCCCC", linewidth=1,
        tickfont=dict(family="Calibri, Arial", size=12, color=C1),
        title_font=dict(family="Calibri, Arial", size=13, color=C1)
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig  # ← FIX: was missing


def rgba(hex_c: str, alpha: float) -> str:
    r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"
