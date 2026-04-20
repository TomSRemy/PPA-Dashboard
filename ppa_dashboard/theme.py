"""
theme.py — KAL-EL PPA Dashboard
================================
Single source of truth for ALL colors, sizes, and helpers.
Supports light and dark mode via set_mode(dark=True/False).

TO RETHEME: edit CORE PALETTE section only.
TO RESIZE ALL CHARTS: edit CHART SIZES section only.
"""

# ── CORE PALETTE ──────────────────────────────────────────────────────────────
_TEAL    = "#2A9D8F"
_TEAL_D  = "#3DBFB0"
_GOLD    = "#E6B800"
_GOLD_RAW= "#FFD700"
_BRICK   = "#E76F51"
_BRICK_D = "#F08060"
_BLUE    = "#3A7BD5"
_BLUE_D  = "#5B9EEF"

COL_AFRR = "#9B59B6"
COL_MFRR = "#E67E22"

CHART_PALETTE = [
    "#8ECAE6","#219EBC","#023047",
    "#FFB703","#FB8500","#6A994E",
    _TEAL, _BRICK, _BLUE, _GOLD_RAW,
]

# ── CHART SIZES ───────────────────────────────────────────────────────────────
CHART_H_XS  = 300
CHART_H_SM  = 380
CHART_H_MD  = 480
CHART_H_LG  = 580
CHART_H_XL  = 720
CHART_H_TBL = 300

# ── PALETTES ──────────────────────────────────────────────────────────────────
_LIGHT = dict(
    BG_PAGE="#F7F4F0", BG_WHITE="#FFFFFF", BG_LIGHT="#C8EDE9", BG_WARN="#FFF3B0",
    TEXT_DARK="#1D3A4A", TEXT_MUTED="#4A6070", TEXT_FAINT="#7A8F9A",
    TEAL=_TEAL, GOLD=_GOLD, GOLD_RAW=_GOLD_RAW, BRICK=_BRICK, BLUE=_BLUE,
    TEAL_L="#D4EDEA", GOLD_LL="#FFF8DC", GOLD_LM="#FFFACD", BRICK_L="#FAEAE6", BLUE_L="#D6E6FC",
    BORDER_LIGHT="#E0E0E0", BORDER_FAINT="#EEEEEE", BORDER_MED="#CCCCCC",
    GRID_LINE="#EEEEEE", REF_LINE="#AAAAAA", REF_LINE_L="#BBBBBB", REF_LINE_LL="#CCCCCC",
    SECTION_BG=_TEAL, SECTION_TEXT="#E8F0F5", SECTION_BORDER=_GOLD_RAW,
)

_DARK = dict(
    BG_PAGE="#0F1E28", BG_WHITE="#1A2E3D", BG_LIGHT="#0D3530", BG_WARN="#1E1A00",
    TEXT_DARK="#E8F0F5", TEXT_MUTED="#9DB5C5", TEXT_FAINT="#6A8A9A",
    TEAL=_TEAL_D, GOLD=_GOLD_RAW, GOLD_RAW=_GOLD_RAW, BRICK=_BRICK_D, BLUE=_BLUE_D,
    TEAL_L="#0D3530", GOLD_LL="#1E1A00", GOLD_LM="#1A1700", BRICK_L="#2A1510", BLUE_L="#0D1E35",
    BORDER_LIGHT="#2A4055", BORDER_FAINT="#1E3448", BORDER_MED="#2A4055",
    GRID_LINE="#1E3448", REF_LINE="#3A5570", REF_LINE_L="#2A4A60", REF_LINE_LL="#1E3A50",
    SECTION_BG="#1A3545", SECTION_TEXT="#E8F0F5", SECTION_BORDER=_GOLD_RAW,
)


def get_palette(dark: bool = False) -> dict:
    return _DARK.copy() if dark else _LIGHT.copy()


# ── ACTIVE VARS — updated by set_mode() ───────────────────────────────────────
_p = _LIGHT

TEXT_DARK = TEXT_MUTED = TEXT_FAINT = ""
ACCENT_PRIMARY = ACCENT_WARN = ACCENT_NEG = ""
BG_PAGE = BG_WHITE = BG_LIGHT = BG_WARN = ""
BORDER_LIGHT = BORDER_FAINT = BORDER_MED = GRID_LINE = ""
REF_LINE = REF_LINE_L = REF_LINE_LL = ""
COL_SOLAR = COL_SOLAR_L = COL_WIND = COL_WIND_L = ""
SECTION_BG = SECTION_TEXT = SECTION_BORDER = ""
C1 = C2 = C3 = C4 = C5 = BG = WHT = ""
C2L = C3L = C4L = C5L = C_WIND = C_WIND_L = ""


def set_mode(dark: bool = False):
    """Call once in app.py after reading the sidebar toggle."""
    global _p, \
        TEXT_DARK, TEXT_MUTED, TEXT_FAINT, \
        ACCENT_PRIMARY, ACCENT_WARN, ACCENT_NEG, \
        BG_PAGE, BG_WHITE, BG_LIGHT, BG_WARN, \
        BORDER_LIGHT, BORDER_FAINT, BORDER_MED, GRID_LINE, \
        REF_LINE, REF_LINE_L, REF_LINE_LL, \
        COL_SOLAR, COL_SOLAR_L, COL_WIND, COL_WIND_L, \
        SECTION_BG, SECTION_TEXT, SECTION_BORDER, \
        C1, C2, C3, C4, C5, BG, WHT, C2L, C3L, C4L, C5L, C_WIND, C_WIND_L

    _p = _DARK if dark else _LIGHT

    TEXT_DARK      = _p["TEXT_DARK"]
    TEXT_MUTED     = _p["TEXT_MUTED"]
    TEXT_FAINT     = _p["TEXT_FAINT"]
    ACCENT_PRIMARY = _p["TEAL"]
    ACCENT_WARN    = _p["GOLD"]
    ACCENT_NEG     = _p["BRICK"]
    BG_PAGE        = _p["BG_PAGE"]
    BG_WHITE       = _p["BG_WHITE"]
    BG_LIGHT       = _p["BG_LIGHT"]
    BG_WARN        = _p["BG_WARN"]
    BORDER_LIGHT   = _p["BORDER_LIGHT"]
    BORDER_FAINT   = _p["BORDER_FAINT"]
    BORDER_MED     = _p["BORDER_MED"]
    GRID_LINE      = _p["GRID_LINE"]
    REF_LINE       = _p["REF_LINE"]
    REF_LINE_L     = _p["REF_LINE_L"]
    REF_LINE_LL    = _p["REF_LINE_LL"]
    COL_SOLAR      = _p["TEAL"]
    COL_SOLAR_L    = _p["TEAL_L"]
    COL_WIND       = _p["BLUE"]
    COL_WIND_L     = _p["BLUE_L"]
    SECTION_BG     = _p["SECTION_BG"]
    SECTION_TEXT   = _p["SECTION_TEXT"]
    SECTION_BORDER = _p["SECTION_BORDER"]
    C1   = TEXT_DARK
    C2   = ACCENT_PRIMARY
    C3   = _p["GOLD_RAW"]
    C4   = _p["GOLD_LM"]
    C5   = ACCENT_NEG
    BG   = BG_PAGE
    WHT  = BG_WHITE
    C2L  = _p["TEAL_L"]
    C3L  = _p["GOLD_LL"]
    C4L  = _p["GOLD_LM"]
    C5L  = _p["BRICK_L"]
    C_WIND   = COL_WIND
    C_WIND_L = COL_WIND_L


# Initialise light mode
set_mode(dark=False)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def rgba(hex_c: str, alpha: float) -> str:
    h = hex_c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def with_alpha(hex_c: str, alpha: float) -> str:
    return rgba(hex_c, alpha)

def transparent() -> str:
    return "rgba(0,0,0,0)"

def band_colors(color: str) -> dict:
    return {"outer": rgba(color, 0.10), "inner": rgba(color, 0.22)}

def pos_neg_colors(values: list, pos_color: str = None,
                   neg_color: str = None, alpha: float = 0.80) -> list:
    pos = pos_color or ACCENT_PRIMARY
    neg = neg_color or ACCENT_NEG
    return [rgba(pos, alpha) if v >= 0 else rgba(neg, alpha) for v in values]
