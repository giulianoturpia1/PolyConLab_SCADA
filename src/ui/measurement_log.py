"""Measurement log: records temperature readings alongside confirmed system status.

Replaces the private history :class:`~ui.widgets.temperature_chart.TemperatureChart`
used to keep for CSV export. Unlike the chart, this module can see system status —
not because the chart's history was wrong, but because recording status alongside
temperature readings is a job that belongs to the log, not to a plotting widget.
it listens to :class:`~comms.plc_client.PlcClient` actuator, temp-control and FSM
state signals and stamps every recorded row with the last confirmed value of each.

Actuator and temp-control status are event-driven: the PLC confirms a new state only
when it changes, and nothing polls the actuators periodically (see PlcClient). Until
the first confirmation arrives for a given session, that status is unknown — recording
it as OFF/CLOSED would be assuming a PLC state this codebase never assumes, so an
unknown status is written to the CSV as an empty cell instead.
"""

from __future__ import annotations

import csv
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject

from comms.plc_client import PlcClient
from comms.protocol import Resp
from models import Device

# Maximum recorded rows kept in memory, comfortably above the download dialog's
# 100 000-row maximum (see MainWindow._download_data).
_MAX_ROWS = 200_000

# CSV column headers, in the exact order written by export_csv(). The first five
# columns are byte-identical to the legacy TemperatureChart.export_history() output
# so existing consumers of the file keep working; the rest are appended on the right.
_CSV_HEADER = [
    "Timestamp",
    "T. Entrada",
    "T. Salida",
    "T. Camisa",
    "T. Mezcla",
    "Estado",
    "Calefactor",
    "Bomba",
    "Enfriador",
    "Válvula 1",
    "Válvula 2",
    "Control Temp",
]

# Per-device (on-word, off-word) pair used to render its confirmed boolean status.
# Heater/pump/chiller report ON/OFF; the valves report OPEN/CLOSED.
_DEVICE_ON_OFF: dict[Device, tuple[str, str]] = {
    Device.HEATER: (Resp.ON, Resp.OFF),
    Device.PUMP: (Resp.ON, Resp.OFF),
    Device.CHILLER: (Resp.ON, Resp.OFF),
    Device.VALVE1: (Resp.OPEN, Resp.CLOSED),
    Device.VALVE2: (Resp.OPEN, Resp.CLOSED),
}

# Device columns, in CSV column order (Calefactor, Bomba, Enfriador, Válvula 1, Válvula 2).
_DEVICE_COLUMNS = (Device.HEATER, Device.PUMP, Device.CHILLER, Device.VALVE1, Device.VALVE2)


class MeasurementLog(QObject):
    """Records one row per measurement round, annotated with the system's confirmed status.

    Connects to :class:`~comms.plc_client.PlcClient` to keep a "last confirmed status"
    snapshot: a per-:class:`~models.Device` on/off flag, the temperature-control flag,
    and the raw FSM state name. Every value starts unknown (``None``) rather than a
    guessed False/OFF, because the PLC has not yet told the SCADA what it is. A
    :attr:`~comms.plc_client.PlcClient.disconnected` clears that snapshot back to
    unknown, since a new session must not inherit the previous one's states — but it
    does not clear the rows already recorded.
    """

    def __init__(self, plc: PlcClient, parent: QObject | None = None) -> None:
        """Wire up to *plc*'s status signals and start with an empty, all-unknown log."""
        super().__init__(parent)
        self._plc = plc
        self._rows: deque[dict[str, object]] = deque(maxlen=_MAX_ROWS)
        self._reset_status()

        self._plc.actuator_changed.connect(self._on_actuator_changed)
        self._plc.temp_control_changed.connect(self._on_temp_control_changed)
        self._plc.state_received.connect(self._on_state_received)
        self._plc.disconnected.connect(self._on_disconnected)

    # ── Public API ───────────────────────────────────────────────────

    def record(
        self,
        tin: float | None,
        tout: float | None,
        tcam: float | None,
        tmez: float | None,
    ) -> None:
        """Append one row: the four temperatures plus the status as it stands right now.

        Oldest rows are dropped once :data:`_MAX_ROWS` is exceeded.
        """
        self._rows.append(
            {
                "timestamp": datetime.now().isoformat(),
                "T. Entrada": tin,
                "T. Salida": tout,
                "T. Camisa": tcam,
                "T. Mezcla": tmez,
                "state": self._fsm_state,
                "actuators": dict(self._actuator_state),
                "temp_control": self._temp_control,
            }
        )

    def export_csv(self, path: str | Path, limit: int = 50) -> bool:
        """Write the last *limit* recorded rows to *path* as CSV; return False if there are none.

        A status column is left as an empty string for any row recorded before the
        PLC's first confirmation of that value — see the class docstring for why an
        empty cell, rather than an assumed OFF/CLOSED, is the correct default.
        """
        rows = list(self._rows)[-limit:] if limit > 0 else list(self._rows)
        if not rows:
            return False

        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(_CSV_HEADER)
            for row in rows:
                writer.writerow(self._format_row(row))

        return True

    # ── Private slots ───────────────────────────────────────────────

    def _on_actuator_changed(self, dev: Device, on: bool) -> None:
        """Record the PLC's confirmed on/off state for *dev*."""
        self._actuator_state[dev] = on

    def _on_temp_control_changed(self, on: bool) -> None:
        """Record the PLC's confirmed temperature-control state."""
        self._temp_control = on

    def _on_state_received(self, state: str) -> None:
        """Record the raw FSM state name from the latest STATE? reply."""
        self._fsm_state = state

    def _on_disconnected(self) -> None:
        """Clear the confirmed-status snapshot back to unknown; recorded rows are kept."""
        self._reset_status()

    # ── Internals ───────────────────────────────────────────────────

    def _reset_status(self) -> None:
        """Reset the confirmed-status snapshot to all-unknown."""
        self._actuator_state: dict[Device, bool | None] = {dev: None for dev in Device}
        self._temp_control: bool | None = None
        self._fsm_state: str | None = None

    def _format_row(self, row: dict[str, object]) -> list[str]:
        """Render one recorded row as CSV cell strings, in :data:`_CSV_HEADER` order."""
        actuators: dict[Device, bool | None] = row["actuators"]  # type: ignore[assignment]
        cells = [
            row["timestamp"],
            self._format_temp(row["T. Entrada"]),
            self._format_temp(row["T. Salida"]),
            self._format_temp(row["T. Camisa"]),
            self._format_temp(row["T. Mezcla"]),
            row["state"] or "",
        ]
        for dev in _DEVICE_COLUMNS:
            on_word, off_word = _DEVICE_ON_OFF[dev]
            cells.append(self._format_bool(actuators.get(dev), on_word, off_word))
        cells.append(self._format_bool(row["temp_control"], Resp.ON, Resp.OFF))
        return cells

    @staticmethod
    def _format_temp(value: object) -> str:
        """Format a temperature reading, or "" for a disabled/unavailable sensor."""
        if value is None:
            return ""
        return f"{value:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_bool(value: object, on_word: str, off_word: str) -> str:
        """Format a confirmed on/off status, or "" while it is still unknown."""
        if value is None:
            return ""
        return on_word if value else off_word
