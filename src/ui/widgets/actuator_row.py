"""ActuatorRow widget — label + ON/OFF button pair for a single actuator."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from ui.style import metrics as m
from ui.style import palette as col
from ui.style.anim import ACTUATOR_BTN_FADE_MS, Fade

# ── Sizing / timing constants ─────────────────────────────────────────────────

# ── Button style helpers ──────────────────────────────────────────────────────
# Full selector blocks ensure :hover rules are not overridden by the global
# stylesheet when setStyleSheet() is called per-widget.

_BTN_TMPL = """
    QPushButton {{
        border-radius: 4px; font-size: 12px; padding: 4px 0;
        border: 1px solid {border}; background: {bg}; color: {fg};
    }}
    QPushButton:hover {{
        background: {hover_bg}; border-color: {hover_border};
    }}
"""


def _btn_style(active: bool) -> str:
    """Return the stylesheet for an ON button in its active or inactive state."""
    if active:
        return _BTN_TMPL.format(
            border=col.ACTIVE,
            bg=col.ACTIVE,
            fg=col.BG,
            hover_bg=col.ACTIVE_HOVER,
            hover_border=col.ACTIVE_HOVER,
        )
    return _BTN_TMPL.format(
        border=col.BORDER,
        bg=col.PANEL,
        fg=col.TEXT,
        hover_bg=col.PANEL_HOVER,
        hover_border=col.TEXT,
    )


def _btn_style_off(active: bool) -> str:
    """Return the stylesheet for an OFF button (highlighted when the row is inactive)."""
    if not active:
        return _BTN_TMPL.format(
            border=col.GRAY,
            bg=col.GRAY,
            fg=col.BG,
            hover_bg=col.GRAY_HOVER,
            hover_border=col.GRAY_HOVER,
        )
    return _BTN_TMPL.format(
        border=col.BORDER,
        bg=col.PANEL,
        fg=col.TEXT,
        hover_bg=col.PANEL_HOVER,
        hover_border=col.TEXT,
    )


class ActuatorRow(QWidget):
    """Row with a label and two buttons (on / off) for a single actuator.

    Emits ``activated(bool)`` when the user clicks a button (True for on/open,
    False for off/close).  The row does not change its own appearance on click;
    the owner sends the command and calls :meth:`set_active` once the PLC
    confirms the new state.
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
        Call :meth:`configure` after ``setupUi()`` to set the per-instance labels.
        """
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(8)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{col.WHITE};font-size:12px;")
        self._lbl.setMinimumWidth(m.ACTUATOR_LBL_MIN_WIDTH_PX)

        self.btn_on = QPushButton(on_text)
        self.btn_on.setObjectName("btn_on")
        self.btn_on.setFixedWidth(m.ACTUATOR_BTN_WIDTH_PX)
        self.btn_on.setEnabled(False)
        self.btn_on.setStyleSheet(_btn_style(False))

        self.btn_off = QPushButton(off_text)
        self.btn_off.setFixedWidth(m.ACTUATOR_BTN_WIDTH_PX)
        self.btn_off.setEnabled(False)
        self.btn_off.setStyleSheet(_btn_style_off(False))

        lay.addWidget(self._lbl, stretch=1)
        lay.addWidget(self.btn_on)
        lay.addWidget(self.btn_off)

        self.btn_on.clicked.connect(lambda: self.activated.emit(True))
        self.btn_off.clicked.connect(lambda: self.activated.emit(False))

        # Flash whichever button confirms the new state.
        self._btn_on_fade = Fade(self.btn_on, duration=ACTUATOR_BTN_FADE_MS)
        self._btn_off_fade = Fade(self.btn_off, duration=ACTUATOR_BTN_FADE_MS)

        # Last state painted: True/False once the PLC confirmed one, None while unknown.
        self._state: bool | None = None

    def configure(self, label: str, on_text: str = "ON", off_text: str = "OFF") -> None:
        """Override the default label and button texts set in ``__init__``."""
        self._lbl.setText(label)
        self.btn_on.setText(on_text)
        self.btn_off.setText(off_text)

    def label(self) -> str:
        """Return the row's display label."""
        return self._lbl.text()

    def set_active(self, active: bool) -> None:
        """Transition the row to ON or OFF state.

        Applies persistent selected/unselected styling to both buttons, then
        fades in the button that confirmed the new state. A repeat of the state
        already shown (the periodic re-query) changes nothing, so it does not flash.
        """
        if self._state is active:
            return
        self._state = active
        self.btn_on.setStyleSheet(_btn_style(active))
        self.btn_off.setStyleSheet(_btn_style_off(active))

        if active:
            self._btn_off_fade.set_opacity(1.0)
            self._btn_on_fade.play(0.1, 1.0)
        else:
            self._btn_on_fade.set_opacity(1.0)
            self._btn_off_fade.play(0.1, 1.0)

    def set_unknown(self) -> None:
        """Show that the PLC's state is unknown: neither button highlighted."""
        self._state = None
        self.btn_on.setStyleSheet(_btn_style(False))
        self.btn_off.setStyleSheet(_btn_style_off(True))

    def set_enabled_buttons(self, enabled: bool) -> None:
        """Enable or disable both action buttons together."""
        self.btn_on.setEnabled(enabled)
        self.btn_off.setEnabled(enabled)
