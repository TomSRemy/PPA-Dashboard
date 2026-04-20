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
    SECTION_BG, SECTION_TEXT, SECTION_BORDER,
    CHART_H_XS, CHART_H_SM, CHART_H_MD, CHART_H_LG, CHART_H_XL, CHART_H_TBL,
    rgba, with_alpha, transparent, band_colors, pos_neg_colors, set_mode, get_palette,
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
def get_css(p: dict = None):
    if p is None:
        from theme import get_palette
        p = get_palette(dark=False)
    # Sidebar always uses Ink Black regardless of mode
    SIDEBAR = "#001219"
    SIDEBAR_TEXT = "#E9D8A6"
    SIDEBAR_ACCENT = "#94D2BD"
    return f"""<style>
html, body, [class*="css"] {{
    font-family: Calibri, 'Segoe UI', Arial, sans-serif !important;
    font-size: 15px !important;
    background-color: {p["PAGE_BG"]} !important;
}}
h1 {{ font-size: 24px !important; font-weight: 700 !important; color: {p["WARN_ACC"]} !important; font-family: Calibri, Arial, sans-serif !important; }}
h2 {{ font-size: 18px !important; font-weight: 700 !important; color: {p["TEXT_PRIMARY"]} !important; }}
h3 {{ font-size: 16px !important; font-weight: 700 !important; color: {p["TEXT_PRIMARY"]} !important; }}
p, li, label, .stMarkdown, td, th {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; color: {p["TEXT_PRIMARY"]} !important; }}
.section-title {{
    font-size: 13px !important; font-weight: 700; color: {p["SECTION_TEXT"]};
    background: {p["SECTION_BG"]};
    padding: 8px 14px; border-radius: 4px; margin: 24px 0 10px 0;
    letter-spacing: 0.06em; text-transform: uppercase; display: block;
    border-left: 4px solid {p["SECTION_BORDER"]};
}}
.chart-desc {{
    font-size: 13px !important; color: {p["TEXT_PRIMARY"]} !important;
    background: {p["WARN_FILL"]}; border-left: 4px solid {p["WARN_ACC"]};
    padding: 10px 14px; border-radius: 0 6px 6px 0;
    margin: 0 0 16px 0; line-height: 1.6; font-family: Calibri, Arial, sans-serif;
}}
.ppa-card {{
    background: {p["SECTION_BG"]}; color: {p["SECTION_TEXT"]};
    padding: 20px 22px; border-radius: 10px; text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}}
.ppa-card .val {{ font-size: 32px; font-weight: 700; color: {p["SECTION_TEXT"]} !important; font-family: Calibri, Arial, sans-serif; }}
.ppa-card .lbl {{ font-size: 11px; color: {p["SECTION_TEXT"]} !important; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.06em; }}
.kpi-card {{
    background: {p["SURFACE"]}; border-left: 5px solid {p["SOLAR_ACC"]}; padding: 14px 18px; border-radius: 6px;
    border: 1px solid {p["BORDER"]}; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
.kpi-val {{ font-size: 24px; font-weight: 700; color: {p["TEXT_PRIMARY"]}; font-family: Calibri, Arial, sans-serif; }}
.kpi-lbl {{ font-size: 11px; color: {p["TEXT_SECONDARY"]}; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-red  {{ border-left-color: {p["NEG_ACC"]} !important; }}
.kpi-gold {{ border-left-color: {p["WARN_ACC"]} !important; }}
.tech-badge-solar {{
    display: inline-block; background: {p["SOLAR_ACC"]}; color: {p["SURFACE"]};
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    letter-spacing: 0.05em; margin-left: 8px; font-family: Calibri, Arial, sans-serif;
}}
.tech-badge-wind {{
    display: inline-block; background: {p["WIND_ACC"]}; color: {p["SURFACE"]};
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    letter-spacing: 0.05em; margin-left: 8px; font-family: Calibri, Arial, sans-serif;
}}
.update-pill {{
    background: {p["SECTION_BG"]} !important; border: 1px solid {p["WARN_ACC"]} !important; border-radius: 20px !important;
    padding: 5px 16px !important; font-size: 12px !important; color: {p["WARN_ACC"]} !important;
    display: inline-block !important; font-family: Calibri, Arial, sans-serif !important; font-weight: 600 !important;
}}
.ytd-badge {{
    font-size: 10px; font-weight: 700; color: {p["SECTION_BG"]}; background: {p["WARN_ACC"]};
    padding: 2px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}}
.status-msg {{
    background: {p["SOLAR_FILL"]}; border: 1px solid {p["SOLAR_ACC"]};
    border-radius: 8px; padding: 12px 18px; color: {p["TEXT_PRIMARY"]} !important; font-weight: 500; margin: 10px 0;
}}
.wind-msg {{
    background: {p["WIND_FILL"]}; border: 1px solid {p["WIND_ACC"]};
    border-radius: 8px; padding: 12px 18px; color: {p["TEXT_PRIMARY"]} !important; font-weight: 500; margin: 10px 0;
}}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {SIDEBAR}, {SIDEBAR}EE) !important; }}
[data-testid="stSidebar"] * {{ color: {SIDEBAR_TEXT} !important; font-family: Calibri, Arial, sans-serif !important; }}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] p {{ color: {SIDEBAR_ACCENT} !important; font-size: 13px !important; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    color: {SIDEBAR_TEXT} !important; font-size: 15px !important;
    border-bottom: 1px solid rgba(148,210,189,0.3); padding-bottom: 6px;
}}
[data-baseweb="slider"] [role="slider"] {{
    background-color: {p["WARN_ACC"]} !important; border: 2px solid {p["SURFACE"]} !important;
    box-shadow: none !important; border-radius: 50% !important;
    width: 14px !important; height: 14px !important;
}}
.stTabs [data-baseweb="tab"] {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; font-weight: 600; padding: 10px 20px !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ border-bottom: 3px solid {p["WARN_ACC"]} !important; background: {p["WARN_FILL"]} !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] p {{ color: {p["SOLAR_ACC"]} !important; font-weight: 700 !important; font-size: 15.5px !important; }}
div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {{
    font-family: Calibri, Arial, sans-serif !important; font-size: 13px !important; color: {p["TEXT_PRIMARY"]} !important;
}}
.stButton > button {{
    background: {p["SOLAR_ACC"]} !important; color: {p["SURFACE"]} !important;
    border: none !important; border-radius: 6px !important;
    font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important;
    font-weight: 600 !important; padding: 10px 24px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
}}
.stDownloadButton > button {{ background: {p["WARN_ACC"]} !important; color: {p["SECTION_BG"]} !important; border: none !important; font-weight: 700 !important; }}
.stAlert {{ background-color: {p["WARN_FILL"]} !important; border: 1px solid {p["WARN_ACC"]} !important; border-radius: 6px !important; }}
.stAlert > div {{ color: {p["TEXT_PRIMARY"]} !important; }}
[data-testid="stFileUploaderDropzone"] {{
    display: flex !important; align-items: center !important; justify-content: center !important;
    min-height: 60px !important;
    background: {p["SOLAR_ACC"]} !important;
    border: none !important; border-radius: 8px !important;
    cursor: pointer !important;
}}
[data-testid="stFileUploaderDropzone"] span {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] svg  {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"]::before {{
    content: "Upload";
    font-family: Calibri, Arial, sans-serif; font-size: 14px;
    color: {p["SURFACE"]}; font-weight: 700; letter-spacing: 0.05em;
}}
</style>"""
