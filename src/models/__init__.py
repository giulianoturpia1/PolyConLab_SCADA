"""Domain models: the logical hardware entities the SCADA monitors and controls."""

from __future__ import annotations

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
