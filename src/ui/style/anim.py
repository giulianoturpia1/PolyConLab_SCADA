"""Small opacity-fade helper to remove the repeated effect+animation boilerplate.

Each :class:`Fade` owns a ``QGraphicsOpacityEffect`` attached to a widget and a
``QPropertyAnimation`` driving its opacity. Call :meth:`play` to fade in on an
event, or :meth:`set_opacity` to snap to a value without animating.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

# ── Named fade durations used across the main window ─────────────────────────
STATE_LABEL_FADE_MS = 400   # FSM state label fade on each state change
ACTION_BTN_FADE_MS = 500    # action button group fade-in on connect
ACTUATOR_BTN_FADE_MS = 400  # actuator ON/OFF button confirmation flash
SENSOR_VALUE_FADE_MS = 450  # sensor card value fade-in on each new reading


class Fade:
    """Opacity fade-in controller bound to a single widget."""

    def __init__(self, widget: QWidget, duration: int = 400) -> None:
        """Attach an opacity effect + animation to ``widget`` (starts fully opaque)."""
        self._effect = QGraphicsOpacityEffect(widget)
        self._effect.setOpacity(1.0)
        widget.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", widget)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def play(self, start: float = 0.1, end: float = 1.0) -> None:
        """Restart the fade from ``start`` opacity to ``end``."""
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def set_opacity(self, value: float) -> None:
        """Stop any running animation and snap to a fixed opacity."""
        self._anim.stop()
        self._effect.setOpacity(value)
