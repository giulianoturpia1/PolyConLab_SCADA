"""Named sizes, fonts and spacing used across the UI (pixels unless stated)."""

from __future__ import annotations

# ── Shared typography and control shapes ─────────────────────────────────────
FONT_UI = "'Segoe UI', Arial, sans-serif"  # base font family of the log window
FONT_MONO = "'Consolas', 'Courier New', monospace"  # log text and command input
DIALOG_FONT_PX = 13  # base font of the log window and the settings dialog
CONTROL_FONT_PX = 12  # buttons, inputs and actuator labels
SMALL_FONT_PX = 11  # log text and secondary labels
CONTROL_RADIUS_PX = 4  # corner rounding of inputs and buttons
BORDER_PX = 1  # standard outline width
THICK_BORDER_PX = 2  # emphasised outline (faulted sensor card, state label)
INPUT_PADDING = "4px 8px"  # inside line edits and spin boxes

# ── Main window header ───────────────────────────────────────────────────────
LOGO_SIZE_PX = 36  # logo scaled to a square of this many pixels
CONN_FONT_PX = 13  # connection indicator label font size
CONN_MARGIN_LEFT_PX = 8  # connection indicator label left margin

# ── Actuator rows ────────────────────────────────────────────────────────────
ACTUATOR_BTN_WIDTH_PX = 72  # fixed width for ON / OFF buttons
ACTUATOR_LBL_MIN_WIDTH_PX = 88  # minimum width for the actuator name label
ACTUATOR_BTN_PADDING = "4px 0"  # inside the ON / OFF buttons
ACTUATOR_ROW_MARGINS = (4, 2, 4, 2)  # left, top, right, bottom
ACTUATOR_ROW_SPACING_PX = 8

# ── Sensor cards ─────────────────────────────────────────────────────────────
SENSOR_CARD_MIN_W_PX = 100
SENSOR_CARD_MIN_H_PX = 88
SENSOR_CARD_MARGINS = (8, 6, 8, 6)  # left, top, right, bottom
SENSOR_CARD_SPACING_PX = 1  # between title, value and unit
SENSOR_CARD_RADIUS_PX = 8
SENSOR_TITLE_FONT_PX = 9
SENSOR_TITLE_LETTER_SPACING_PX = 1
SENSOR_VALUE_FONT_PX = 22
SENSOR_UNIT_FONT_PX = 10

# ── FSM state label ──────────────────────────────────────────────────────────
STATE_LABEL_FONT_PX = 18
STATE_LABEL_RADIUS_PX = 6
STATE_LABEL_PADDING = "14px 8px"

# ── Temperature control button ───────────────────────────────────────────────
TEMP_CONTROL_RADIUS_PX = 4

# ── Temperature chart ────────────────────────────────────────────────────────
CHART_X_TICK_COUNT = 6  # X-axis tick labels (one every 60 s over a 300 s window)
CHART_POINT_MARKER_PX = 6  # marker diameter, drawn only on a lone point (a line segment with one reading)
CHART_LINE_WIDTH_PX = 2  # width of each temperature line

# ── Connection settings dialog ───────────────────────────────────────────────
SETTINGS_DIALOG_W_PX = 320
SETTINGS_DIALOG_H_PX = 214
SETTINGS_HINT_FONT_PX = 11  # sampling-period hint under its field
SETTINGS_MARGINS = (16, 16, 16, 12)  # left, top, right, bottom
SETTINGS_SPACING_PX = 12  # between the form and the button box
SETTINGS_FORM_SPACING_PX = 8
SETTINGS_SPIN_BUTTON_W_PX = 16  # up/down arrows of the spin boxes
SETTINGS_BUTTON_PADDING = "6px 14px"

# ── Log window ───────────────────────────────────────────────────────────────
LOG_WINDOW_W_PX = 800
LOG_WINDOW_H_PX = 490
LOG_MARGIN_PX = 10
LOG_SPACING_PX = 6
LOG_CMD_LABEL_W_PX = 32
LOG_SEND_BTN_W_PX = 70
LOG_CLEAR_BTN_W_PX = 80
LOG_BUTTON_PADDING = "6px 12px"
