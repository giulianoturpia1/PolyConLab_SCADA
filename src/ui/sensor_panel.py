"""SensorPanel — manages the six sensor display cards and chart integration.

Centralises every sensor-display concern so neither the window nor
:class:`~ui.scada_controller.ScadaController` touches the cards directly.

Responsibilities owned here:
* Per-sensor card value and fault display
* Polling enable/disable (forwarded to :class:`~comms.plc_client.PlcClient`)
* Chart series visibility, temperature-batch accumulation and measurement-log recording
* Init-probe fault marking and clearing
* Full reset on disconnect
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from comms.plc_client import PlcClient
from comms.protocol import parse_value
from config.data import DEFAULT_TEMP_LIMITS
from models import Sensor, TempLimits
from ui.measurement_log import MeasurementLog
from ui.style import palette as col
from ui.widgets.sensor_card import SensorCard
from ui.widgets.temperature_chart import TemperatureChart

# Temperature sensors forwarded to the chart, in the order TemperatureChart.push() expects.
_CHART_SENSORS = (Sensor.TEMP_IN, Sensor.TEMP_OUT, Sensor.TEMP_BATH, Sensor.TEMP_MIX)


class SensorPanel(QObject):
    """Manages the six sensor cards, their temperature-chart integration and measurement logging.

    Constructed after the card dict is built in ``_configure_widgets`` so the
    cards are fully labelled before signals are wired.
    """

    #: Human-readable message to surface in the log window.
    log = Signal(str)

    def __init__(
        self,
        cards: dict[Sensor, SensorCard],
        chart: TemperatureChart,
        log: MeasurementLog,
        plc: PlcClient,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cards = cards
        self._chart = chart
        self._log = log
        self._plc = plc

        # Sensors currently plotted in the chart (user-selected subset).
        self._enabled_chart_sensors: set[Sensor] = set()
        # Accumulates one reading per enabled chart sensor before pushing to the chart.
        self._temp_batch: dict[Sensor, float] = {}
        # Enabled chart sensors currently in a fault state; excluded from the
        # "all reported" gate so one faulty sensor cannot stall the whole chart.
        self._faulted_chart_sensors: set[Sensor] = set()
        # Bath reading at/over the PLC's heater limit and not yet back under the clear threshold.
        self._over_limit = False
        self._limits = DEFAULT_TEMP_LIMITS

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
            self._faulted_chart_sensors.clear()
            # Readings resume after an unknown pause: do not join them to the last ones.
            self._chart.break_lines()

    def mark_init_fault(self, sensor: Sensor, ok: bool) -> None:
        """Apply the init-probe fault indicator to *sensor*'s card if it failed."""
        if not ok:
            self._cards[sensor].set_fault(True)

    def clear_fault(self, sensor: Sensor) -> None:
        """Clear the init-probe fault indicator on a single card and blank its value.

        ``SensorCard.set_fault(False)`` only reverts the border; the value label
        keeps its ``"FALLO"`` text until the next poll, and re-init runs in SOFT
        ERROR where polling is paused — so blank the value here to show the card
        recovered.
        """
        card = self._cards[sensor]
        card.set_fault(False)
        card.set_value("--")

    def clear_faults(self) -> None:
        """Clear init-probe fault indicators on all cards."""
        for card in self._cards.values():
            card.set_fault(False)

    def card_title(self, sensor: Sensor) -> str:
        """Return the configured display title for *sensor*'s card."""
        return self._cards[sensor].title()

    def set_temp_limits(self, limits: TempLimits) -> None:
        """Follow the bath thresholds the PLC reported."""
        self._limits = limits

    def reset(self) -> None:
        """Blank all cards, clear the temperature batch and reset chart visibility.

        Call this whenever the TCP connection is lost so the next connection
        starts from a clean visual state.
        """
        self._enabled_chart_sensors.clear()
        self._temp_batch.clear()
        self._faulted_chart_sensors.clear()
        self._over_limit = False
        self._chart.reset_visibility()
        self._chart.break_lines()
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
                self._faulted_chart_sensors.discard(sensor)

    def _on_sensor_updated(self, sensor: Sensor, value: str) -> None:
        """Show a fresh reading on its card; push to the chart once every enabled sensor has reported or faulted."""
        temp = parse_value(value)
        over_limit = sensor == Sensor.TEMP_BATH and temp is not None and self._track_bath_limit(temp)
        self._cards[sensor].set_value(value, col.ORANGE if over_limit else col.WHITE)

        if temp is not None and sensor in self._enabled_chart_sensors:
            self._faulted_chart_sensors.discard(sensor)  # a reading means it recovered
            self._temp_batch[sensor] = temp
            self._maybe_push_chart()

    def _track_bath_limit(self, temp: float) -> bool:
        """Follow the PLC's heater limit on the bath reading and log each crossing; True while over it."""
        limit, clear = self._limits.bath_limit, self._limits.bath_clear
        if not self._over_limit and temp >= limit:
            self._over_limit = True
            self.log.emit(
                f"Temperatura de camisa {temp:.1f} °C: alcanzó el límite de {limit:g} °C. "
                f"El PLC apaga el calentador hasta que baje de {clear:g} °C."
            )
        elif self._over_limit and temp < clear:
            self._over_limit = False
            self.log.emit(f"Temperatura de camisa bajo {clear:g} °C: el PLC vuelve a permitir el calentador.")
        return self._over_limit

    def _on_sensor_fault(self, sensor: Sensor) -> None:
        """Mark a card as ERR on a runtime poll fault; let the other series still flush."""
        self._cards[sensor].set_value("ERR", col.RED)
        self._temp_batch.pop(sensor, None)
        if sensor in self._enabled_chart_sensors:
            self._faulted_chart_sensors.add(sensor)
            # A fault on the last-awaited sensor must not stall the healthy ones.
            self._maybe_push_chart()

    def _maybe_push_chart(self) -> None:
        """Push one chart point once every enabled chart sensor has either reported or faulted.

        Faulted sensors are passed to the chart as None (skipped series), so a
        single failing sensor never freezes the others. A round with no real
        readings at all is dropped rather than plotting an empty point.
        """
        active = self._enabled_chart_sensors
        if not active:
            return
        if not all((s in self._temp_batch or s in self._faulted_chart_sensors) for s in active):
            return
        if not any(s in self._temp_batch for s in active):
            # Every enabled chart sensor is faulted: nothing real to plot.
            self._temp_batch.clear()
            return
        readings = tuple(self._temp_batch.get(s) for s in _CHART_SENSORS)
        self._chart.push(*readings)
        self._log.record(*readings)
        self._temp_batch.clear()
