"""
Color palette shared across all UI modules.
Import as:  from ui.style import palette as col
"""

from __future__ import annotations

from comms.protocol import State

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
# Slightly lighter panel — hover for inactive actuator buttons and dialog buttons.
PANEL_HOVER = "#353A47"
# Darker than BG — a dialog button while pressed.
PRESSED = "#23272E"
# Darkest background — the log view and the command input of the log window.
CONSOLE_BG = "#151820"
# Dim gray-blue — log text, quieter than TEXT so the log reads as secondary.
CONSOLE_TEXT = "#7E8898"
# Slightly lighter gray — used as hover for active (OFF) actuator buttons.
GRAY_HOVER = "#6B7280"
# Amber — warm orange used for the SOFT ERROR firmware state.
AMBER = "#D19A66"

# ── Semantic control roles ────────────────────────────────────────────────────
# An ON / active control: the temp-control button and ON actuator rows.
ACTIVE = GREEN
ACTIVE_HOVER = GREEN_HOVER

# ── State-label colours ───────────────────────────────────────────────────────
STATE_COLOR: dict[str, str] = {
    State.STARTUP: BLUE,
    State.CHECKUP: ORANGE,
    State.MANUAL: GREEN,
    State.PAUSE: ORANGE,
    State.SOFT_ERROR: AMBER,
    State.HARD_ERROR: RED,
    State.SHUTDOWN: GRAY,
}
