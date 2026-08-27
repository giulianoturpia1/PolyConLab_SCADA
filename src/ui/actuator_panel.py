"""ActuatorPanel — owns the actuator rows and their PLC command/confirmation flow.

Mirrors :class:`~ui.sensor_panel.SensorPanel`: it subscribes to the PLC signals
it cares about and keeps :class:`~ui.windows.main_window.MainWindow` out of the
actuator wire. Rows are painted only when the PLC confirms a state, so the UI
reflects the PLC and never a SCADA-side assumption.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from comms.plc_client import PlcClient
from models import Device
from ui.widgets.actuator_row import ActuatorRow


class ActuatorPanel(QObject):
    """Manages the actuator rows: command on click, repaint on PLC confirmation."""

    #: Human-readable message to surface in the log window (e.g. a rejection).
    log = Signal(str)

    def __init__(self, rows: dict[Device, ActuatorRow], plc: PlcClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows = rows
        self._plc = plc

        # A click sends the command; the row is not painted until the PLC confirms.
        for dev, row in self._rows.items():
            row.activated.connect(lambda on, d=dev: self._plc.set_actuator(d, on))

        self._plc.actuator_changed.connect(self._on_actuator_changed)
        self._plc.actuator_rejected.connect(self._on_actuator_rejected)

    # ── Public API ─────────────────────────────────────────────────────────────

    def reconcile(self) -> None:
        """Query the PLC for the authoritative state of every actuator.

        Replies arrive as :attr:`~comms.plc_client.PlcClient.actuator_changed`
        and repaint the rows through :meth:`_on_actuator_changed`.
        """
        self._plc.query_all_actuator_states()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the on/off buttons on every row (FSM gating)."""
        for row in self._rows.values():
            row.set_enabled_buttons(enabled)

    def reset(self) -> None:
        """Clear any stale ON styling — e.g. on disconnect."""
        for row in self._rows.values():
            row.set_active(False)

    # ── Private slots ──────────────────────────────────────────────────────────

    def _on_actuator_changed(self, dev: Device, on: bool) -> None:
        """Paint a row once the PLC confirms its new state."""
        self._rows[dev].set_active(on)

    def _on_actuator_rejected(self, dev: Device) -> None:
        """Surface that the PLC refused a command; the row is left unchanged."""
        self.log.emit(f"  PLC rechazó el comando — {self._rows[dev].label()} sin cambios.")
