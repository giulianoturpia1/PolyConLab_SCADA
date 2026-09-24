"""Drives the PLC connect handshake after a TCP connection is established, and re-probes
sensors and drives fault recovery for the lifetime of that connection.

Expected wire flow::

    SCADA connects
    → STATE? → "STARTUP"  →  EVT:INIT OK  → (settle)
    → STATE? → "CHECKUP"  →  probe all sensors (MEAS:… queries)
                              → all OK  →  EVT:SCADA OK + EVT:SENSORS OK  → (settle)
                              → any fault  →  EVT:FAULT RECOVERABLE
    → STATE? → "MANUAL"   →  finished(True)

If the PLC is already in CHECKUP or MANUAL when we connect, the corresponding
earlier steps are skipped.  Call :meth:`reprobe_sensors` after the operator
requests a retry — it sends RETRY CHECKUP itself and re-runs the sensor probe,
without tearing down the TCP connection.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from comms.plc_client import PlcClient
from comms.protocol import Evt, State
from config.polling import HANDSHAKE_PROBE_TIMEOUT_MS, HANDSHAKE_SETTLE_MS
from models import Sensor

# ── Human-readable sensor labels (Spanish UI) ────────────────────────────────

_SENSOR_LABEL: dict[Sensor, str] = {
    Sensor.TEMP_IN: "T. Entrada",
    Sensor.TEMP_OUT: "T. Salida",
    Sensor.TEMP_BATH: "T. Camisa",
    Sensor.TEMP_MIX: "T. Mezcla",
    Sensor.FLOW: "Caudal",
    Sensor.LEVEL: "Nivel",
}


class PlcHandshake(QObject):
    """Drives the PLC connect handshake, sensor re-probing, and fault-recovery flows.

    Create one instance per :class:`~comms.plc_client.PlcClient` and reuse it
    across sessions by calling :meth:`start` after every TCP connect.
    """

    #: Human-readable status update — forward to the log window or a label.
    progress = Signal(str)

    #: Per-sensor probe result emitted during CHECKUP: ``(Sensor, passed)``.
    sensor_result = Signal(object, bool)

    #: Emitted when the sequence completes: ``(success, human_readable_message)``.
    finished = Signal(bool, str)

    def __init__(self, plc: PlcClient, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._plc = plc
        self._running = False

        self._probe_timer = QTimer(self)
        self._probe_timer.setSingleShot(True)
        self._probe_timer.setInterval(HANDSHAKE_PROBE_TIMEOUT_MS)
        self._probe_timer.timeout.connect(self._on_probe_timeout)

        # Live STATE? listener, if any, plus an epoch that invalidates in-flight
        # work (pending listener, settle timers) when a sequence is cancelled.
        self._state_slot: Callable[[str], None] | None = None
        self._epoch = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """True while a handshake sequence is in progress."""
        return self._running

    def start(self) -> None:
        """Begin the full handshake from a STATE? inspection.

        No-op if already running.  Safe to call every time the TCP socket
        connects — the sequence is self-contained.
        """
        if self._running:
            return
        self._running = True
        self.progress.emit("Conectado — verificando estado del sistema...")
        self._query_state(self._on_initial_state)

    def reprobe_sensors(self) -> None:
        """Ask the PLC to re-run the sensor checkup, then re-probe.

        Sends EVT:RETRY CHECKUP itself and confirms the PLC reached CHECKUP before probing, so the
        whole retry flow has a single owner — the caller only expresses the intent. No-op if a
        sequence is already running.
        """
        if self._running:
            return
        self._running = True
        self.progress.emit("Re-verificando sensores...")
        self._plc.send_event(Evt.RETRY_CHECKUP)
        self._query_state(self._on_post_init_state)

    def skip_probe(self) -> None:
        """Skip the sensor probe and complete the handshake unconditionally.

        Used when the operator acknowledges known-failed sensors and wants to
        reach MANUAL anyway.  Handles two starting points:

        * **SOFT ERROR** — sends EVT:ACK FAULT + EVT:CONDITION CLEARED to exit
          back to CHECKUP, then sends EVT:SCADA OK + EVT:SENSORS OK.
        * **CHECKUP** — sends EVT:SCADA OK + EVT:SENSORS OK immediately.

        In both cases the PLC ends up in MANUAL.  Broken sensor cards are left
        red by the caller so the operator can see which devices are unavailable.
        """
        if self._running:
            return
        self._running = True
        self.progress.emit("Accediendo a MANUAL sin re-verificar sensores...")
        self._query_state(self._on_force_state)

    def abort(self) -> None:
        """Cancel any in-progress sequence (e.g. on TCP disconnect).

        Drops the pending STATE? listener and bumps the epoch so a reply or a
        settle timer belonging to the cancelled run is ignored instead of
        starting a second, parallel handshake on the next connection.
        """
        self._probe_timer.stop()
        self._disconnect_state_slot()
        self._epoch += 1
        self._running = False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _disconnect_state_slot(self) -> None:
        """Drop the pending STATE? listener, if any. Idempotent."""
        if self._state_slot is None:
            return
        try:
            self._plc.state_received.disconnect(self._state_slot)
        except RuntimeError:
            pass  # already disconnected (e.g. object deleted)
        self._state_slot = None

    def _query_state(self, callback: Callable[[str], None]) -> None:
        """Send STATE? and deliver the single reply to *callback*.

        At most one listener is connected at a time and it is dropped as soon as
        it fires, so aborted sequences cannot leave slots stacked on the signal.
        """
        self._disconnect_state_slot()
        epoch = self._epoch

        def one_shot(state: str) -> None:
            self._disconnect_state_slot()
            if epoch != self._epoch:
                return  # the sequence was cancelled while this query was in flight
            callback(state)

        self._state_slot = one_shot
        self._plc.state_received.connect(one_shot)

        if not self._plc.query_state():
            self._disconnect_state_slot()
            self._finish(False, "Sin respuesta del PLC al consultar estado.")

    def _defer_query(self, callback: Callable[[str], None]) -> None:
        """Re-query STATE? after the settle delay, unless the sequence was cancelled."""
        epoch = self._epoch

        def go() -> None:
            if epoch == self._epoch:
                self._query_state(callback)

        QTimer.singleShot(HANDSHAKE_SETTLE_MS, go)

    # ── State callbacks ────────────────────────────────────────────────────────

    def _on_initial_state(self, state: str) -> None:
        """React to the first STATE? reply after connecting."""
        if state == State.STARTUP:
            # Normal boot path: PLC waiting for the SCADA to kick off the checkup.
            self.progress.emit("PLC en inicio — comenzando chequeo del sistema...")
            self._plc.send_event(Evt.INIT_OK)
            self._defer_query(self._on_post_init_state)

        elif state == State.CHECKUP:
            # PLC was already in CHECKUP (e.g. SCADA reconnected during init).
            self._begin_probe()

        elif state == State.MANUAL:
            # Common reconnect path: SCADA closed the TCP session but the
            # Ethernet cable stayed connected, so the PLC stayed in MANUAL.
            self._finish(True, "Sistema ya operativo.")

        elif state == State.PAUSE:
            # The PLC is suspended.  Most likely the operator paused the system
            # before the SCADA disconnected.  The FW will also enter PAUSE
            # automatically if the Ethernet cable is pulled and then reinserted
            # while the SCADA is not connected — but in that case the FW
            # auto-resumes to the previous state once the link comes back up,
            # so the SCADA would see MANUAL instead.
            # Action: surface the Resume button; the operator decides when to continue.
            self._finish(False, "PLC en PAUSE — use el botón Reanudar para continuar.")

        elif state in (State.SOFT_ERROR, State.HARD_ERROR):
            # PLC was in an error state when we connected (e.g. a sensor failed
            # on a previous boot and the SCADA was restarted).
            self._finish(False, f"PLC en estado de falla «{state}». Use los botones de recuperación.")

        else:
            self._finish(False, f"Estado inesperado al conectar: «{state}»")

    def _on_post_init_state(self, state: str) -> None:
        """React to the STATE? reply after the PLC was told to begin checkup."""
        if state == State.CHECKUP:
            self._begin_probe()
        elif state == State.MANUAL:
            self._finish(True, "Sistema listo.")
        else:
            self._finish(False, f"El PLC no alcanzó CHEQUEO (estado actual: «{state}»)")

    def _begin_probe(self) -> None:
        """Send all sensor queries and arm the overall probe timeout."""
        self.progress.emit("Verificando sensores del sistema...")
        self._probe_timer.start()
        if not self._plc.probe_sensors(self._on_probe_done):
            self._probe_timer.stop()
            self._finish(False, "No se pudo iniciar la verificación de sensores.")

    def _on_probe_timeout(self) -> None:
        self._finish(False, "Tiempo de espera agotado verificando sensores.")

    def _on_probe_done(self, results: dict[Sensor, bool]) -> None:
        """Evaluate sensor probe results and complete the handshake accordingly.

        Replies that arrive after the probe timed out belong to a sequence that
        already finished; acting on them would send the OK events and emit a
        second ``finished`` for a run the controller has moved on from.
        """
        if not self._running:
            return

        self._probe_timer.stop()

        for sensor, ok in results.items():
            self.sensor_result.emit(sensor, ok)

        failed = [_SENSOR_LABEL[s] for s, ok in results.items() if not ok]

        if failed:
            names = ", ".join(failed)
            self.progress.emit(f"Sensor(es) sin respuesta: {names}")
            self._plc.send_event(Evt.FAULT_RECOVERABLE)
            self._finish(False, f"Fallo de sensor(es): {names}")
        else:
            self.progress.emit("Sensores OK — habilitando sistema...")
            self._plc.send_event(Evt.SCADA_OK)
            self._plc.send_event(Evt.SENSORS_OK)
            self._defer_query(self._on_final_state)

    def _on_final_state(self, state: str) -> None:
        """Confirm the PLC reached MANUAL after the successful handshake."""
        if state == State.MANUAL:
            self._finish(True, "Sistema listo.")
        else:
            self._finish(False, f"El PLC no alcanzó MANUAL (estado actual: «{state}»)")

    # ── Force-proceed callbacks ────────────────────────────────────────────────

    def _on_force_state(self, state: str) -> None:
        """Decide how to reach CHECKUP based on the current state."""
        if state == State.MANUAL:
            self._finish(True, "Sistema ya en MANUAL.")
        elif state == State.CHECKUP:
            self._send_ok_events()
        elif state == State.SOFT_ERROR:
            self.progress.emit("Reconociendo error y continuando...")
            self._plc.send_event(Evt.ACK_FAULT)
            self._plc.send_event(Evt.CONDITION_CLEARED)
            self._defer_query(self._on_force_checkup_state)
        else:
            self._finish(False, f"No se puede continuar desde estado «{state}»")

    def _on_force_checkup_state(self, state: str) -> None:
        """Confirm CHECKUP was reached after ACK, then send the OK events."""
        if state == State.CHECKUP:
            self._send_ok_events()
        elif state == State.MANUAL:
            self._finish(True, "Sistema listo.")
        else:
            self._finish(False, f"Estado inesperado tras reconocimiento: «{state}»")

    def _send_ok_events(self) -> None:
        """Send SCADA OK + SENSORS OK and wait for the MANUAL confirmation."""
        self.progress.emit("Completando acceso a MANUAL sin re-verificar sensores...")
        self._plc.send_event(Evt.SCADA_OK)
        self._plc.send_event(Evt.SENSORS_OK)
        self._defer_query(self._on_final_state)

    # ── Finish ─────────────────────────────────────────────────────────────────

    def _finish(self, success: bool, msg: str) -> None:
        self._disconnect_state_slot()
        self._epoch += 1
        self._running = False
        self.finished.emit(success, msg)
