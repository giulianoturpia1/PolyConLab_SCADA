"""RecoveryActionBar — the recovery / runtime action buttons as one gated unit."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QAbstractButton

from ui.style.anim import ACTION_BTN_FADE_FROM, ACTION_BTN_FADE_MS, OPAQUE, Fade

# Labels of the combined pause/resume button, which follows the PLC state.
_PAUSE_TEXT = "Pausar"
_RESUME_TEXT = "Reanudar"


class RecoveryActionBar(QObject):
    """The pause-resume / e-stop / ack / retry / re-init buttons managed together.

    Emits one signal per operator intent; the owner decides what each does. Pause
    and resume share one button that reads "Pausar" in MANUAL and "Reanudar" in
    PAUSE. Enable state is set as a group via :meth:`set_permissions`, and the
    buttons fade in when the connection is established.
    """

    pause = Signal()
    resume = Signal()
    stop = Signal()
    ack = Signal()
    retry = Signal()
    reinit = Signal()

    def __init__(
        self,
        pause_resume_btn: QAbstractButton,
        estop_btn: QAbstractButton,
        ack_btn: QAbstractButton,
        retry_btn: QAbstractButton,
        reinit_btn: QAbstractButton,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pause_resume = pause_resume_btn
        self._resume_mode = False  # True while the combined button reads "Reanudar"
        self._estop = estop_btn
        self._ack = ack_btn
        self._retry = retry_btn
        self._reinit = reinit_btn
        self._buttons = [pause_resume_btn, estop_btn, ack_btn, retry_btn, reinit_btn]

        self._pause_resume.clicked.connect(self._on_pause_resume)
        self._estop.clicked.connect(self.stop)
        self._ack.clicked.connect(self.ack)
        self._retry.clicked.connect(self.retry)
        self._reinit.clicked.connect(self.reinit)

        self._fades = [Fade(btn, duration=ACTION_BTN_FADE_MS) for btn in self._buttons]

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_permissions(self, *, pause: bool, resume: bool, stop: bool, ack: bool, retry: bool, reinit: bool) -> None:
        """Enable or disable each button for the current FSM state.

        *pause* and *resume* drive the one combined button: it reads "Reanudar" and resumes when
        *resume* is allowed, otherwise it reads "Pausar" and is enabled only if *pause* is.
        """
        self._resume_mode = resume
        self._pause_resume.setText(_RESUME_TEXT if resume else _PAUSE_TEXT)
        self._pause_resume.setEnabled(pause or resume)
        self._estop.setEnabled(stop)
        self._ack.setEnabled(ack)
        self._retry.setEnabled(retry)
        self._reinit.setEnabled(reinit)

    # ── Internals ────────────────────────────────────────────────────────────

    def _on_pause_resume(self) -> None:
        """Emit the intent the button showed when clicked, then hold it until the next state update.

        Disabling it stops a quick double-click from pausing and immediately resuming; the next
        :meth:`set_permissions` (every STATE? poll) re-enables it with the label for the new state.
        """
        self._pause_resume.setEnabled(False)
        if self._resume_mode:
            self.resume.emit()
        else:
            self.pause.emit()

    def fade_in(self) -> None:
        """Fade all buttons in — on connection established."""
        for fade in self._fades:
            fade.play(ACTION_BTN_FADE_FROM)

    def reset_fade(self) -> None:
        """Restore full opacity — on disconnect."""
        for fade in self._fades:
            fade.set_opacity(OPAQUE)
