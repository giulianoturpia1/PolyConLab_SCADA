"""
Real-time temperature chart.

Wraps the QChart, its four series, the axes and the series-visibility
toggle buttons.  Instantiated by passing the QChartView and the toggles
container widget from the generated .ui.
"""

from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui import palette as col

# (name, color) — fixed order: tin, tout, tcam, tmez
_SERIES_CFG = [
    ("T. Entrada", col.BLUE),
    ("T. Salida", col.GREEN),
    ("T. Cámara", col.ORANGE),
    ("T. Mezcla", col.RED),
]


class TemperatureChart:
    """Manages the temperature line chart with a rolling time window."""

    WINDOW = 60  # number of data points visible at once

    def __init__(self, chart_view: QChartView, toggles_container: QWidget) -> None:
        self._t = 0
        self._series: list[QLineSeries] = []

        chart = self._build_chart()
        chart_view.setChart(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._build_toggles(toggles_container)

    # ── Internal setup ───────────────────────────────────────────────────────

    def _build_chart(self) -> QChart:
        chart = QChart()
        chart.setBackgroundBrush(QColor(col.PANEL))
        chart.setPlotAreaBackgroundBrush(QColor(col.BG))
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setLabelColor(QColor(col.TEXT))
        chart.setTitle("")

        for name, color in _SERIES_CFG:
            s = QLineSeries()
            s.setName(name)
            s.setColor(QColor(color))
            chart.addSeries(s)
            self._series.append(s)

        self._ax_x = QValueAxis()
        self._ax_x.setRange(0, self.WINDOW)
        self._ax_x.setLabelFormat("%d")
        self._ax_x.setLabelsColor(QColor(col.TEXT))
        self._ax_x.setGridLineColor(QColor(col.BORDER))
        self._ax_x.setTitleText("Tiempo (s)")
        self._ax_x.setTitleBrush(QColor(col.TEXT))

        self._ax_y = QValueAxis()
        self._ax_y.setRange(0, 100)
        self._ax_y.setLabelFormat("%.0f°")
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

    def _build_toggles(self, container: QWidget) -> None:
        lay = QHBoxLayout(container)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)
        lay.addStretch()

        for (label, color), series in zip(_SERIES_CFG, self._series):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {col.PANEL};
                    border: 2px solid {color};
                    border-radius: 4px;
                    color: {color};
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:!checked {{
                    border-color: {col.BORDER};
                    color: {col.GRAY};
                    font-weight: normal;
                }}
            """)
            btn.toggled.connect(series.setVisible)
            lay.addWidget(btn)

        lay.addStretch()

    # ── Public API ───────────────────────────────────────────────────────────

    def push(self, tin: float, tout: float, tcam: float, tmez: float) -> None:
        """Append one data point to each series; slides the time window when the limit is reached."""
        t = self._t
        for s, v in zip(self._series, (tin, tout, tcam, tmez)):
            s.append(t, v)
        self._t += 1

        if t >= self.WINDOW:
            self._ax_x.setRange(t - self.WINDOW + 1, t)
            for s in self._series:
                s.removePoints(0, 1)
