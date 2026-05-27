from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui import palette as col

# Button style helpers -------------------------------------------------------
_BTN_BASE = "border-radius:4px;font-size:12px;padding:4px 0;border:1px solid {border};background:{bg};color:{fg};"


def _btn_style(active: bool) -> str:
    """Return the stylesheet for an actuator button in its active or inactive state."""
    if active:
        return _BTN_BASE.format(border=col.GREEN, bg=col.GREEN, fg=col.BG)
    return _BTN_BASE.format(border=col.BORDER, bg=col.PANEL, fg=col.TEXT)


def _btn_style_off(active: bool) -> str:
    """Return the stylesheet for an OFF button (highlighted when the row is inactive)."""
    if not active:
        return _BTN_BASE.format(border=col.GRAY, bg=col.GRAY, fg=col.BG)
    return _BTN_BASE.format(border=col.BORDER, bg=col.PANEL, fg=col.TEXT)


class _SensorCard(QFrame):
    """Compact card showing a title, current value and unit."""

    def __init__(self, parent: QWidget | None = None, title: str = "–", unit: str = "") -> None:
        """Build the card layout; call configure() after construction to set real labels."""
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

        # Opacity animation: fades the value label in whenever set_value() is called.
        self._val_effect = QGraphicsOpacityEffect(self._val)
        self._val_effect.setOpacity(1.0)
        self._val.setGraphicsEffect(self._val_effect)
        self._val_anim = QPropertyAnimation(self._val_effect, b"opacity", self)
        self._val_anim.setDuration(450)
        self._val_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def configure(self, title: str, unit: str = "") -> None:
        """Set the card title and unit label (called after setupUi promotion)."""
        self._lbl_title.setText(title.upper())
        self._lbl_unit.setText(unit)

    def set_value(self, v: str, color: str = col.WHITE) -> None:
        """Update the displayed value and play a fade-in to signal the change to the operator."""
        self._val.setText(v)
        self._val.setStyleSheet(f"background:transparent;border:none;color:{color};font-size:22px;font-weight:bold;")
        self._val_anim.stop()
        self._val_anim.setStartValue(0.15)
        self._val_anim.setEndValue(1.0)
        self._val_anim.start()


class _ActuatorRow(QWidget):
    """Row with an LED indicator, label and two buttons (on / off)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "Actuador",
        on_text: str = "ON",
        off_text: str = "OFF",
    ) -> None:
        """Build the row layout; call configure() after construction to set real labels."""
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(8)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{col.WHITE};font-size:12px;")
        self._lbl.setMinimumWidth(88)

        self.btn_on = QPushButton(on_text)
        self.btn_on.setObjectName("btn_on")
        self.btn_on.setFixedWidth(72)
        self.btn_on.setEnabled(False)
        self.btn_on.setStyleSheet(_btn_style(False))

        self.btn_off = QPushButton(off_text)
        self.btn_off.setFixedWidth(72)
        self.btn_off.setEnabled(False)
        self.btn_off.setStyleSheet(_btn_style_off(False))

        lay.addWidget(self._lbl, stretch=1)
        lay.addWidget(self.btn_on)
        lay.addWidget(self.btn_off)

        # Wire clicks to the local state machine.
        self.btn_on.clicked.connect(lambda: self.set_active(True))
        self.btn_off.clicked.connect(lambda: self.set_active(False))

        # Opacity animations: flash whichever button confirms the new state.
        self._btn_on_effect = QGraphicsOpacityEffect(self.btn_on)
        self._btn_on_effect.setOpacity(1.0)
        self.btn_on.setGraphicsEffect(self._btn_on_effect)
        self._btn_on_anim = QPropertyAnimation(self._btn_on_effect, b"opacity", self)
        self._btn_on_anim.setDuration(400)
        self._btn_on_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._btn_off_effect = QGraphicsOpacityEffect(self.btn_off)
        self._btn_off_effect.setOpacity(1.0)
        self.btn_off.setGraphicsEffect(self._btn_off_effect)
        self._btn_off_anim = QPropertyAnimation(self._btn_off_effect, b"opacity", self)
        self._btn_off_anim.setDuration(400)
        self._btn_off_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def configure(self, label: str, on_text: str = "ON", off_text: str = "OFF") -> None:
        """Set the row label and button texts (called after setupUi promotion)."""
        self._lbl.setText(label)
        self.btn_on.setText(on_text)
        self.btn_off.setText(off_text)

    def set_active(self, active: bool) -> None:
        """Transition the row to ON or OFF state.

        Applies persistent selected/unselected styling to both buttons, then fades
        in the button that confirmed the new state.
        """
        # Persist the new selected/unselected appearance for both buttons.
        self.btn_on.setStyleSheet(_btn_style(active))
        self.btn_off.setStyleSheet(_btn_style_off(active))

        # Fade in the button that confirmed the state change; keep the other opaque.
        if active:
            self._btn_off_effect.setOpacity(1.0)
            self._btn_on_anim.stop()
            self._btn_on_anim.setStartValue(0.1)
            self._btn_on_anim.setEndValue(1.0)
            self._btn_on_anim.start()
        else:
            self._btn_on_effect.setOpacity(1.0)
            self._btn_off_anim.stop()
            self._btn_off_anim.setStartValue(0.1)
            self._btn_off_anim.setEndValue(1.0)
            self._btn_off_anim.start()

    def set_enabled_buttons(self, enabled: bool) -> None:
        """Enable or disable both action buttons together."""
        self.btn_on.setEnabled(enabled)
        self.btn_off.setEnabled(enabled)
