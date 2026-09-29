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

# ── Opacity each fade starts from (every fade ends fully opaque) ─────────────
OPAQUE = 1.0
STATE_LABEL_FADE_FROM = 0.2
ACTION_BTN_FADE_FROM = 0.0
ACTUATOR_BTN_FADE_FROM = 0.1
SENSOR_VALUE_FADE_FROM = 0.15


class Fade:
    """Opacity fade-in controller bound to a single widget."""

    def __init__(self, widget: QWidget, duration: int) -> None:
        """Attach an opacity effect + animation to ``widget`` (starts fully opaque)."""
        self._effect = QGraphicsOpacityEffect(widget)
        self._effect.setOpacity(OPAQUE)
        widget.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", widget)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def play(self, start: float, end: float = OPAQUE) -> None:
        """Restart the fade from ``start`` opacity to ``end``."""
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def set_opacity(self, value: float) -> None:
        """Stop any running animation and snap to a fixed opacity."""
        self._anim.stop()
        self._effect.setOpacity(value)
