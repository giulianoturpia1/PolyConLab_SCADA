"""
Real-time temperature chart.

Wraps the QChart, its four series and both axes. Purely a live display: it plots
the last :data:`config.data.CHART_WINDOW_S` of readings and keeps no history
of its own — see :class:`~ui.measurement_log.MeasurementLog` for recording and CSV
export of measurements.
Series visibility is driven externally via :meth:`set_series_visible` — each
temperature SensorCard click in MainWindow enables or disables its series.
"""

from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QPainter

from config.data import CHART_TEMP_MAX_C, CHART_TEMP_MIN_C, CHART_WINDOW_S
from config.polling import SENSOR_POLL_INTERVAL_MS
from ui.style import metrics as m
from ui.style import palette as col

# (name, color) — fixed order: tin, tout, tcam, tmez
_SERIES_CFG = [
    ("T. Entrada", col.BLUE),
    ("T. Salida", col.GREEN),
    ("T. Camisa", col.ORANGE),
    ("T. Mezcla", col.RED),
]


class TemperatureChart(QObject):
    """Manages the temperature line chart's series, axes and rolling time window."""

    def __init__(self, chart_view: QChartView) -> None:
        """Build the chart and attach it to the view."""
        super().__init__()
        self._t = 0
        self._series: list[QLineSeries] = []

        self._chart = self._build_chart()
        chart_view.setChart(self._chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

    # ── Internal setup ───────────────────────────────────────────────────────

    def _build_chart(self) -> QChart:
        """Create the QChart with all four series and both axes; return the configured chart."""
        chart = QChart()
        chart.setBackgroundBrush(QColor(col.PANEL))
        chart.setPlotAreaBackgroundBrush(QColor(col.BG))
        chart.setPlotAreaBackgroundVisible(True)
        chart.setTitle("")

        for name, color in _SERIES_CFG:
            s = QLineSeries()
            s.setName(name)
            s.setColor(QColor(color))
            s.setVisible(False)  # hidden until the user enables polling
            s.setPointsVisible(True)
            s.setMarkerSize(m.CHART_POINT_MARKER_PX)
            chart.addSeries(s)
            self._series.append(s)

        # Configure and show legend with color reference for each sensor
        legend = chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignTop)
        legend.setBackgroundVisible(False)
        legend.setLabelColor(QColor(col.TEXT))

        self._ax_x = QValueAxis()
        self._ax_x.setRange(0, CHART_WINDOW_S)
        self._ax_x.setTickCount(m.CHART_X_TICK_COUNT)
        self._ax_x.setLabelFormat("%d")
        self._ax_x.setLabelsColor(QColor(col.TEXT))
        self._ax_x.setGridLineColor(QColor(col.BORDER))
        self._ax_x.setTitleText("Tiempo (s)")
        self._ax_x.setTitleBrush(QColor(col.TEXT))

        self._ax_y = QValueAxis()
        self._ax_y.setRange(CHART_TEMP_MIN_C, CHART_TEMP_MAX_C)
        self._ax_y.setLabelFormat("%.0f ")
        self._ax_y.setLabelsColor(QColor(col.TEXT))
        self._ax_y.setGridLineColor(QColor(col.BORDER))
        self._ax_y.setTitleText("°C")
        self._ax_y.setTitleBrush(QColor(col.TEXT))

        chart.addAxis(self._ax_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(self._ax_y, Qt.AlignmentFlag.AlignLeft)
        for s in self._series:
            s.attachAxis(self._ax_x)
            s.attachAxis(self._ax_y)

        return chart

    # ── Public API ───────────────────────────────────────────────────────────

    def set_series_visible(self, idx: int, visible: bool) -> None:
        """Show or hide the series at ``idx`` (0=Entrada, 1=Salida, 2=Camisa, 3=Mezcla)."""
        self._series[idx].setVisible(visible)

    def reset_visibility(self) -> None:
        """Hide all series — called on PLC disconnect so the chart starts clean on reconnect."""
        for s in self._series:
            s.setVisible(False)

    def push(
        self,
        tin: float | None,
        tout: float | None,
        tcam: float | None,
        tmez: float | None,
    ) -> None:
        """Append one data point per enabled series; slides the time window when the limit is reached.

        A ``None`` value means that sensor is currently disabled — its series is
        left untouched so no phantom data is stored while polling is off.
        Only series that received a new point participate in the window-slide
        removal, keeping every series' point count internally consistent.
        """
        step_s = SENSOR_POLL_INTERVAL_MS / 1000  # one sample, in seconds
        t_seconds = self._t * step_s
        updated: list[QLineSeries] = []
        for s, v in zip(self._series, (tin, tout, tcam, tmez)):
            if v is not None:
                s.append(t_seconds, v)
                updated.append(s)
        self._t += 1

        if t_seconds >= CHART_WINDOW_S:
            self._ax_x.setRange(t_seconds - CHART_WINDOW_S + step_s, t_seconds)
            for s in updated:
                s.removePoints(0, 1)
