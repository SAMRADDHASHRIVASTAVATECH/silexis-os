"""
Centralized style definitions for the GUI.
Dark theme with color-coded status indicators.
"""

# ── Color Palette ──────────────────────────────────────────────────────────
BG_DARK       = "#0d1117"
BG_PANEL      = "#161b22"
BG_PANEL_ALT  = "#1c2128"
BG_HEADER     = "#21262d"
BG_DROP       = "#0d1117"
BG_DROP_HOVER = "#1a2332"

BORDER        = "#30363d"
BORDER_ACCENT = "#388bfd"

TEXT_PRIMARY   = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED     = "#484f58"
TEXT_SUCCESS   = "#3fb950"
TEXT_WARNING   = "#d29922"
TEXT_ERROR     = "#f85149"
TEXT_INFO      = "#388bfd"
TEXT_ACCENT    = "#a5d6ff"

ACCENT_BLUE    = "#388bfd"
ACCENT_GREEN   = "#3fb950"
ACCENT_ORANGE  = "#d29922"
ACCENT_RED     = "#f85149"
ACCENT_PURPLE  = "#bc8cff"

# ── Stage Colors ──────────────────────────────────────────────────────────
STAGE_COLORS = {
    "WAITING":    "#484f58",
    "SCANNING":   "#d29922",
    "ANALYZING":  "#388bfd",
    "CONVERTING": "#e3b341",
    "STORING":    "#bc8cff",
    "ROUTING":    "#58a6ff",
    "EXPANDING":  "#c9a227",
    "ACTIVATING": "#f0883e",
    "ONLINE":     "#3fb950",
    "FAILED":     "#f85149",
}

# ── Severity Colors ───────────────────────────────────────────────────────
SEVERITY_COLORS = {
    "INFO":    TEXT_SECONDARY,
    "SUCCESS": TEXT_SUCCESS,
    "WARNING": TEXT_WARNING,
    "ERROR":   TEXT_ERROR,
}

# ── Font Definitions ──────────────────────────────────────────────────────
FONT_MONO   = ("Consolas", 9)
FONT_MONO_S = ("Consolas", 8)
FONT_MONO_L = ("Consolas", 10)
FONT_TITLE  = ("Segoe UI", 11, "bold")
FONT_HEADER = ("Segoe UI", 9, "bold")
FONT_BODY   = ("Segoe UI", 9)
FONT_SMALL  = ("Segoe UI", 8)

# ── Panel Padding ─────────────────────────────────────────────────────────
PAD = 6
PAD_S = 3
PAD_L = 10
