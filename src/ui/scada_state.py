"""SCADA-side state machine: maps the compound (connection + PLC FSM) state to UI control permissions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ScadaState(Enum):
    DISCONNECTED = auto()
    CONNECTING   = auto()
    INITIALIZING = auto()   # TCP up, handshake in progress
    STARTUP      = auto()
    CHECKUP      = auto()
    MANUAL       = auto()
    PAUSE        = auto()
    SOFT_ERROR   = auto()
    HARD_ERROR   = auto()
    SHUTDOWN     = auto()
    UNKNOWN      = auto()   # connected but state string not recognised


@dataclass(frozen=True)
class _EnabledControls:
    sensors:   bool = False
    actuators: bool = False
    pause:     bool = False
    resume:    bool = False
    stop:      bool = False
    ack:       bool = False
    retry:     bool = False
    reinit:    bool = False


STATE_CONTROLS: dict[ScadaState, _EnabledControls] = {
    ScadaState.DISCONNECTED:  _EnabledControls(),
    ScadaState.CONNECTING:    _EnabledControls(),
    ScadaState.INITIALIZING:  _EnabledControls(),
    ScadaState.STARTUP:       _EnabledControls(),
    ScadaState.CHECKUP:       _EnabledControls(),
    ScadaState.MANUAL:        _EnabledControls(sensors=True, actuators=True, pause=True, stop=True),
    ScadaState.PAUSE:         _EnabledControls(resume=True, stop=True),
    ScadaState.SOFT_ERROR:    _EnabledControls(ack=True, retry=True, reinit=True),
    ScadaState.HARD_ERROR:    _EnabledControls(),
    ScadaState.SHUTDOWN:      _EnabledControls(),
    ScadaState.UNKNOWN:       _EnabledControls(),
}

_PLC_MAP: dict[str, ScadaState] = {
    "STARTUP":    ScadaState.STARTUP,
    "CHECKUP":    ScadaState.CHECKUP,
    "MANUAL":     ScadaState.MANUAL,
    "PAUSE":      ScadaState.PAUSE,
    "SOFT ERROR": ScadaState.SOFT_ERROR,
    "HARD ERROR": ScadaState.HARD_ERROR,
    "SHUTDOWN":   ScadaState.SHUTDOWN,
}


def from_plc(raw: str) -> ScadaState:
    """Translate a raw PLC state string to its ScadaState counterpart."""
    return _PLC_MAP.get(raw, ScadaState.UNKNOWN)
