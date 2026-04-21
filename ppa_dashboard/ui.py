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


def kpi_card(label: str, value: str, color: str = None, extra_cls: str = "",
             delta: str = None, delta_color: str = None):
    c = color or _DEFAULT["SOLAR_ACC"]
    d_color = delta_color or c
    delta_html = f'<div class="kpi-delta" style="color:{d_color}">{delta}</div>' if delta else ""
    st.markdown(
        f'<div class="kpi-card {extra_cls}" style="border-left-color:{c}">'
        f'<div class="kpi-lbl" style="color:{c}">{label}</div>'
        f'<div class="kpi-val">{value}</div>'
        f'{delta_html}'
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
    pal    = p or _DEFAULT
    text   = pal.get("TEXT_PRIMARY", pal.get("TEXT_DARK", "#001219"))
    bg_w   = pal.get("SURFACE",      pal.get("BG_WHITE",  "#FFFFFF"))
    bg_p   = pal.get("PAGE_BG",      pal.get("BG_PAGE",   "#E9D8A6"))
    grid   = pal.get("GRID",         pal.get("GRID_LINE", "#E9D8A6"))
    border = pal.get("BORDER",       pal.get("BORDER_MED","#94D2BD"))

    legend_cfg = dict(
        orientation="h", yanchor="top",
        y=-0.15 if legend_below else 1.02,
        xanchor="center", x=0.5,
        font=dict(size=12, color=text, family="Calibri, Arial"),
        bgcolor=bg_w,
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
