"""SensorPanel — manages the six sensor display cards and chart integration.

Centralises every sensor-display concern so :class:`~ui.main_window.MainWindow`
stays focused on connection lifecycle and FSM state management.

Responsibilities owned here:
* Per-sensor card value and fault display
* Polling enable/disable (forwarded to :class:`~comms.plc_client.PlcClient`)
* Chart series visibility and temperature-batch accumulation
* Init-probe fault marking and clearing
* Full reset on disconnect
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from comms.plc_client import PlcClient
from comms.protocol import parse_value
from models import Sensor
from ui.style import palette as col
from ui.widgets.sensor_card import SensorCard
from ui.widgets.temperature_chart import TemperatureChart

# Temperature sensors forwarded to the chart, in the order TemperatureChart.push() expects.
_CHART_SENSORS = (Sensor.TEMP_IN, Sensor.TEMP_OUT, Sensor.TEMP_BATH, Sensor.TEMP_MIX)


class SensorPanel(QObject):
    """Manages the six sensor cards and their temperature-chart integration.

    Constructed after the card dict is built in ``_configure_widgets`` so the
    cards are fully labelled before signals are wired.
    """

    def __init__(
        self,
        cards: dict[Sensor, SensorCard],
        chart: TemperatureChart,
        plc: PlcClient,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cards = cards
        self._chart = chart
        self._plc = plc

        # Sensors currently plotted in the chart (user-selected subset).
        self._enabled_chart_sensors: set[Sensor] = set()
        # Accumulates one reading per enabled chart sensor before pushing to the chart.
        self._temp_batch: dict[Sensor, float] = {}

        # Wire card toggled signals to poll enable/disable and chart visibility.
        for sensor, card in self._cards.items():
            card.toggled.connect(lambda enabled, s=sensor: self._on_card_toggled(s, enabled))

        # Wire PLC sensor events directly — no indirection through MainWindow.
        self._plc.sensor_updated.connect(self._on_sensor_updated)
        self._plc.sensor_fault.connect(self._on_sensor_fault)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_interactive(self, enabled: bool) -> None:
        """Full connect/disconnect reset for all cards.

        Propagates to each card's :meth:`~ui.sensor_card.SensorCard.set_interactive`
        which resets polling and fault state on disconnect.  For FSM-state-based
        gating without resetting user selections, use :meth:`set_polling_allowed`.
        """
        for card in self._cards.values():
            card.set_interactive(enabled)

    def set_polling_allowed(self, allowed: bool) -> None:
        """Gate sensor card interaction and polling based on the PLC FSM state.

        Call with ``True`` only when the PLC is in MANUAL state (the only state
        where sensor read commands are accepted).  In all other states pass
        ``False`` to:

        * Make cards non-clickable (preserving the user's green-border selection).
        * Pause all active PlcClient sensor subscriptions so no MEAS queries are
          sent while the FW would reject them with COMMAND REJECTED.
        * Drop any partial temperature batch to avoid mixing stale data.

        When re-entering MANUAL the user's previous selections are automatically
        re-subscribed so polling resumes without any manual intervention.
        """
        for sensor, card in self._cards.items():
            card.set_clickable(allowed)
            if allowed:
                # Re-subscribe sensors the user had selected before the state changed.
                if card.is_polling:
                    self._plc.set_sensor_enabled(sensor, True)
            else:
                # Unsubscribe without clearing the card's visual selection.
                self._plc.set_sensor_enabled(sensor, False)

        if not allowed:
            # Drop partial batch — new readings will rebuild it cleanly on resume.
            self._temp_batch.clear()

    def mark_init_fault(self, sensor: Sensor, ok: bool) -> None:
        """Apply the init-probe fault indicator to *sensor*'s card if it failed."""
        if not ok:
            self._cards[sensor].set_fault(True)

    def clear_faults(self) -> None:
        """Clear init-probe fault indicators on all cards."""
        for card in self._cards.values():
            card.set_fault(False)

    def card_title(self, sensor: Sensor) -> str:
        """Return the configured display title for *sensor*'s card."""
        return self._cards[sensor].title()

    def reset(self) -> None:
        """Blank all cards, clear the temperature batch and reset chart visibility.

        Call this whenever the TCP connection is lost so the next connection
        starts from a clean visual state.
        """
        self._enabled_chart_sensors.clear()
        self._temp_batch.clear()
        self._chart.reset_visibility()
        for card in self._cards.values():
            card.set_value("--")

    # ── Private slots ──────────────────────────────────────────────────────────

    def _on_card_toggled(self, sensor: Sensor, enabled: bool) -> None:
        """Forward poll enable/disable to PlcClient and update chart series."""
        self._plc.set_sensor_enabled(sensor, enabled)

        if sensor in _CHART_SENSORS:
            idx = _CHART_SENSORS.index(sensor)
            self._chart.set_series_visible(idx, enabled)
            if enabled:
                self._enabled_chart_sensors.add(sensor)
            else:
                self._enabled_chart_sensors.discard(sensor)
                # Drop stale reading so the next batch does not mix old and new data.
                self._temp_batch.pop(sensor, None)

    def _on_sensor_updated(self, sensor: Sensor, value: str) -> None:
        """Show a fresh reading on its card; push to the chart when all enabled sensors reported."""
        self._cards[sensor].set_value(value)

        temp = parse_value(value)
        if temp is not None and sensor in self._enabled_chart_sensors:
            self._temp_batch[sensor] = temp
            # Push only when every currently-enabled chart sensor has reported.
            if all(s in self._temp_batch for s in self._enabled_chart_sensors):
                # Disabled sensors are passed as None so the chart skips their series.
                self._chart.push(*(self._temp_batch.get(s) for s in _CHART_SENSORS))
                self._temp_batch.clear()

    def _on_sensor_fault(self, sensor: Sensor) -> None:
        """Mark a card as ERR on a runtime poll fault; drop any partial batch."""
        self._cards[sensor].set_value("ERR", col.RED)
        self._temp_batch.pop(sensor, None)
