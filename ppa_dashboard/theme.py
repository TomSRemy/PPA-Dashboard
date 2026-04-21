"""
theme.py — KAL-EL PPA Dashboard
================================
Single source of truth for ALL colors, sizes, and helpers.

HOW TO RETHEME — edit ONLY the 2 palette dicts below.
Names are ROLES, not colors. Never use color names as keys.

LIGHT PALETTE roles:
  PAGE_BG       — main page background
  SURFACE       — cards, chart backgrounds
  SIDEBAR_BG    — sidebar background
  TEXT_PRIMARY  — main readable text
  TEXT_SECONDARY— muted labels, captions
  TEXT_FAINT    — metadata, footnotes
  SOLAR_ACC     — solar tech accent / positive / CTA
  SOLAR_FILL    — solar light fill (badges, bands)
  WIND_ACC      — wind tech accent
  WIND_FILL     — wind light fill
  WARN_ACC      — warnings, bands, tab highlight
  WARN_FILL     — warning background fill
  NEG_ACC       — losses, negative P&L
  NEG_FILL      — negative background fill
  BORDER        — card borders, separators
  GRID          — plotly gridlines
  REF           — y=0, y=1 reference lines
  SECTION_BG    — section title background
  SECTION_TEXT  — section title text
  SECTION_BORDER— section title left border

TO RESIZE ALL CHARTS: edit CHART SIZES section.
"""

# ══════════════════════════════════════════════════════════════════════════════
# LIGHT PALETTE
# ══════════════════════════════════════════════════════════════════════════════
_LIGHT = dict(
    PAGE_BG        = "#FFFFFF",   # Wheat — warm parchment background
    SURFACE        = "#FFFFFF",   # White — cards, chart bg
    SIDEBAR_BG     = "#001219",   # Ink Black — deep sidebar
    TEXT_PRIMARY   = "#001219",   # Ink Black — max contrast on light
    TEXT_SECONDARY = "#005F73",   # Dark Teal — secondary labels
    TEXT_FAINT     = "#0A9396",   # Dark Cyan — hints, metadata
    SOLAR_ACC      = "#0A9396",   # Dark Cyan — solar, positive, CTA
    SOLAR_FILL     = "#94D2BD",   # Pearl Aqua — solar light fill
    WIND_ACC       = "#005F73",   # Dark Teal — wind accent
    WIND_FILL      = "#94D2BD",   # Pearl Aqua — wind light fill
    WARN_ACC       = "#EE9B00",   # Golden Orange — warnings, tabs (replaces yellow)
    WARN_FILL      = "#E9D8A6",   # Wheat — warning background
    NEG_ACC        = "#BB3E03",   # Rusty Spice — losses, negative
    NEG_FILL       = "#AE2012",   # Oxidized Iron (dark fill variant)
    BORDER         = "#94D2BD",   # Pearl Aqua — subtle border
    CARD_BORDER_COLOR = "#D0D0D0",  # card outer border — neutral grey
    GRID           = "#E8E8E8",   # Ink Black — max contrast on light
    REF            = "#C0C0C0",   # Burnt Caramel — reference lines
    SECTION_BG     = "#005F73",   # Dark Teal — section header bg
    SECTION_TEXT   = "#E9D8A6",   # Wheat — section header text
    SECTION_BORDER = "#EE9B00",   # Golden Orange — section left border
)

# ══════════════════════════════════════════════════════════════════════════════
# DARK PALETTE
# ══════════════════════════════════════════════════════════════════════════════
_DARK = dict(
    PAGE_BG        = "#FFFFFF",   # Ink Black — deep dark background
    SURFACE        = "#005F73",   # Dark Teal — elevated surface
    SIDEBAR_BG     = "#001219",   # Ink Black — same as page in dark
    TEXT_PRIMARY   = "#E9D8A6",   # Wheat — warm readable on dark
    TEXT_SECONDARY = "#94D2BD",   # Pearl Aqua — muted on dark
    TEXT_FAINT     = "#0A9396",   # Dark Cyan — faint on dark
    SOLAR_ACC      = "#94D2BD",   # Pearl Aqua — solar on dark bg
    SOLAR_FILL     = "#0A9396",   # Dark Cyan — solar fill on dark
    WIND_ACC       = "#94D2BD",   # Pearl Aqua — wind on dark
    WIND_FILL      = "#005F73",   # Dark Teal — wind fill on dark
    WARN_ACC       = "#EE9B00",   # Golden Orange — same, always visible
    WARN_FILL      = "#CA6702",   # Burnt Caramel — warn fill on dark
    NEG_ACC        = "#BB3E03",   # Rusty Spice — same on dark
    NEG_FILL       = "#001219",   # Ink Black fill variant
    BORDER         = "#0A9396",   # Dark Cyan — border on dark
    CARD_BORDER_COLOR = "#2A4055",  # card outer border — dark mode
    GRID           = "#005F73",   # Dark Teal — gridlines on dark
    REF            = "#94D2BD",   # Pearl Aqua — ref lines on dark
    SECTION_BG     = "#005F73",   # Dark Teal — same section bg
    SECTION_TEXT   = "#E9D8A6",   # Wheat — same section text
    SECTION_BORDER = "#EE9B00",   # Golden Orange — same border
)

# ══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPAT KEYS — added to both palettes
# ══════════════════════════════════════════════════════════════════════════════
def _add_compat(p: dict, dark: bool) -> dict:
    """Add legacy key aliases so existing code doesn't break."""
    p["ACCENT_PRIMARY"] = p["SOLAR_ACC"]
    p["ACCENT_WARN"]    = p["WARN_ACC"]
    p["ACCENT_NEG"]     = p["NEG_ACC"]
    p["BG_PAGE"]        = p["PAGE_BG"]
    p["BG_WHITE"]       = p["SURFACE"]
    p["BG_LIGHT"]       = p["SOLAR_FILL"]
    p["BG_WARN"]        = p["WARN_FILL"]
    p["TEXT_DARK"]      = p["TEXT_PRIMARY"]
    p["TEXT_MUTED"]     = p["TEXT_SECONDARY"]
    p["BORDER_LIGHT"]   = p["BORDER"]
    p["CARD_BORDER_COLOR"] = p["CARD_BORDER_COLOR"]
    p["BORDER_FAINT"]   = p["GRID"]
    p["BORDER_MED"]     = p["BORDER"]
    p["GRID_LINE"]      = p["GRID"]
    p["REF_LINE"]       = p["REF"]
    p["REF_LINE_L"]     = p["REF"]
    p["REF_LINE_LL"]    = p["REF"]
    p["COL_SOLAR"]      = p["SOLAR_ACC"]
    p["COL_SOLAR_L"]    = p["SOLAR_FILL"]
    p["COL_WIND"]       = p["WIND_ACC"]
    p["COL_WIND_L"]     = p["WIND_FILL"]
    p["C1"]  = p["TEXT_PRIMARY"]
    p["C2"]  = p["SOLAR_ACC"]
    p["C3"]  = p["WARN_ACC"]
    p["C4"]  = p["WARN_FILL"]
    p["C5"]  = p["NEG_ACC"]
    p["BG"]  = p["PAGE_BG"]
    p["WHT"] = p["SURFACE"]
    p["C2L"] = p["SOLAR_FILL"]
    p["C3L"] = p["WARN_FILL"]
    p["C4L"] = p["WARN_FILL"]
    p["C5L"] = p["NEG_FILL"]
    p["C_WIND"]   = p["WIND_ACC"]
    p["C_WIND_L"] = p["WIND_FILL"]
    return p


def get_palette(dark: bool = False) -> dict:
    """Return full color palette for light or dark mode."""
    base = _DARK.copy() if dark else _LIGHT.copy()
    return _add_compat(base, dark)


# ══════════════════════════════════════════════════════════════════════════════
# CARD SIZES — edit to resize ALL cards at once
# ══════════════════════════════════════════════════════════════════════════════
CARD_BORDER_OUTER  = "2px"       # outline border thickness
CARD_BORDER_ACCENT = "7px"       # left accent border thickness
CARD_RADIUS        = "8px"       # corner radius
CARD_PADDING       = "16px 18px" # internal padding
CARD_SHADOW        = "none"      # box shadow — set to e.g. "0 2px 8px rgba(0,0,0,0.08)" to re-enable

# ══════════════════════════════════════════════════════════════════════════════
# CHART SIZES — edit to resize ALL charts at once
# ══════════════════════════════════════════════════════════════════════════════
CHART_H_XS  = 300
CHART_H_SM  = 380
CHART_H_MD  = 480
CHART_H_LG  = 580
CHART_H_XL  = 720
CHART_H_TBL = 300

# ══════════════════════════════════════════════════════════════════════════════
# CHART PALETTE — categorical, same in both modes
# ══════════════════════════════════════════════════════════════════════════════
COL_AFRR      = "#9B59B6"
COL_MFRR      = "#E67E22"
CHART_PALETTE = [
    "#94D2BD",  # Pearl Aqua
    "#0A9396",  # Dark Cyan
    "#005F73",  # Dark Teal
    "#EE9B00",  # Golden Orange
    "#CA6702",  # Burnt Caramel
    "#BB3E03",  # Rusty Spice
    "#AE2012",  # Oxidized Iron
    "#9B2226",  # Brown Red
    "#94D2BD",
    "#E9D8A6",
]

# ══════════════════════════════════════════════════════════════════════════════
# MODULE-LEVEL VARS — set by set_mode(), used by legacy imports
# ══════════════════════════════════════════════════════════════════════════════
_p = get_palette(dark=False)

def set_mode(dark: bool = False):
    global _p
    _p = get_palette(dark=dark)

# Expose flat vars (legacy — prefer get_palette())
def __getattr__(name):
    if name in _p:
        return _p[name]
    raise AttributeError(f"module 'theme' has no attribute {name!r}")



def kpi_color(asset_val, national_val=None, margin: float = 0.02,
              higher_is_better: bool = True) -> str:
    """
    Returns border color for a KPI card based on asset vs national comparison.

    - asset_val > national_val + margin  → SOLAR_ACC (green)
    - within margin                       → WARN_ACC  (orange)
    - asset_val < national_val - margin  → NEG_ACC   (red)

    If national_val is None, falls back to zero comparison.
    higher_is_better=False inverts the logic (e.g. shape discount: lower is better).
    """
    if asset_val is None:
        return _p["SOLAR_ACC"]
    ref = national_val if national_val is not None else 0.0
    diff = (asset_val - ref) if higher_is_better else (ref - asset_val)
    if diff > margin:
        return _p["SOLAR_ACC"]
    if diff > -margin:
        return _p["WARN_ACC"]
    return _p["NEG_ACC"]

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
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
    pos = pos_color or _p["SOLAR_ACC"]
    neg = neg_color or _p["NEG_ACC"]
    return [rgba(pos, alpha) if v >= 0 else rgba(neg, alpha) for v in values]
