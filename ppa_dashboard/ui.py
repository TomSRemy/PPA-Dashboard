"""
ui.py — KAL-EL PPA Dashboard
Reusable UI components. Colors come from palette dict, not module-level vars.
"""
import streamlit as st
import plotly.graph_objects as go

from theme import get_palette

_DEFAULT = get_palette(dark=False)


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


def kpi_card(label: str, value: str, color: str = None, extra_cls: str = ""):
    c = color or _DEFAULT["TEAL"]
    st.markdown(
        f'<div class="kpi-card {extra_cls}" style="border-left-color:{c}">'
        f'<div class="kpi-lbl">{label}</div>'
        f'<div class="kpi-val" style="color:{c}">{value}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def tech_badge(tech_label: str) -> str:
    cls = "tech-badge-solar" if tech_label == "Solar" else "tech-badge-wind"
    return f'<span class="{cls}">{tech_label.upper()}</span>'


def plotly_base(fig: go.Figure, h: int = 480,
                show_legend: bool = True, legend_below: bool = True,
                p: dict = None) -> go.Figure:
    """
    Apply KAL-EL styling to a Plotly figure.
    Pass p=palette_dict for correct dark/light colors.
    Falls back to light palette if p not provided.
    """
    pal = p or _DEFAULT
    text   = pal["TEXT_DARK"]
    bg_w   = pal["BG_WHITE"]
    bg_p   = pal["BG_PAGE"]
    grid   = pal["GRID_LINE"]
    border = pal["BORDER_MED"]

    legend_cfg = dict(
        orientation="h", yanchor="top",
        y=-0.15 if legend_below else 1.02,
        xanchor="center", x=0.5,
        font=dict(size=12, color=text, family="Calibri, Arial"),
        bgcolor="rgba(255,255,255,0.9)" if pal == _DEFAULT else "rgba(26,46,61,0.9)",
        bordercolor=border, borderwidth=1,
    ) if show_legend else dict(visible=False)

    fig.update_layout(
        height=h, plot_bgcolor=bg_w, paper_bgcolor=bg_p,
        margin=dict(l=60, r=40, t=50, b=100 if legend_below else 40),
        font=dict(family="Calibri, Arial, sans-serif", size=14, color=text),
        legend=legend_cfg,
        title=dict(
            font=dict(size=16, color=text, family="Calibri, Arial"),
            x=0.5, xanchor="center", y=0.98, yanchor="top"
        )
    )
    axis_style = dict(
        showgrid=True, gridcolor=grid, gridwidth=1,
        linecolor=border, linewidth=1,
        tickfont=dict(family="Calibri, Arial", size=12, color=text),
        title_font=dict(family="Calibri, Arial", size=13, color=text)
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig
