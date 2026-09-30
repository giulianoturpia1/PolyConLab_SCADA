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
from ui.style import metrics as m
from ui.style import palette as col

# Corner rounding for the toggle button, in px.

# Button style while control was last requested ON (in MANUAL).
_ACTIVE_STYLE = (
    f"background-color:{col.ACTIVE};color:{col.WHITE};"
    f"font-weight:bold;border-radius:{m.TEMP_CONTROL_RADIUS_PX}px;"
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
        # The PLC confirms each toggle with the control state it settled on.
        self._plc.temp_control_changed.connect(self._on_temp_control_changed)

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
        if self._plc.set_temperature_control(value):
            # The indicator is not moved here: it follows the PLC, either through the heater state
            # or through the confirmation this command gets back.
            self.log.emit(f"Control de temperatura solicitado: {Cmd.temp_set_in(value)}")
        else:
            self.log.emit("No conectado — comando de temperatura no enviado.")

    def _on_temp_control_changed(self, on: bool) -> None:
        """Log the control state the PLC reported after a toggle."""
        self.log.emit(f"Control de temperatura {'ACTIVADO' if on else 'DESACTIVADO'} (confirmado por el PLC).")

    def _on_actuator_changed(self, device: Device, on: bool) -> None:
        """Update the indicator when the PLC's heater state changes."""
        if device == Device.HEATER:
            self._set_requested(on)

    def _set_requested(self, requested: bool) -> None:
        self._requested = requested
        self._button.setStyleSheet(_ACTIVE_STYLE if requested else _IDLE_STYLE)
