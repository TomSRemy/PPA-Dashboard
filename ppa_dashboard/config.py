"""
config.py — KAL-EL PPA Dashboard
Palette, technology config, shared constants.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"

# ── Palette ───────────────────────────────────────────────────────────────────
C1  = "#1D3A4A"   # dark navy
C2  = "#2A9D8F"   # teal         — solar accent
C3  = "#FFD700"   # gold         — warnings, bands
C4  = "#F7DC6F"   # light gold
C5  = "#E76F51"   # brick red    — losses, negative
BG  = "#F7F4F0"   # page bg
WHT = "#FFFFFF"

C2L = "#D4EDEA"   # teal light
C3L = "#FFF8DC"   # gold light
C4L = "#FFFACD"
C5L = "#FAEAE6"

C_WIND  = "#5B8DEF"   # blue  — wind accent
C_WIND_L= "#D6E6FC"

# ── Technology config ─────────────────────────────────────────────────────────
# All per-technology variables resolved from here — no more if/else chains.
TECH_CONFIG = {
    "Solar": {
        "prod_col":   "NatMW",
        "color":      C2,
        "color_l":    C2L,
        "nat_cp":     "cp_nat_pct",
        "nat_eur":    "cp_nat",
        "nat_sd":     "shape_disc",
        "label":      "Solar",
        "psr_codes":  ["B16"],
        "badge_cls":  "tech-badge-solar",
        # Duck/canyon months: solar production season
        "duck_months": [4, 5, 6, 7, 8, 9],
    },
    "Wind": {
        "prod_col":   "WindMW",
        "color":      C_WIND,
        "color_l":    C_WIND_L,
        "nat_cp":     "cp_wind_pct",
        "nat_eur":    "cp_wind",
        "nat_sd":     "shape_disc_wind",
        "label":      "Wind",
        "psr_codes":  ["B19", "B18"],   # onshore + offshore
        "badge_cls":  "tech-badge-wind",
        # Wind: all months (no seasonal restriction)
        "duck_months": list(range(1, 13)),
    },
}

# ── Chart constants ───────────────────────────────────────────────────────────
MONTH_NAMES   = ["Jan","Feb","Mar","Apr","May","Jun",
                 "Jul","Aug","Sep","Oct","Nov","Dec"]

DEFAULT_FWD   = {2026: 55.0, 2027: 54.0, 2028: 53.0, 2029: 52.0, 2030: 51.0}

# ── CSS (injected once in app.py) ─────────────────────────────────────────────
def get_css():
    return f"""<style>
html, body, [class*="css"] {{
    font-family: Calibri, 'Segoe UI', Arial, sans-serif !important;
    font-size: 15px !important;
    background-color: {BG} !important;
}}
h1 {{ font-size: 24px !important; font-weight: 700 !important; color: {C4} !important; font-family: Calibri, Arial, sans-serif !important; }}
h2 {{ font-size: 18px !important; font-weight: 700 !important; color: {C4} !important; }}
h3 {{ font-size: 16px !important; font-weight: 700 !important; color: {C4} !important; }}
p, li, label, .stMarkdown, td, th {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; color: {C4} !important; }}
.section-title {{
    font-size: 13px !important; font-weight: 700; color: {WHT};
    background: linear-gradient(90deg, {C2}, {C2});
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
    background: linear-gradient(90deg, {C1}, {C1}); color: {WHT};
    padding: 20px 22px; border-radius: 10px; text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}}
.ppa-card .val {{ font-size: 32px; font-weight: 700; color: {WHT} !important; font-family: Calibri, Arial, sans-serif; }}
.ppa-card .lbl {{ font-size: 11px; color: {WHT} !important; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.06em; }}
.kpi-card {{
    background: {WHT}; border-left: 5px solid {C2}; padding: 14px 18px; border-radius: 6px;
    border: 1px solid #E0E0E0; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
.kpi-val {{ font-size: 24px; font-weight: 700; color: {C1}; font-family: Calibri, Arial, sans-serif; }}
.kpi-lbl {{ font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 0.05em; }}
.kpi-red  {{ border-left-color: {C5} !important; }}
.kpi-gold {{ border-left-color: {C3} !important; }}
.tech-badge-solar {{
    display: inline-block; background: {C2}; color: {WHT};
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    letter-spacing: 0.05em; margin-left: 8px; font-family: Calibri, Arial, sans-serif;
}}
.tech-badge-wind {{
    display: inline-block; background: {C_WIND}; color: {WHT};
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    letter-spacing: 0.05em; margin-left: 8px; font-family: Calibri, Arial, sans-serif;
}}
.update-pill {{
    background: {C1} !important; border: 1px solid {C3} !important; border-radius: 20px !important;
    padding: 5px 16px !important; font-size: 12px !important; color: {C3} !important;
    display: inline-block !important; font-family: Calibri, Arial, sans-serif !important; font-weight: 600 !important;
}}
.ytd-badge {{
    font-size: 10px; font-weight: 700; color: {C1}; background: {C3};
    padding: 2px 6px; border-radius: 3px; margin-left: 6px; vertical-align: middle;
}}
.status-msg {{
    background: linear-gradient(90deg, {C2L}, {C2L}); border: 1px solid {C2};
    border-radius: 8px; padding: 12px 18px; color: {C1} !important; font-weight: 500; margin: 10px 0;
}}
.wind-msg {{
    background: linear-gradient(90deg, {C_WIND_L}, {C_WIND_L}); border: 1px solid {C_WIND};
    border-radius: 8px; padding: 12px 18px; color: {C1} !important; font-weight: 500; margin: 10px 0;
}}
[data-testid="stSidebar"] {{ background: linear-gradient(1890deg, {C1}, {C1}CC) !important; }}
[data-testid="stSidebar"] * {{ color: {WHT} !important; font-family: Calibri, Arial, sans-serif !important; }}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] p {{ color: #D0E4ED !important; font-size: 13px !important; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    color: {WHT} !important; font-size: 15px !important;
    border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 6px;
}}
[data-baseweb="slider"] [role="slider"] {{
    background-color: {C3} !important; border: 2px solid {WHT} !important;
    box-shadow: none !important; border-radius: 50% !important;
    width: 14px !important; height: 14px !important;
}}
[data-baseweb="slider"] [role="slider"]:hover {{ box-shadow: none !important; transform: none !important; }}
.stTabs [data-baseweb="tab"] {{ font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important; font-weight: 600; padding: 10px 20px !important; }}
.stTabs [data-baseweb="tab"]:not([aria-selected="true"]) p {{ color: rgba(247,220,111,0.7) !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ border-bottom: 3px solid {C3} !important; background: {C3L} !important; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] p {{ color: {C2} !important; font-weight: 700 !important; font-size: 15.5px !important; }}
div[data-testid="stDataFrame"] td, div[data-testid="stDataFrame"] th {{
    font-family: Calibri, Arial, sans-serif !important; font-size: 13px !important; color: {C1} !important;
}}
.stButton > button {{
    background: linear-gradient(90deg, {C2}, {C2}) !important; color: {WHT} !important;
    border: none !important; border-radius: 6px !important;
    font-family: Calibri, Arial, sans-serif !important; font-size: 14px !important;
    font-weight: 600 !important; padding: 10px 24px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important; transition: all 0.2s ease !important;
}}
.stButton > button:hover {{ background: linear-gradient(90deg, {C2}, {C2}) !important; transform: translateY(-1px) !important; }}
.stDownloadButton > button {{ background: linear-gradient(90deg, {C3}, {C3}) !important; color: {C1} !important; border: none !important; font-weight: 700 !important; }}
.stAlert {{ background-color: {C3L} !important; border: 1px solid {C3} !important; border-radius: 6px !important; }}
.stAlert > div {{ color: {C1} !important; }}
[data-testid="stFileUploaderDropzone"] span {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] svg  {{ display: none !important; }}
[data-testid="stFileUploaderDropzone"] {{
    display: flex !important; flex-direction: column !important;
    align-items: center !important; justify-content: center !important;
    min-height: 60px !important;
    background: linear-gradient(90deg, {C2}, {C2}) !important;
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
