from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui import palette as col


class _SensorCard(QFrame):
    """Compact card showing a title, current value and unit."""

    def __init__(self, parent: QWidget | None = None, title: str = "–", unit: str = "") -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {col.PANEL};
                border: 1px solid {col.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setMinimumSize(100, 88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(1)

        self._lbl_title = QLabel(title.upper())
        self._lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_title.setStyleSheet(
            f"background:transparent;border:none;color:{col.TEXT};font-size:9px;letter-spacing:1px;"
        )

        self._val = QLabel("--")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setStyleSheet(
            f"background:transparent;border:none;color:{col.WHITE};font-size:22px;font-weight:bold;"
        )

        self._lbl_unit = QLabel(unit)
        self._lbl_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_unit.setStyleSheet(f"background:transparent;border:none;color:{col.TEXT};font-size:10px;")

        lay.addWidget(self._lbl_title)
        lay.addWidget(self._val)
        lay.addWidget(self._lbl_unit)

    def configure(self, title: str, unit: str = "") -> None:
        self._lbl_title.setText(title.upper())
        self._lbl_unit.setText(unit)

    def set_value(self, v: str, color: str = col.WHITE) -> None:
        self._val.setText(v)
        self._val.setStyleSheet(f"background:transparent;border:none;color:{color};font-size:22px;font-weight:bold;")


class _ActuatorRow(QWidget):
    """Row with an LED indicator, label and two buttons (on / off)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "Actuador",
        on_text: str = "ON",
        off_text: str = "OFF",
    ) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(18)
        self._dot.setStyleSheet(f"color:{col.GRAY};font-size:14px;")

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{col.WHITE};font-size:12px;")
        self._lbl.setMinimumWidth(88)

        self.btn_on = QPushButton(on_text)
        self.btn_on.setObjectName("btn_on")
        self.btn_on.setFixedWidth(72)
        self.btn_on.setEnabled(False)

        self.btn_off = QPushButton(off_text)
        self.btn_off.setFixedWidth(72)
        self.btn_off.setEnabled(False)

        lay.addWidget(self._dot)
        lay.addWidget(self._lbl, stretch=1)
        lay.addWidget(self.btn_on)
        lay.addWidget(self.btn_off)

    def configure(self, label: str, on_text: str = "ON", off_text: str = "OFF") -> None:
        self._lbl.setText(label)
        self.btn_on.setText(on_text)
        self.btn_off.setText(off_text)

    def set_active(self, active: bool) -> None:
        c = col.GREEN if active else col.GRAY
        self._dot.setStyleSheet(f"color:{c};font-size:14px;")

    def set_enabled_buttons(self, enabled: bool) -> None:
        self.btn_on.setEnabled(enabled)
        self.btn_off.setEnabled(enabled)
