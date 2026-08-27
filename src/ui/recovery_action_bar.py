"""RecoveryActionBar — the recovery / runtime action buttons as one gated unit."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QAbstractButton

from ui.style.anim import ACTION_BTN_FADE_MS, Fade


class RecoveryActionBar(QObject):
    """The pause / resume / e-stop / ack / retry buttons managed together.

    Emits one signal per button (the operator's intent); the owner decides what
    each does. Enable state is set as a group via :meth:`set_permissions`, and
    the buttons fade in when the connection is established.
    """

    pause = Signal()
    resume = Signal()
    stop = Signal()
    ack = Signal()
    retry = Signal()

    def __init__(
        self,
        pause_btn: QAbstractButton,
        resume_btn: QAbstractButton,
        estop_btn: QAbstractButton,
        ack_btn: QAbstractButton,
        retry_btn: QAbstractButton,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pause = pause_btn
        self._resume = resume_btn
        self._estop = estop_btn
        self._ack = ack_btn
        self._retry = retry_btn
        self._buttons = [pause_btn, resume_btn, estop_btn, ack_btn, retry_btn]

        self._pause.clicked.connect(self.pause)
        self._resume.clicked.connect(self.resume)
        self._estop.clicked.connect(self.stop)
        self._ack.clicked.connect(self.ack)
        self._retry.clicked.connect(self.retry)

        self._fades = [Fade(btn, duration=ACTION_BTN_FADE_MS) for btn in self._buttons]

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_permissions(self, *, pause: bool, resume: bool, stop: bool, ack: bool, retry: bool) -> None:
        """Enable or disable each button for the current FSM state."""
        self._pause.setEnabled(pause)
        self._resume.setEnabled(resume)
        self._estop.setEnabled(stop)
        self._ack.setEnabled(ack)
        self._retry.setEnabled(retry)

    def fade_in(self) -> None:
        """Fade all buttons in — on connection established."""
        for fade in self._fades:
            fade.play(0.0, 1.0)

    def reset_fade(self) -> None:
        """Restore full opacity — on disconnect."""
        for fade in self._fades:
            fade.set_opacity(1.0)
