"""Wire protocol for the PolyConLab PLC: commands, events and responses.

Mirrors the firmware definitions in ``lib/Definitions/Definitions.hpp``
(kCommandMap, kEventMap, kResponseMap). Every command/event is a single ASCII
line terminated with ``\\n`` by the transport layer. Keep this module in sync
with the firmware definitions.

Strings are grouped into namespace classes used as plain attribute holders
(never instantiated): ``Cmd`` for commands/queries, ``Evt`` for state-machine
events, ``Resp`` for the canonical replies the PLC sends back.
"""

from __future__ import annotations

from dataclasses import dataclass

from models import Device, Sensor


class Cmd:
    """SCPI commands and queries sent to the PLC."""

    # Heater
    HEAT_ON = "OUTP:HEAT ON"
    HEAT_OFF = "OUTP:HEAT OFF"
    HEAT_STATE = "OUTP:HEAT?"

    # Pump
    PUMP_ON = "OUTP:PUMP ON"
    PUMP_OFF = "OUTP:PUMP OFF"
    PUMP_STATE = "OUTP:PUMP?"

    # Chiller
    CHILL_ON = "OUTP:CHILL ON"
    CHILL_OFF = "OUTP:CHILL OFF"
    CHILL_STATE = "OUTP:CHILL?"

    # Sensor reads
    TEMP_IN = "MEAS:TEMP:IN?"
    TEMP_OUT = "MEAS:TEMP:OUT?"
    TEMP_BATH = "MEAS:TEMP:CAM?"
    TEMP_MIX = "MEAS:TEMP:MEZ?"
    FLOW = "MEAS:FLOW?"
    LEVEL = "MEAS:LEVEL?"

    # Diagnostics / system
    PING = "PING"
    STATE = "STATE?"
    LOG_ON = "SYST:LOG ON"
    LOG_OFF = "SYST:LOG OFF"
    LOG_STATE = "SYST:LOG?"
    FAULT_QUERY = "SYST:FAULT?"  # Query which devices failed hardware initialisation

    # Sensor re-initialisation: re-run one sensor's hardware begin() on the PLC.
    REINIT_TEMP_IN = "SYST:REINIT:TEMP:IN"
    REINIT_TEMP_OUT = "SYST:REINIT:TEMP:OUT"
    REINIT_TEMP_BATH = "SYST:REINIT:TEMP:CAM"
    REINIT_TEMP_MIX = "SYST:REINIT:TEMP:MEZ"
    REINIT_FLOW = "SYST:REINIT:FLOW"
    REINIT_LEVEL = "SYST:REINIT:LEVEL"

    # Temperature control (manual inlet setpoint). The FW handles TEMP:SET:IN as a
    # LOCAL TOGGLE in ManualState and answers with the resulting control state
    # (ON / OFF), so the reply must be correlated like any other command.
    TEMP_SET_IN = "TEMP:SET:IN"

    # Valves are parameterized by number, appended after a comma
    # (e.g. "OUTP:VALV OPEN,1"). Firmware accepts valve numbers 1 and 2 only.
    @staticmethod
    def valve_open(n: int) -> str:
        """Command to open valve ``n``."""
        return f"OUTP:VALV OPEN,{n}"

    @staticmethod
    def valve_close(n: int) -> str:
        """Command to close valve ``n``."""
        return f"OUTP:VALV CLOSE,{n}"

    @staticmethod
    def valve_state(n: int) -> str:
        """Query for the state of valve ``n``."""
        return f"OUTP:VALV?,{n}"

    @staticmethod
    def temp_set_in(value: float) -> str:
        """Command line to set the inlet temperature setpoint (toggles control in the FW)."""
        return f"{Cmd.TEMP_SET_IN},{value}"


class Evt:
    """State-machine events (``EVT:`` prefix).

    Initialization handshake (sent *by* the SCADA to drive the startup sequence):

    * :attr:`INIT_OK` — advance PLC from STARTUP to CHECKUP.
    * :attr:`SCADA_OK` — SCADA side is ready (sent while PLC is in CHECKUP).
    * :attr:`SENSORS_OK` — all sensor probes passed (sent while PLC is in CHECKUP).
    * :attr:`FAULT_RECOVERABLE` — at least one sensor probe failed; PLC goes to SOFT ERROR.
    """

    # Initialisation handshake
    INIT_OK = "EVT:INIT OK"
    SCADA_OK = "EVT:SCADA OK"
    SENSORS_OK = "EVT:SENSORS OK"
    FAULT_RECOVERABLE = "EVT:FAULT RECOVERABLE"

    # Runtime control
    PAUSE = "EVT:PAUSE"
    UNPAUSE = "EVT:UNPAUSE"
    ACK_FAULT = "EVT:ACK FAULT"
    CONDITION_CLEARED = "EVT:CONDITION CLEARED"  # paired with ACK_FAULT to exit SOFT ERROR
    RETRY_CHECKUP = "EVT:RETRY CHECKUP"

    # Stop / shutdown
    SHUTDOWN = "EVT:SHUTDOWN"
    # SHUTDOWN: graceful ordered stop — works from MANUAL, PAUSE, CHECKUP, STARTUP.
    #   FW runs SafeState (actuators off, valves closed), then auto-returns to STARTUP.
    #   Use for the operator "stop the experiment" action; no fault flag is set.

    RESET_FAULT = "EVT:RESET FAULT"

    # ── Diagnostic-only events (not used by normal SCADA UI buttons) ──────────
    # STOP maps to kEStop in the FW. kEStop is only handled in SoftErrorState
    # (→ HardError). ManualState and PauseState ignore it. Do NOT wire this to
    # a UI button enabled in MANUAL or PAUSE — it will be silently discarded.
    ESTOP_DIAGNOSTIC = "EVT:STOP"


class Resp:
    """Canonical single-line replies the PLC sends back over the wire.

    Error replies are formatted firmware-side as ``"<code>,'MESSAGE'"`` and are
    not enumerated here; detect them with :func:`is_error`.
    """

    ON = "ON"
    OFF = "OFF"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    HIGH = "HIGH"
    LOW = "LOW"
    PONG = "PONG"
    OK = "OK"  # positive reply to a SYST:REINIT command


class State:
    """Canonical FSM state names as the PLC reports them in a STATE? reply."""

    STARTUP = "STARTUP"
    CHECKUP = "CHECKUP"
    MANUAL = "MANUAL"
    PAUSE = "PAUSE"
    SOFT_ERROR = "SOFT ERROR"
    HARD_ERROR = "HARD ERROR"
    SHUTDOWN = "SHUTDOWN"


@dataclass(frozen=True)
class ActuatorSpec:
    """Wire strings for one actuator: the on/off commands and their confirmation replies."""

    on_cmd: str
    off_cmd: str
    on_resp: str
    off_resp: str


# Maps each logical device to its protocol strings. This is the single place that
# couples a Device to the wire; the client correlates replies through it.
ACTUATORS: dict[Device, ActuatorSpec] = {
    Device.HEATER: ActuatorSpec(Cmd.HEAT_ON, Cmd.HEAT_OFF, Resp.ON, Resp.OFF),
    Device.PUMP: ActuatorSpec(Cmd.PUMP_ON, Cmd.PUMP_OFF, Resp.ON, Resp.OFF),
    Device.CHILLER: ActuatorSpec(Cmd.CHILL_ON, Cmd.CHILL_OFF, Resp.ON, Resp.OFF),
    Device.VALVE1: ActuatorSpec(Cmd.valve_open(1), Cmd.valve_close(1), Resp.OPEN, Resp.CLOSED),
    Device.VALVE2: ActuatorSpec(Cmd.valve_open(2), Cmd.valve_close(2), Resp.OPEN, Resp.CLOSED),
}

# Maps each logical sensor to the query command that reads it.
SENSORS: dict[Sensor, str] = {
    Sensor.TEMP_IN: Cmd.TEMP_IN,
    Sensor.TEMP_OUT: Cmd.TEMP_OUT,
    Sensor.TEMP_BATH: Cmd.TEMP_BATH,
    Sensor.TEMP_MIX: Cmd.TEMP_MIX,
    Sensor.FLOW: Cmd.FLOW,
    Sensor.LEVEL: Cmd.LEVEL,
}

# Maps each logical sensor to the command that re-initialises it on the PLC.
REINIT: dict[Sensor, str] = {
    Sensor.TEMP_IN: Cmd.REINIT_TEMP_IN,
    Sensor.TEMP_OUT: Cmd.REINIT_TEMP_OUT,
    Sensor.TEMP_BATH: Cmd.REINIT_TEMP_BATH,
    Sensor.TEMP_MIX: Cmd.REINIT_TEMP_MIX,
    Sensor.FLOW: Cmd.REINIT_FLOW,
    Sensor.LEVEL: Cmd.REINIT_LEVEL,
}


def parse_value(line: str) -> float | None:
    """Parse a numeric sensor reply (e.g. "25.30", "-5.3") to float, else None.

    Returns None for non-numeric replies such as "HIGH"/"LOW" or error strings,
    so callers can distinguish a measurement from a status/fault.
    """
    try:
        return float(line)
    except ValueError:
        return None


def is_error(response: str) -> bool:
    """True if ``response`` is a firmware error reply (e.g. "-101,'COMMAND REJECTED'").

    Errors are formatted as ``-<code>,'MESSAGE'``. The check requires both the
    leading minus sign and the comma so that negative sensor readings (e.g.
    "-5.3" from a sub-zero temperature) are not mistaken for errors.
    """
    text = response.lstrip()
    return text.startswith("-") and "," in text
