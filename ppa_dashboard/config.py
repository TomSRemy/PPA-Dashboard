"""
config.py — KAL-EL PPA Dashboard
Constants: paths, tech config, chart defaults, CSS injection.
Colors: imported from theme.py — do NOT add color values here.
"""

from pathlib import Path

# ── Re-export theme so existing imports (from config import C1...) still work ─
from theme import (
    C1, C2, C3, C4, C5, BG, WHT, C2L, C3L, C4L, C5L,
    C_WIND, C_WIND_L, COL_AFRR, COL_MFRR, CHART_PALETTE,
    TEXT_DARK, TEXT_MUTED, TEXT_FAINT, ACCENT_PRIMARY, ACCENT_WARN, ACCENT_NEG,
    BG_PAGE, BG_WHITE, BG_LIGHT, BG_WARN, BORDER_LIGHT, GRID_LINE,
    REF_LINE, REF_LINE_L, REF_LINE_LL, COL_SOLAR, COL_SOLAR_L, COL_WIND, COL_WIND_L,
    CHART_H_XS, CHART_H_SM, CHART_H_MD, CHART_H_LG, CHART_H_XL, CHART_H_TBL,
    rgba, with_alpha, transparent, band_colors, pos_neg_colors,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"

# ── Technology config ─────────────────────────────────────────────────────────
TECH_CONFIG = {
    "Solar": {
        "prod_col":   "NatMW",
        "color":      COL_SOLAR,
        "color_l":    COL_SOLAR_L,
        "nat_cp":     "cp_nat_pct",
        "nat_eur":    "cp_nat",
        "nat_sd":     "shape_disc",
        "label":      "Solar",
        "psr_codes":  ["B16"],
        "badge_cls":  "tech-badge-solar",
        "duck_months": [4, 5, 6, 7, 8, 9],
    },
    "Wind": {
        "prod_col":   "WindMW",
        "color":      COL_WIND,
        "color_l":    COL_WIND_L,
        "nat_cp":     "cp_wind_pct",
        "nat_eur":    "cp_wind",
        "nat_sd":     "shape_disc_wind",
        "label":      "Wind",
        "psr_codes":  ["B19", "B18"],
        "badge_cls":  "tech-badge-wind",
        "duck_months": list(range(1, 13)),
    },
}

# ── Chart constants ───────────────────────────────────────────────────────────
MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

DEFAULT_FWD = {2026: 55.0, 2027: 54.0, 2028: 53.0, 2029: 52.0, 2030: 51.0}

EXAMPLE_CSV = (
    "Date,Prod_MWh\n"
    "2024-01-01 00:00:00,0.0\n"
    "2024-01-01 06:00:00,0.5\n"
    "2024-01-01 12:00:00,6.2\n"
    "2024-01-01 18:00:00,0.2\n"
)

# ── CSS (injected once in app.py) ─────────────────────────────────────────────
def get_css():
    return f"""<style>
html, body, [class*="css"] {{
    font-family: Calibri, 'Segoe UI', Arial, sans-serif !important;
    font-size: 15px !important;
    background-color: {BG_PAGE} !important;
}}
h1 {{ font-size: 24px !important; font-weight: 700 !important; color: {C4} !important; font-family: Calibri, Arial, sans-serif !important; }}
h2 {{ font-size: 18px !important; font-weight: 700 !important; color: {C4} !important; }}
h3 {{ font-size: 16px !important; font-weight: 700 !important; color: {C4} !important; }}
p, li, label, .stMarkdown, td, th {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; color: {C4} !important; }}
.section-title {{
    font-size: 13px !important; font-weight: 700; color: {WHT};
    background: linear-gradient(90deg, {ACCENT_PRIMARY}, {ACCENT_PRIMARY});
    padding: 8px 14px; border-radius: 4px; margin: 24px 0 10px 0;
    letter-spacing: 0.06em; text-transform: uppercase; display: block;
    border-left: 4px solid {ACCENT_WARN};
}}
.chart-desc {{
    font-size: 13px !important; color: {TEXT_DARK} !important;
    background: {BG_WARN}; border-left: 4px solid {ACCENT_WARN};
    padding: 10px 14px; border-radius: 0 6px 6px 0;
    margin: 0 0 16px 0; line-height: 1.6; font-family: Calibri, Arial, sans-serif;
}}
.ppa-card {{
    background: linear-gradient(90deg, {TEXT_DARK}, {TEXT_DARK}); color: {WHT};
    padding: 20px 22px; border-radius: 10px; text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}}
.ppa-card .val {{ font-size: 32px; font-weight: 700; color: {WHT} !important; font-family: Calibri, Arial, sans-serif; }}
.ppa-card .lbl {{ font-size: 11px; color: {WHT} !important; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.06em; }}
.kpi-card {{
    background: {BG_WHITE}; border-left: 5px solid {ACCENT_PRIMARY}; padding: 14px 18px; border-radius: 6px;
    border: 1px solid {BORDER_LIGHT}; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
.kpi-val {{ font-size: 24px; font-weight: 700; color: {TEXT_DARK}; font-family: Calibri, Arial, sans-serif; }}
.kpi-lbl {{ font-size: 11px; color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-red  {{ border-left-color: {ACCENT_NEG} !important; }}
.kpi-gold {{ border-left-color: {ACCENT_WARN} !important; }}
.tech-badge-solar {{
    display: inline-block; background: {COL_SOLAR}; color: {WHT};
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    letter-spacing: 0.05em; margin-left: 8px; font-family: Calibri, Arial, sans-serif;
}}
.tech-badge-wind {{
    display: inline-block; background: {COL_WIND}; color: {WHT};
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    letter-spacing: 0.05em; margin-left: 8px; font-family: Calibri, Arial, sans-serif;
}}
.update-pill {{
    background: {TEXT_DARK} !important; border: 1px solid {ACCENT_WARN} !important; border-radius: 20px !important;
    padding: 5px 16px !important; font-size: 12px !important; color: {ACCENT_WARN} !important;
    display: inline-block !important; font-family: Calibri, Arial, sans-serif !important; font-weight: 600 !important;
}}
.ytd-badge {{
    font-size: 10px; font-weight: 700; color: {TEXT_DARK}; background: {ACCENT_WARN};
    padding: 2px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}}
.status-msg {{
    background: linear-gradient(90deg, {BG_LIGHT}, {BG_LIGHT}); border: 1px solid {ACCENT_PRIMARY};
    border-radius: 8px; padding: 12px 18px; color: {TEXT_DARK} !important; font-weight: 500; margin: 10px 0;
}}
.wind-msg {{
    background: linear-gradient(90deg, {COL_WIND_L}, {COL_WIND_L}); border: 1px solid {COL_WIND};
    border-radius: 8px; padding: 12px 18px; color: {TEXT_DARK} !important; font-weight: 500; margin: 10px 0;
}}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {TEXT_DARK}, {TEXT_DARK}CC) !important; }}
[data-testid="stSidebar"] * {{ color: {WHT} !important; font-family: Calibri, Arial, sans-serif !important; }}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] p {{ color: #D0E4ED !important; font-size: 13px !important; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    color: {WHT} !important; font-size: 15px !important;
    border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 6px;
}}
[data-baseweb="slider"] [role="slider"] {{
    background-color: {ACCENT_WARN} !important; border: 2px solid {WHT} !important;
    box-shadow: none !important; border-radius: 50% !important;
    width: 14px !important; height: 14px !important;
}}
[data-baseweb="slider"] [role="slider"]:hover {{ box-shadow: none !important; transform: none !important; }}
.stTabs [data-baseweb="tab"] {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; font-weight: 600; padding: 10px 20px !important; }}
.stTabs [data-baseweb="tab"]:not([aria-selected="true"]) p {{ color: rgba(247,220,111,0.7) !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ border-bottom: 3px solid {ACCENT_WARN} !important; background: {BG_WARN} !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] p {{ color: {ACCENT_PRIMARY} !important; font-weight: 700 !important; font-size: 15.5px !important; }}
div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {{
    font-family: Calibri, Arial, sans-serif !important; font-size: 13px !important; color: {TEXT_DARK} !important;
}}
.stButton > button {{
    background: linear-gradient(90deg, {ACCENT_PRIMARY}, {ACCENT_PRIMARY}) !important; color: {WHT} !important;
    border: none !important; border-radius: 6px !important;
    font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important;
    font-weight: 600 !important; padding: 10px 24px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important; transition: all 0.2s ease !important;
}}
.stButton > button:hover {{ background: linear-gradient(90deg, {ACCENT_PRIMARY}, {ACCENT_PRIMARY}) !important; transform: translateY(-1px) !important; }}
.stDownloadButton > button {{ background: linear-gradient(90deg, {ACCENT_WARN}, {ACCENT_WARN}) !important; color: {TEXT_DARK} !important; border: none !important; font-weight: 700 !important; }}
.stAlert {{ background-color: {BG_WARN} !important; border: 1px solid {ACCENT_WARN} !important; border-radius: 6px !important; }}
.stAlert > div {{ color: {TEXT_DARK} !important; }}
[data-testid="stFileUploaderDropzone"] span {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] svg  {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] {{
    display: flex !important; flex-direction: column !important;
    align-items: center !important; justify-content: center !important;
    min-height: 60px !important;
    background: linear-gradient(90deg, {ACCENT_PRIMARY}, {ACCENT_PRIMARY}) !important;
    border: none !important; border-radius: 8px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
    cursor: pointer !important; transition: all 0.2s ease !important;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    box-shadow: 0 6px 16px rgba(0,0,0,0.25) !important; transform: translateY(-1px) !important;
}}
[data-testid="stFileUploaderDropzone"]::before {{
    content: "Upload";
    font-family: Calibri, Arial, sans-serif; font-size: 14px;
    color: {WHT}; font-weight: 700; letter-spacing: 0.05em;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p:empty {{ display: none !important; }}
</style>"""
