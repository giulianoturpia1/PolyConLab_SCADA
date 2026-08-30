"""TemperatureControl — owns the manual temperature-setpoint controls.

Wraps the promoted slider / spinbox / toggle button and the send logic for the
``TEMP:SET:IN`` command. Synchronizes the button indicator with the PLC's actual
heater state via the ``actuator_changed`` signal, and clears it when leaving
MANUAL or the link drops.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QAbstractButton, QAbstractSlider, QSpinBox

from comms.plc_client import PlcClient
from comms.protocol import Cmd
from models import Device
from ui.style import palette as col

# Corner rounding for the toggle button, in px.
_BORDER_RADIUS_PX = 4

# Button style while control was last requested ON (in MANUAL).
_ACTIVE_STYLE = (
    f"background-color:{col.ACTIVE};color:{col.WHITE};"
    f"font-weight:bold;border-radius:{_BORDER_RADIUS_PX}px;"
)
_IDLE_STYLE = "font-weight:bold;"


class TemperatureControl(QObject):
    """Manual setpoint controls: send TEMP:SET:IN on click, reflect the request."""

    #: Human-readable message to surface in the log window.
    log = Signal(str)

    def __init__(
        self,
        button: QAbstractButton,
        spinbox: QSpinBox,
        slider: QAbstractSlider,
        plc: PlcClient,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._button = button
        self._spinbox = spinbox
        self._slider = slider
        self._plc = plc
        self._requested = False  # current state of the heater (from PLC)

        self._button.clicked.connect(self._on_clicked)
        # Listen to the PLC's actual heater state to keep the indicator in sync.
        self._plc.actuator_changed.connect(self._on_actuator_changed)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all three controls together (FSM gating)."""
        self._slider.setEnabled(enabled)
        self._spinbox.setEnabled(enabled)
        self._button.setEnabled(enabled)

    def clear(self) -> None:
        """Force the request indicator off — on leaving MANUAL or disconnect."""
        self._set_requested(False)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _on_clicked(self) -> None:
        value = self._spinbox.value()
        line = Cmd.temp_set_in(value)
        if self._plc.send_raw(line):
            # Toggle is sent to the PLC; state will update via actuator_changed signal.
            status = "ACTIVADO" if not self._requested else "DESACTIVADO"
            self.log.emit(f"Control de temperatura {status}: {line}")
        else:
            self.log.emit("No conectado — comando de temperatura no enviado.")

    def _on_actuator_changed(self, device: Device, on: bool) -> None:
        """Update the indicator when the PLC's heater state changes."""
        if device == Device.HEATER:
            self._set_requested(on)

    def _set_requested(self, requested: bool) -> None:
        self._requested = requested
        self._button.setStyleSheet(_ACTIVE_STYLE if requested else _IDLE_STYLE)
