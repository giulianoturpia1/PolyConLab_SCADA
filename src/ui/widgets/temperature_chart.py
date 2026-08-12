"""
Real-time temperature chart.

Wraps the QChart, its four series and both axes.
Series visibility is driven externally via :meth:`set_series_visible` — each
temperature SensorCard click in MainWindow enables or disables its series.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor, QPainter

from ui.style import palette as col

# (name, color) — fixed order: tin, tout, tcam, tmez
_SERIES_CFG = [
    ("T. Entrada", col.BLUE),
    ("T. Salida", col.GREEN),
    ("T. Cámara", col.ORANGE),
    ("T. Mezcla", col.RED),
]


class TemperatureChart(QObject):
    """Manages the temperature line chart with a rolling time window."""

    WINDOW = 60  # number of data points visible at once
    _TEMP_MIN_C = 0  # default Y-axis lower bound (°C)
    _TEMP_MAX_C = 100  # default Y-axis upper bound (°C)

    def __init__(self, chart_view: QChartView) -> None:
        """Build the chart and attach it to the view."""
        super().__init__()
        self._t = 0
        self._series: list[QLineSeries] = []
        self._history: list[dict[str, float | None]] = []

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
            chart.addSeries(s)
            self._series.append(s)

        # Configure and show legend with color reference for each sensor
        legend = chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignTop)
        legend.setBackgroundVisible(False)
        legend.setLabelColor(QColor(col.TEXT))

        self._ax_x = QValueAxis()
        self._ax_x.setRange(0, self.WINDOW)
        self._ax_x.setLabelFormat("%d")
        self._ax_x.setLabelsColor(QColor(col.TEXT))
        self._ax_x.setGridLineColor(QColor(col.BORDER))
        self._ax_x.setTitleText("Tiempo (s)")
        self._ax_x.setTitleBrush(QColor(col.TEXT))

        self._ax_y = QValueAxis()
        self._ax_y.setRange(self._TEMP_MIN_C, self._TEMP_MAX_C)
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
        """Show or hide the series at ``idx`` (0=Entrada, 1=Salida, 2=Cámara, 3=Mezcla)."""
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
        t = self._t
        updated: list[QLineSeries] = []
        for s, v in zip(self._series, (tin, tout, tcam, tmez)):
            if v is not None:
                s.append(t, v)
                updated.append(s)
        self._t += 1

        self._history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "T. Entrada": tin,
                "T. Salida": tout,
                "T. Cámara": tcam,
                "T. Mezcla": tmez,
            }
        )

        if t >= self.WINDOW:
            self._ax_x.setRange(t - self.WINDOW + 1, t)
            for s in updated:
                s.removePoints(0, 1)

    def export_history(self, path: str | Path, limit: int = 50) -> bool:
        """Export the last ``limit`` measurement rows to a CSV file."""
        rows = self._history[-limit:] if limit > 0 else self._history
        if not rows:
            return False

        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Timestamp", "T. Entrada", "T. Salida", "T. Cámara", "T. Mezcla"])
            for row in rows:
                writer.writerow(
                    [
                        row.get("timestamp", ""),
                        self._format_value(row.get("T. Entrada")),
                        self._format_value(row.get("T. Salida")),
                        self._format_value(row.get("T. Cámara")),
                        self._format_value(row.get("T. Mezcla")),
                    ]
                )

        return True

    @staticmethod
    def _format_value(value: float | None) -> str:
        if value is None:
            return ""
        return f"{value:.3f}".rstrip("0").rstrip(".")
