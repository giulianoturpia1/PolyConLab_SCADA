"""Polling cadence and reply timing between the SCADA and the PLC."""

from __future__ import annotations

# Sensor read cadence (ms): one full round of MEAS queries per interval. Also sets the
# time step between chart samples.
SENSOR_POLL_INTERVAL_MS = 1_000

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
