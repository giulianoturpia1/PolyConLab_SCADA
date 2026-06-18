"""SensorCard widget — compact display tile for a single sensor reading."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.style import palette as col
from ui.style.anim import Fade

# ── Sizing / timing constants ─────────────────────────────────────────────────
_CARD_MIN_W = 100  # minimum card width in pixels
_CARD_MIN_H = 88  # minimum card height in pixels
_VAL_FADE_MS = 450  # value label fade-in duration on each new reading


class SensorCard(QFrame):
    """Compact card showing a title, current value and unit.

    When made interactive (PLC connected), the card acts as a toggle: clicking
    it enables or disables polling for that sensor and emits ``toggled(bool)``.
    While not interactive (disconnected), clicks are silently ignored.
    """

    # Emitted when the user clicks an interactive card to start or stop polling.
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, title: str = "SENSOR", unit: str = "") -> None:
        """Build the card layout.

        Default title and unit produce a usable placeholder in Qt Designer.
        Call :meth:`configure` after ``setupUi()`` to set the per-instance labels.
        """
        super().__init__(parent)
        self.setMinimumSize(_CARD_MIN_W, _CARD_MIN_H)
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
        self._val_fade = Fade(self._val, duration=_VAL_FADE_MS)

        self._polling_enabled: bool = False
        self._interactive: bool = False
        self._fault: bool = False  # True when the device failed the init probe
        self._apply_card_style()

    # ── Internal style ───────────────────────────────────────────────────────

    def _apply_card_style(self) -> None:
        """Rebuild the card stylesheet and cursor to reflect the current state."""
        if self._fault:
            # Init probe failed: red border.
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {col.PANEL};
                    border: 2px solid {col.RED};
                    border-radius: 8px;
                }}
            """)
        elif self._polling_enabled:
            # Active: green border signals that this sensor is being polled.
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {col.PANEL};
                    border: 1px solid {col.GREEN};
                    border-radius: 8px;
                }}
            """)
        elif self._interactive:
            # Connected but idle: dim border with a hover hint.
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {col.PANEL};
                    border: 1px solid {col.BORDER};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border-color: {col.TEXT};
                }}
            """)
        else:
            # Disconnected: plain dim border, no interaction cues.
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {col.PANEL};
                    border: 1px solid {col.BORDER};
                    border-radius: 8px;
                }}
            """)

        self.setCursor(Qt.CursorShape.PointingHandCursor if self._interactive else Qt.CursorShape.ArrowCursor)

    # ── Public API ───────────────────────────────────────────────────────────

    def configure(self, title: str, unit: str = "") -> None:
        """Override the default title and unit set in ``__init__``."""
        self._lbl_title.setText(title.upper())
        self._lbl_unit.setText(unit)

    def title(self) -> str:
        """Return the sensor label text as configured."""
        return self._lbl_title.text()

    def set_value(self, v: str, color: str = col.WHITE) -> None:
        """Update the displayed value and play a fade-in to signal the change."""
        self._val.setText(v)
        self._val.setStyleSheet(f"background:transparent;border:none;color:{color};font-size:22px;font-weight:bold;")
        self._val_fade.play(0.15, 1.0)

    @property
    def is_polling(self) -> bool:
        """True if the user has selected this card for polling."""
        return self._polling_enabled

    def set_interactive(self, enabled: bool) -> None:
        """Full connect/disconnect reset.

        Call with ``True`` when the PLC connects and ``False`` when it
        disconnects.  Disabling interaction also resets the polling and fault
        states so the card starts from a clean slate on the next connection.

        For FSM-state-based gating (e.g. block clicking in PAUSE without
        resetting the user's polling selection), use :meth:`set_clickable`.
        """
        self._interactive = enabled
        if not enabled:
            self._polling_enabled = False
            self._fault = False
        self._apply_card_style()

    def set_clickable(self, clickable: bool) -> None:
        """Allow or block click-to-toggle without resetting polling or fault state.

        Used by :class:`~ui.sensor_panel.SensorPanel` to gate interactivity
        based on the current PLC FSM state.  When *clickable* is False the card
        preserves its green border if polling was active (showing the user's
        selection) but ignores mouse clicks.
        """
        self._interactive = clickable
        self._apply_card_style()

    def set_fault(self, faulted: bool) -> None:
        """Mark or clear a hardware-init fault on this card.

        When *faulted* is True the card shows a red border and its value is set
        to ``"FALLO"`` to make the failed sensor immediately visible.
        Clearing the fault reverts to the normal idle style.
        """
        self._fault = faulted
        if faulted:
            self.set_value("FALLO", col.RED)
        self._apply_card_style()

    # ── Event handling ───────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Toggle polling on a left-click when the card is interactive."""
        if self._interactive and event.button() == Qt.MouseButton.LeftButton:
            self._polling_enabled = not self._polling_enabled
            self._apply_card_style()
            self.toggled.emit(self._polling_enabled)
        super().mousePressEvent(event)
