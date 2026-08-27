"""StateLabel — owns the FSM state indicator label: text, colour, and fade."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from ui.style import palette as col
from ui.style.anim import Fade, STATE_LABEL_FADE_MS

# ── State label stylesheet values ─────────────────────────────────────────────
_FONT_PX = 18
_BORDER_RADIUS_PX = 6
_PADDING = "14px 8px"

# Placeholder shown while disconnected / before the first state is known.
_PLACEHOLDER = "--"


class StateLabel:
    """Presentation for the promoted ``lbl_state`` QLabel.

    Receives the label created by ``Ui_MainWindow`` (the .ui owns the layout);
    this class owns only the presentation — colour lookup by state, the
    stylesheet, and the fade played on every change.
    """

    def __init__(self, label: QLabel) -> None:
        self._label = label
        self._fade = Fade(label, duration=STATE_LABEL_FADE_MS)

    def set_state(self, raw: str) -> None:
        """Set the label to *raw*, colour it by state, and fade it in."""
        color = col.STATE_COLOR.get(raw, col.GRAY)
        self._label.setText(raw)
        self._label.setStyleSheet(
            f"color:{color};background:{col.PANEL};border:2px solid {color};"
            f"border-radius:{_BORDER_RADIUS_PX}px;font-size:{_FONT_PX}px;"
            f"font-weight:bold;padding:{_PADDING};"
        )
        self._fade.play(0.2, 1.0)

    def reset(self) -> None:
        """Reset to the disconnected placeholder ("--")."""
        self.set_state(_PLACEHOLDER)
