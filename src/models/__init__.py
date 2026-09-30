"""Domain models: the logical hardware entities the SCADA monitors and controls."""

from __future__ import annotations

from enum import Enum, auto


class Device(Enum):
    """Logical actuators the operator can toggle, independent of the wire protocol."""

    HEATER = auto()
    PUMP = auto()
    MIXER = auto()
    VALVE1 = auto()


class Sensor(Enum):
    """Logical sensors the system polls, independent of the wire protocol."""

    TEMP_IN = auto()
    TEMP_OUT = auto()
    TEMP_BATH = auto()
    TEMP_MIX = auto()
    FLOW = auto()
    LEVEL = auto()


# Display name of each sensor (Spanish UI): card titles, chart legend, CSV header and log
# messages all take it from here.
SENSOR_LABEL: dict[Sensor, str] = {
    Sensor.TEMP_IN: "T. Entrada",
    Sensor.TEMP_OUT: "T. Salida",
    Sensor.TEMP_BATH: "T. Camisa",
    Sensor.TEMP_MIX: "T. Mezcla",
    Sensor.FLOW: "Caudal",
    Sensor.LEVEL: "Nivel",
}

# Unit shown under each sensor's reading ("" when the reading is a state, not a quantity).
SENSOR_UNIT: dict[Sensor, str] = {
    Sensor.TEMP_IN: "°C",
    Sensor.TEMP_OUT: "°C",
    Sensor.TEMP_BATH: "°C",
    Sensor.TEMP_MIX: "°C",
    Sensor.FLOW: "L/min",
    Sensor.LEVEL: "",
}
