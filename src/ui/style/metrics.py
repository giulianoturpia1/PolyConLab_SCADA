"""Named sizes, fonts and spacing used across the UI (pixels unless stated)."""

from __future__ import annotations

# ── Main window header ───────────────────────────────────────────────────────
LOGO_SIZE_PX = 36  # logo scaled to a square of this many pixels
CONN_FONT_PX = 13  # connection indicator label font size
CONN_MARGIN_LEFT_PX = 8  # connection indicator label left margin

# ── Actuator rows ────────────────────────────────────────────────────────────
ACTUATOR_BTN_WIDTH_PX = 72  # fixed width for ON / OFF buttons
ACTUATOR_LBL_MIN_WIDTH_PX = 88  # minimum width for the actuator name label

# ── Sensor cards ─────────────────────────────────────────────────────────────
SENSOR_CARD_MIN_W_PX = 100
SENSOR_CARD_MIN_H_PX = 88

# ── FSM state label ──────────────────────────────────────────────────────────
STATE_LABEL_FONT_PX = 18
STATE_LABEL_RADIUS_PX = 6
STATE_LABEL_PADDING = "14px 8px"

# ── Temperature control button ───────────────────────────────────────────────
TEMP_CONTROL_RADIUS_PX = 4

# ── Temperature chart ────────────────────────────────────────────────────────
CHART_X_TICK_COUNT = 6  # X-axis tick labels (one every 60 s over a 300 s window)
CHART_POINT_MARKER_PX = 6  # visible point-marker diameter drawn on each series

# ── Connection settings dialog ───────────────────────────────────────────────
SETTINGS_DIALOG_W_PX = 320
SETTINGS_DIALOG_H_PX = 148
