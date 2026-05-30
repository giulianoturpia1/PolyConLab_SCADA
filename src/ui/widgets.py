from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
from ui.anim import Fade

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


class SensorCard(QFrame):
    """Compact card showing a title, current value and unit."""

    def __init__(self, parent: QWidget | None = None, title: str = "SENSOR", unit: str = "") -> None:
        """Build the card layout.

        Default title and unit produce a usable placeholder in Qt Designer.
        Call configure() after setupUi() to set the per-instance labels.
        """
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

        # Fades the value label in whenever set_value() is called.
        self._val_fade = Fade(self._val, duration=450)

    def configure(self, title: str, unit: str = "") -> None:
        """Override the default title and unit set in __init__."""
        self._lbl_title.setText(title.upper())
        self._lbl_unit.setText(unit)

    def set_value(self, v: str, color: str = col.WHITE) -> None:
        """Update the displayed value and play a fade-in to signal the change to the operator."""
        self._val.setText(v)
        self._val.setStyleSheet(f"background:transparent;border:none;color:{color};font-size:22px;font-weight:bold;")
        self._val_fade.play(0.15, 1.0)


class ActuatorRow(QWidget):
    """Row with an LED indicator, label and two buttons (on / off).

    Emits ``activated(bool)`` when the user clicks a button (True for on/open,
    False for off/close). The row does not change its own appearance on click;
    the owner sends the command and calls :meth:`set_active` to reflect state.
    """

    activated = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "Actuador",
        on_text: str = "ON",
        off_text: str = "OFF",
    ) -> None:
        """Build the row layout.

        Default label and button texts produce a usable placeholder in Qt Designer.
        Call configure() after setupUi() to set the per-instance labels.
        """
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

        # Emit user intent; the owner decides what command to send and when to
        # update the visual state (see set_active).
        self.btn_on.clicked.connect(lambda: self.activated.emit(True))
        self.btn_off.clicked.connect(lambda: self.activated.emit(False))

        # Flash whichever button confirms the new state.
        self._btn_on_fade = Fade(self.btn_on, duration=400)
        self._btn_off_fade = Fade(self.btn_off, duration=400)

    def configure(self, label: str, on_text: str = "ON", off_text: str = "OFF") -> None:
        """Override the default label and button texts set in __init__."""
        self._lbl.setText(label)
        self.btn_on.setText(on_text)
        self.btn_off.setText(off_text)

    def label(self) -> str:
        """Return the row's display label."""
        return self._lbl.text()

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
            self._btn_off_fade.set_opacity(1.0)
            self._btn_on_fade.play(0.1, 1.0)
        else:
            self._btn_on_fade.set_opacity(1.0)
            self._btn_off_fade.play(0.1, 1.0)

    def set_enabled_buttons(self, enabled: bool) -> None:
        """Enable or disable both action buttons together."""
        self.btn_on.setEnabled(enabled)
        self.btn_off.setEnabled(enabled)
