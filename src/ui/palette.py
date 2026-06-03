"""
Color palette shared across all UI modules.
Import as:  from ui import palette as col
"""

from __future__ import annotations

# ── Base colours ─────────────────────────────────────────────────────────────
BG = "#1E2127"
PANEL = "#282C34"
BORDER = "#3D4452"
TEXT = "#ABB2BF"
WHITE = "#EFEFEF"
GREEN = "#56B870"
RED = "#E06C75"
ORANGE = "#E5C07B"
BLUE = "#61AFEF"
GRAY = "#5C6370"

# ── Derived / hover colours ───────────────────────────────────────────────────
# Slightly darker green — used as hover for active (ON) actuator buttons.
GREEN_HOVER = "#45A060"
# Slightly lighter panel — used as hover for inactive actuator buttons.
PANEL_HOVER = "#353A47"
# Slightly lighter gray — used as hover for active (OFF) actuator buttons.
GRAY_HOVER = "#6B7280"
# Amber — warm orange used for the SOFT ERROR firmware state.
AMBER = "#D19A66"

# ── State-label colours ───────────────────────────────────────────────────────
STATE_COLOR: dict[str, str] = {
    "STARTUP": BLUE,
    "CHECKUP": ORANGE,
    "MANUAL": GREEN,
    "PAUSE": ORANGE,
    "SOFT ERROR": AMBER,
    "HARD ERROR": RED,
    "SHUTDOWN": GRAY,
}
