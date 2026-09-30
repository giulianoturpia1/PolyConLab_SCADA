"""
Real-time temperature chart.

Wraps the QChart, its temperature lines and both axes. Purely a live display: it plots
the last :data:`config.data.CHART_WINDOW_S` of readings and keeps no history
of its own — see :class:`~ui.measurement_log.MeasurementLog` for recording and CSV
export of measurements.
Series visibility is driven externally via :meth:`set_series_visible` — each
temperature card click (through SensorPanel) enables or disables its series.

A sensor's line is broken wherever it has no reading (a fault, a timeout, a disabled
card or paused polling) instead of being drawn straight across the gap: each unbroken
stretch is its own ``QLineSeries`` ("segment"), and only the sensor's first segment has
a legend entry. Point markers are drawn only on a segment with a single point, which
would otherwise be invisible; on a dense line they merge into a thick band.
"""

from __future__ import annotations

from time import monotonic

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from config.data import CHART_TEMP_MAX_C, CHART_TEMP_MIN_C, CHART_WINDOW_S
from models import SENSOR_LABEL, Sensor
from ui.style import metrics as m
from ui.style import palette as col

# (name, color) — fixed order: tin, tout, tcam, tmez
_SERIES_CFG = [
    (SENSOR_LABEL[Sensor.TEMP_IN], col.BLUE),
    (SENSOR_LABEL[Sensor.TEMP_OUT], col.GREEN),
    (SENSOR_LABEL[Sensor.TEMP_BATH], col.ORANGE),
    (SENSOR_LABEL[Sensor.TEMP_MIX], col.RED),
]


class TemperatureChart(QObject):
    """Manages the temperature line chart's segments, axes and rolling time window."""

    def __init__(self, chart_view: QChartView) -> None:
        """Build the chart and attach it to the view."""
        super().__init__()
        self._t0: float | None = None  # monotonic time of the first point; x = seconds since then
        # Hidden until the user enables polling of that sensor.
        self._visible = [False] * len(_SERIES_CFG)
        # True when the sensor's next reading must start a new segment instead of joining the last one.
        self._gap = [False] * len(_SERIES_CFG)
        # Per sensor, its segments oldest first; the first one owns the legend entry.
        self._segments: list[list[QLineSeries]] = []

        self._chart = self._build_chart()
        for idx in range(len(_SERIES_CFG)):
            self._segments.append([self._new_segment(idx, owns_legend=True)])
        chart_view.setChart(self._chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

    # ── Internal setup ───────────────────────────────────────────────────────

    def _build_chart(self) -> QChart:
        """Create the QChart with its legend and both axes; return the configured chart."""
        chart = QChart()
        chart.setBackgroundBrush(QColor(col.PANEL))
        chart.setPlotAreaBackgroundBrush(QColor(col.BG))
        chart.setPlotAreaBackgroundVisible(True)
        chart.setTitle("")

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
        return chart

    def _new_segment(self, idx: int, owns_legend: bool = False) -> QLineSeries:
        """Create an empty line segment for sensor ``idx``, attached to the chart and both axes.

        Only the sensor's first segment (``owns_legend``) keeps its legend entry.
        """
        name, color = _SERIES_CFG[idx]
        seg = QLineSeries()
        seg.setName(name)
        pen = QPen(QColor(color))
        pen.setWidth(m.CHART_LINE_WIDTH_PX)
        seg.setPen(pen)
        seg.setMarkerSize(m.CHART_POINT_MARKER_PX)
        seg.setPointsVisible(False)
        self._chart.addSeries(seg)
        seg.attachAxis(self._ax_x)
        seg.attachAxis(self._ax_y)
        seg.setVisible(self._visible[idx])
        if not owns_legend:
            self._hide_legend_markers(seg)
        return seg

    def _hide_legend_markers(self, seg: QLineSeries) -> None:
        """Remove a continuation segment from the legend (its sensor is listed by its first segment).

        Qt shows a series' legend marker again whenever the series is shown, so this runs after
        every visibility change as well as on creation.
        """
        for marker in self._chart.legend().markers(seg):
            marker.setVisible(False)

    def _drop_segment(self, seg: QLineSeries) -> None:
        """Detach a segment from the chart and free it."""
        self._chart.removeSeries(seg)
        seg.deleteLater()

    @staticmethod
    def _refresh_markers(seg: QLineSeries) -> None:
        """Show the point marker only on a lone point, which draws no line of its own."""
        seg.setPointsVisible(seg.count() == 1)

    # ── Public API ───────────────────────────────────────────────────────────

    def set_series_visible(self, idx: int, visible: bool) -> None:
        """Show or hide sensor ``idx`` (0=Entrada, 1=Salida, 2=Camisa, 3=Mezcla)."""
        self._visible[idx] = visible
        for seg in self._segments[idx]:
            seg.setVisible(visible)
        for seg in self._segments[idx][1:]:
            self._hide_legend_markers(seg)

    def break_lines(self) -> None:
        """Make every sensor's next reading start a new segment (e.g. after polling was paused)."""
        self._gap = [True] * len(_SERIES_CFG)

    def clear(self) -> None:
        """Discard every plotted point and restart the time axis at 0 s with the next reading."""
        for segs in self._segments:
            for seg in segs[1:]:
                self._drop_segment(seg)
            del segs[1:]
            segs[0].clear()
            self._refresh_markers(segs[0])
        self._gap = [False] * len(_SERIES_CFG)
        self._t0 = None
        self._ax_x.setRange(0, CHART_WINDOW_S)

    def reset_visibility(self) -> None:
        """Hide all series — called on PLC disconnect so the chart starts clean on reconnect."""
        for idx in range(len(_SERIES_CFG)):
            self.set_series_visible(idx, False)

    def push(
        self,
        tin: float | None,
        tout: float | None,
        tcam: float | None,
        tmez: float | None,
    ) -> None:
        """Append one data point per sensor that has a reading; slides the time window when the limit is reached.

        ``None`` means that sensor has no reading this round (faulted, timed out or disabled):
        nothing is stored, and its line is broken so the next reading starts a new segment
        instead of being joined across the gap.
        """
        # X is real elapsed time, not a sample count, so the axis stays true when the sampling
        # period changes mid-session or rounds are skipped.
        now = monotonic()
        if self._t0 is None:
            self._t0 = now
        t_seconds = now - self._t0
        for idx, v in enumerate((tin, tout, tcam, tmez)):
            if v is None:
                self._gap[idx] = True
                continue
            segs = self._segments[idx]
            if self._gap[idx] and segs[-1].count():
                segs.append(self._new_segment(idx))
            self._gap[idx] = False
            segs[-1].append(t_seconds, v)
            self._refresh_markers(segs[-1])

        if t_seconds >= CHART_WINDOW_S:
            window_start = t_seconds - CHART_WINDOW_S
            self._ax_x.setRange(window_start, t_seconds)
            for segs in self._segments:
                self._trim(segs, window_start)

    def _trim(self, segs: list[QLineSeries], window_start: float) -> None:
        """Drop the points of a sensor that slid out of the window, and every segment left empty.

        The first segment is kept even when empty (it owns the legend entry), and so is the last
        one (the sensor's current line).
        """
        for seg in segs:
            stale = 0
            while stale < seg.count() and seg.at(stale).x() < window_start:
                stale += 1
            if stale:
                seg.removePoints(0, stale)
                self._refresh_markers(seg)
        for seg in segs[1:-1]:
            if not seg.count():
                self._drop_segment(seg)
        segs[1:-1] = [seg for seg in segs[1:-1] if seg.count()]
