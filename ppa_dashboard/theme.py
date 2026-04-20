"""
theme.py — KAL-EL PPA Dashboard
================================
Single source of truth for ALL colors, opacities, and semantic color helpers.
To retheme the dashboard: edit ONLY this file.

PALETTE SECTIONS
  1. Core palette       — raw hex values
  2. Semantic aliases   — named by role, not by hue
  3. Tech colors        — per-technology accent colors
  4. Neutral scale      — grids, borders, muted text
  5. Chart palette      — multi-series categorical colors
  6. Helper functions   — rgba(), with_alpha(), darken()
"""

# ── 1. CORE PALETTE ───────────────────────────────────────────────────────────
# Edit these to retheme everything at once.

NAVY       = "#1D3A4A"   # primary dark — text, axis labels
TEAL       = "#2A9D8F"   # solar accent — positive, primary action
GOLD       = "#FFD700"   # warnings, highlight bands, tabs
GOLD_L     = "#F7DC6F"   # light gold — headings in dark bg
BRICK      = "#E76F51"   # negative, losses, risk
BLUE       = "#5B8DEF"   # wind accent
PAGE_BG    = "#F7F4F0"   # page background (warm off-white)
WHITE      = "#FFFFFF"

# Light variants (backgrounds, fills)
TEAL_L     = "#D4EDEA"
GOLD_LL    = "#FFF8DC"   # very light gold for desc boxes
GOLD_LM    = "#FFFACD"   # medium light gold
BRICK_L    = "#FAEAE6"
BLUE_L     = "#D6E6FC"

# ── 2. SEMANTIC ALIASES ───────────────────────────────────────────────────────
# Use these throughout the app — never the raw names above.

TEXT_DARK      = NAVY        # primary text, axis labels, chart font
TEXT_MUTED     = "#555555"   # secondary labels, sub-headers
TEXT_FAINT     = "#888888"   # source notes, metadata
ACCENT_PRIMARY = TEAL        # main CTA, solar, positive
ACCENT_WARN    = GOLD        # warnings, stress bands
ACCENT_NEG     = BRICK       # losses, negative P&L
BG_PAGE        = PAGE_BG
BG_WHITE       = WHITE
BG_LIGHT       = TEAL_L      # status message backgrounds
BG_WARN        = GOLD_LL     # desc box background
BORDER_LIGHT   = "#E0E0E0"
BORDER_FAINT   = "#EEEEEE"
BORDER_MED     = "#CCCCCC"
BORDER_GRID    = "#EEEEEE"   # plotly gridlines
GRID_LINE      = "#EEEEEE"   # alias for use in layout dicts
REF_LINE       = "#AAAAAA"   # horizontal/vertical reference lines (y=0, y=1)
REF_LINE_L     = "#BBBBBB"   # lighter reference lines
REF_LINE_LL    = "#CCCCCC"   # faintest reference lines

# ── 3. TECH COLORS ────────────────────────────────────────────────────────────

COL_SOLAR      = TEAL
COL_SOLAR_L    = TEAL_L
COL_WIND       = BLUE
COL_WIND_L     = BLUE_L

# Reserve services (used in FPC / balancing charts)
COL_AFRR       = "#9B59B6"   # purple
COL_MFRR       = "#E67E22"   # orange

# ── 4. NEUTRAL SCALE ──────────────────────────────────────────────────────────
# Used for axis styling, borders, muted elements.

NEUTRAL_50     = "#FAFAFA"
NEUTRAL_100    = "#F5F5F5"
NEUTRAL_200    = "#EEEEEE"
NEUTRAL_300    = "#DDDDDD"
NEUTRAL_400    = "#CCCCCC"
NEUTRAL_500    = "#AAAAAA"
NEUTRAL_600    = "#888888"
NEUTRAL_700    = "#555555"
NEUTRAL_800    = "#333333"

# ── 5. CHART PALETTE — categorical multi-series ───────────────────────────────
# Used in generation-mix charts, cross-border flows, etc.

CHART_PALETTE  = [
    "#8ECAE6",   # sky blue
    "#219EBC",   # ocean blue
    "#023047",   # dark blue
    "#FFB703",   # amber
    "#FB8500",   # orange
    "#6A994E",   # green
    TEAL,
    BRICK,
    BLUE,
    GOLD,
]

# ── 6. HELPER FUNCTIONS ───────────────────────────────────────────────────────

def rgba(hex_c: str, alpha: float) -> str:
    """Convert hex color + alpha to rgba string.
    
    Usage: rgba(COL_SOLAR, 0.3) → 'rgba(42,157,143,0.3)'
    """
    h = hex_c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def with_alpha(hex_c: str, alpha: float) -> str:
    """Alias for rgba() — more readable in chart code."""
    return rgba(hex_c, alpha)


def transparent() -> str:
    """Fully transparent — used for invisible fill boundaries."""
    return "rgba(0,0,0,0)"


def band_colors(color: str) -> dict:
    """Return P10-P90 / P25-P75 band fill colors for a given accent color.
    
    Usage:
        bands = band_colors(COL_SOLAR)
        fillcolor=bands["outer"]   # P10-P90
        fillcolor=bands["inner"]   # P25-P75
    """
    return {
        "outer": rgba(color, 0.10),
        "inner": rgba(color, 0.22),
    }


def pos_neg_colors(values: list, pos_color: str = ACCENT_PRIMARY,
                   neg_color: str = ACCENT_NEG, alpha: float = 0.80) -> list:
    """Return a list of colors — pos_color for >=0, neg_color for <0.
    
    Usage: marker_color=pos_neg_colors(my_values)
    """
    return [rgba(pos_color, alpha) if v >= 0 else rgba(neg_color, alpha)
            for v in values]


# ── 7. CHART SIZES ───────────────────────────────────────────────────────────
# Edit these to resize ALL charts at once.
# Current sizes are ~20% larger than original defaults.

CHART_H_XS  = 300    # tiny — inline sparklines, small KPI charts
CHART_H_SM  = 380    # small — compact single-metric charts
CHART_H_MD  = 480    # medium — standard chart (was 380-420)
CHART_H_LG  = 580    # large — dual-axis, subplots, feature charts (was 450-520)
CHART_H_XL  = 720    # extra large — heatmaps, historical subplots (was 520-640)
CHART_H_TBL = 300    # stats table panels (narrow column, fixed)

# ── 8. BACKWARD COMPATIBILITY ─────────────────────────────────────────────────
# config.py still re-exports these for files not yet migrated.
# Do NOT use these in new code — use semantic aliases above.

C1    = TEXT_DARK
C2    = ACCENT_PRIMARY
C3    = ACCENT_WARN
C4    = GOLD_L
C5    = ACCENT_NEG
BG    = BG_PAGE
WHT   = WHITE
C2L   = TEAL_L
C3L   = GOLD_LL
C4L   = GOLD_LM
C5L   = BRICK_L
C_WIND   = COL_WIND
C_WIND_L = COL_WIND_L
