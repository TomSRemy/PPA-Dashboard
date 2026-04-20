"""
ui.py — KAL-EL PPA Dashboard
Reusable UI components: section headers, description boxes, KPI cards, plotly base.
Colors imported from theme.py — no hex values here.
"""
import streamlit as st
import plotly.graph_objects as go

from theme import (
    TEXT_DARK, TEXT_MUTED, ACCENT_PRIMARY, BG_WHITE, BG_PAGE,
    BORDER_FAINT, BORDER_MED, GRID_LINE, REF_LINE,
    C1, C2, C3, WHT,
)


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


def kpi_card(label: str, value: str, color: str = ACCENT_PRIMARY, extra_cls: str = ""):
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
    Returns fig — use as: st.plotly_chart(plotly_base(fig, h=400))
    """
    legend_cfg = dict(
        orientation="h", yanchor="top",
        y=-0.15 if legend_below else 1.02,
        xanchor="center", x=0.5,
        font=dict(size=12, color=TEXT_DARK, family="Calibri, Arial"),
        bgcolor="rgba(255,255,255,0.9)", bordercolor=BORDER_MED, borderwidth=1,
    ) if show_legend else dict(visible=False)

    fig.update_layout(
        height=h, plot_bgcolor=BG_WHITE, paper_bgcolor=BG_PAGE,
        margin=dict(l=60, r=40, t=50, b=100 if legend_below else 40),
        font=dict(family="Calibri, Arial, sans-serif", size=14, color=TEXT_DARK),
        legend=legend_cfg,
        title=dict(
            font=dict(size=16, color=TEXT_DARK, family="Calibri, Arial"),
            x=0.5, xanchor="center", y=0.98, yanchor="top"
        )
    )
    axis_style = dict(
        showgrid=True, gridcolor=GRID_LINE, gridwidth=1,
        linecolor=BORDER_MED, linewidth=1,
        tickfont=dict(family="Calibri, Arial", size=12, color=TEXT_DARK),
        title_font=dict(family="Calibri, Arial", size=13, color=TEXT_DARK)
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig
