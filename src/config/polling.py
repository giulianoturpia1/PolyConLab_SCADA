"""Polling cadence and reply timing between the SCADA and the PLC."""

from __future__ import annotations

# Default sensor sampling period (ms): one full round of MEAS queries per period. The operator
# changes it at runtime from Configuración, within the bounds below.
SENSOR_POLL_INTERVAL_MS = 2_000

# Bounds and step of the sampling-period field in the settings dialog. The floor keeps every
# round inside what the PLC link sustains with margin (see recommended_min_period_ms).
SAMPLE_PERIOD_MIN_MS = 500
SAMPLE_PERIOD_MAX_MS = 10_000
SAMPLE_PERIOD_STEP_MS = 50

# Commands the SCADA lets wait for a reply at once. Mirrors the firmware's
# config::kMaxInFlightCommands: a command sent while that many are unanswered is refused with
# -106 BUSY, so further commands are held here until a reply frees a slot. Keep in sync.
MAX_IN_FLIGHT_COMMANDS = 8

# Firmware task periods the recommended minimum period is derived from: config::kAppTaskPeriodMs
# and config::kStateMachineTaskPeriodMs. A whole round goes out as one batch, so its worst case is
# one round trip: up to one App tick to read the query and one SM tick to dispatch it, then one SM
# tick to collect the reply and one App tick to write it. Keep in sync.
FW_APP_TICK_MS = 20
FW_SM_TICK_MS = 50

# Margin over that worst-case round trip: the STATE? poll, actuator queries and Wi-Fi latency
# share the same link and firmware ticks.
SAMPLE_PERIOD_HEADROOM = 2.0

# FSM state label refresh cadence (ms): one STATE? query per interval.
STATE_POLL_INTERVAL_MS = 2_000

# How long (ms) a command may sit at the head of the reply queue before it is dropped. The
# firmware answers every command it accepts, so this only fires when a reply is lost on the
# wire; without it one lost reply would stall the correlator for the rest of the session.
PENDING_TTL_MS = 5_000

# How long (ms) the handshake waits after sending a transition event before re-querying
# STATE?, to let the PLC's FreeRTOS scheduler process the event and settle.
HANDSHAKE_SETTLE_MS = 400

# Overall timeout (ms) for the handshake's sensor probe step. Each sensor query takes at most
# one SM tick (~50 ms) plus network latency; 6 sensors x ~100 ms each gives ~600 ms nominal,
# so 6 s is a generous upper bound.
HANDSHAKE_PROBE_TIMEOUT_MS = 6_000

# Most recent reply latencies kept by the link statistics for the average / p95 / max.
LINK_STATS_WINDOW = 1_000
