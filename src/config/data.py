"""Measurement log, CSV export, temperature chart and fallback temperature-limit settings."""

from __future__ import annotations

from models import TempLimits

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

# Temperature limits used until the PLC reports its own with TEMP:LIM?, and when it does not (older
# firmware). They match FW config::kTempSetpointMinC/MaxC, kMaxBathTempC and kBathTempClearC.
DEFAULT_TEMP_LIMITS = TempLimits(setpoint_min=0.0, setpoint_max=65.0, bath_limit=65.0, bath_clear=60.0)
