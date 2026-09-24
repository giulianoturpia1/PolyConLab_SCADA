"""StateLabel — owns the FSM state indicator label: text, colour, and fade."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from ui.style import metrics as m
from ui.style import palette as col
from ui.style.anim import Fade, STATE_LABEL_FADE_MS

# ── State label stylesheet values ─────────────────────────────────────────────

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
        self._current: str | None = None  # last painted state; skip redundant repaints

    def set_state(self, raw: str) -> None:
        """Set the label to *raw*, colour it by state, and fade it in.

        No-op when *raw* already matches the painted state, so the periodic
        STATE? poll does not replay the fade every cycle when nothing changed.
        """
        if raw == self._current:
            return
        self._current = raw
        color = col.STATE_COLOR.get(raw, col.GRAY)
        self._label.setText(raw)
        self._label.setStyleSheet(
            f"color:{color};background:{col.PANEL};border:2px solid {color};"
            f"border-radius:{m.STATE_LABEL_RADIUS_PX}px;font-size:{m.STATE_LABEL_FONT_PX}px;"
            f"font-weight:bold;padding:{m.STATE_LABEL_PADDING};"
        )
        self._fade.play(0.2, 1.0)

    def reset(self) -> None:
        """Reset to the disconnected placeholder ("--")."""
        self.set_state(_PLACEHOLDER)
