"""
theme.py — KAL-EL PPA Dashboard (Ocean Sunset Theme)
====================================================
Single source of truth for colors, sizes, helpers.
Supports light/dark mode via set_mode().
"""

# ── CORE PALETTE (OCEAN SUNSET) ──────────────────────────────────────────────
_COLD_1 = "#001219"
_COLD_2 = "#005F73"
_COLD_3 = "#0A9396"
_COLD_4 = "#94D2BD"

_NEUTRAL = "#E9D8A6"

_WARM_1 = "#EE9B00"
_WARM_2 = "#CA6702"
_WARM_3 = "#BB3E03"

_HOT    = "#AE2012"
_CRIT   = "#9B2226"

# light variants (used by charts / gradients)
_COLD_2_L = "#0FB5C2"
_COLD_3_L = "#35D0B5"
_COLD_4_L = "#C8F2E3"

_WARM_1_L = "#FFD166"
_WARM_2_L = "#FF9F1C"
_WARM_3_L = "#E76F51"


# ── CHART SIZES ───────────────────────────────────────────────────────────────
CHART_H_XS  = 300
CHART_H_SM  = 380
CHART_H_MD  = 480
CHART_H_LG  = 580
CHART_H_XL  = 720
CHART_H_TBL = 300


# ── CHART PALETTE ─────────────────────────────────────────────────────────────
CHART_PALETTE = [
    _COLD_4, _COLD_3, _COLD_2,
    _NEUTRAL,
    _WARM_1, _WARM_2, _WARM_3,
    _HOT, _CRIT
]


# ── THEMES ────────────────────────────────────────────────────────────────────
_LIGHT = dict(
    BG_PAGE="#F7F4F0",
    BG_WHITE="#FFFFFF",
    BG_LIGHT="#C8EDE9",
    BG_WARN="#FFF3B0",

    TEXT_DARK="#1D3A4A",
    TEXT_MUTED="#4A6070",
    TEXT_FAINT="#7A8F9A",

    COLD_1=_COLD_1,
    COLD_2=_COLD_2,
    COLD_3=_COLD_3,
    COLD_4=_COLD_4,

    COLD_2_L=_COLD_2_L,
    COLD_3_L=_COLD_3_L,
    COLD_4_L=_COLD_4_L,

    NEUTRAL=_NEUTRAL,

    WARM_1=_WARM_1,
    WARM_2=_WARM_2,
    WARM_3=_WARM_3,

    HOT=_HOT,
    CRIT=_CRIT,
)

_DARK = dict(
    BG_PAGE="#0F1E28",
    BG_WHITE="#1A2E3D",
    BG_LIGHT="#0D3530",
    BG_WARN="#1E1A00",

    TEXT_DARK="#E8F0F5",
    TEXT_MUTED="#9DB5C5",
    TEXT_FAINT="#6A8A9A",

    COLD_1=_COLD_1,
    COLD_2="#00A6B4",
    COLD_3="#00C2A8",
    COLD_4="#7AE0C3",

    COLD_2_L="#5CE1E6",
    COLD_3_L="#6EF0D2",
    COLD_4_L="#BFF3E4",

    NEUTRAL="#C2B280",

    WARM_1="#FFB703",
    WARM_2="#FB8500",
    WARM_3="#D94F04",

    HOT="#FF2D55",
    CRIT="#B00020",
)


def get_palette(dark: bool = False) -> dict:
    return _DARK.copy() if dark else _LIGHT.copy()


# ── ACTIVE VARS ───────────────────────────────────────────────────────────────
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

    TEXT_DARK  = _p["TEXT_DARK"]
    TEXT_MUTED = _p["TEXT_MUTED"]
    TEXT_FAINT = _p["TEXT_FAINT"]

    ACCENT_PRIMARY = _p["COLD_3"]
    ACCENT_WARN    = _p["WARM_2"]
    ACCENT_NEG     = _p["HOT"]

    BG_PAGE  = _p["BG_PAGE"]
    BG_WHITE = _p["BG_WHITE"]
    BG_LIGHT = _p["BG_LIGHT"]
    BG_WARN  = _p["BG_WARN"]

    BORDER_LIGHT = _p.get("BORDER_LIGHT", "#E0E0E0")
    BORDER_FAINT = _p.get("BORDER_FAINT", "#EEEEEE")
    BORDER_MED   = _p.get("BORDER_MED", "#CCCCCC")

    GRID_LINE = _p.get("GRID_LINE", "#EEEEEE")

    REF_LINE    = _p.get("REF_LINE", "#AAAAAA")
    REF_LINE_L  = _p.get("REF_LINE_L", "#BBBBBB")
    REF_LINE_LL = _p.get("REF_LINE_LL", "#CCCCCC")

    COL_SOLAR   = _p["COLD_4"]
    COL_SOLAR_L = _p["COLD_4_L"]

    COL_WIND    = _p["COLD_2"]
    COL_WIND_L  = _p["COLD_2_L"]

    SECTION_BG     = _p.get("SECTION_BG", _COLD_2)
    SECTION_TEXT   = _p.get("SECTION_TEXT", "#E8F0F5")
    SECTION_BORDER = _p.get("SECTION_BORDER", _NEUTRAL)

    C1 = TEXT_DARK
    C2 = ACCENT_PRIMARY
    C3 = _p["NEUTRAL"]
    C4 = _p["WARM_1"]
    C5 = ACCENT_NEG
    BG = BG_PAGE
    WHT = BG_WHITE

    C2L = _p["COLD_3_L"]
    C3L = _p.get("NEUTRAL", _NEUTRAL)
    C4L = _p["WARM_2"]
    C5L = _p["WARM_3"]

    C_WIND   = COL_WIND
    C_WIND_L = COL_WIND_L


# initialise light mode
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
    return {
        "outer": rgba(color, 0.10),
        "inner": rgba(color, 0.22),
    }


def pos_neg_colors(values: list, pos_color: str = None,
                   neg_color: str = None, alpha: float = 0.80) -> list:
    pos = pos_color or ACCENT_PRIMARY
    neg = neg_color or ACCENT_NEG
    return [rgba(pos, alpha) if v >= 0 else rgba(neg, alpha) for v in values]
