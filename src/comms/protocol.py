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
from enum import Enum, auto


class Device(Enum):
    """Logical actuators the operator can toggle, independent of the wire protocol."""

    HEATER = auto()
    PUMP = auto()
    CHILLER = auto()
    VALVE1 = auto()
    VALVE2 = auto()


class Sensor(Enum):
    """Logical sensors the system polls, independent of the wire protocol."""

    TEMP_IN = auto()
    TEMP_OUT = auto()
    TEMP_BATH = auto()
    TEMP_MIX = auto()
    FLOW = auto()
    LEVEL = auto()


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


class Evt:
    """State-machine events (``EVT:`` prefix)."""

    PAUSE = "EVT:PAUSE"
    UNPAUSE = "EVT:UNPAUSE"
    STOP = "EVT:STOP"
    ACK_FAULT = "EVT:ACK FAULT"
    RETRY_CHECKUP = "EVT:RETRY CHECKUP"
    SHUTDOWN = "EVT:SHUTDOWN"
    RESET_FAULT = "EVT:RESET FAULT"


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
