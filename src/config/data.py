"""Measurement log, CSV export, temperature chart and bath-limit display settings."""

from __future__ import annotations

# Maximum recorded rows kept in memory, comfortably above EXPORT_MAX_ROWS.
LOG_MAX_ROWS = 200_000

# CSV export: rows offered by default in the download dialog, and the most it accepts.
EXPORT_DEFAULT_ROWS = 50
EXPORT_MAX_ROWS = 100_000

# Rolling time window (s) shown on the chart's X axis.
CHART_WINDOW_S = 300

# Default Y-axis bounds (°C) of the temperature chart.
CHART_TEMP_MIN_C = 0
CHART_TEMP_MAX_C = 100

# Bath temperature (°C) at which the PLC turns the heater off, and the reading it must drop below before
# the heater may come back on. They mirror FW config::kMaxBathTempC / kBathTempClearC: keep them in sync.
BATH_TEMP_LIMIT_C = 65.0
BATH_TEMP_CLEAR_C = 60.0
