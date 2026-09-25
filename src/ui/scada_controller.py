"""ScadaController — the SCADA-side brain: lifecycle, state machine, gating, reconciliation.

Owns the compound SCADA state and drives the view collaborators (the panels and
the state label) from the PLC's reported state — never from an assumption.
Connection-lifecycle chrome that lives on MainWindow's own header widgets (the
connection label and the connect button) is surfaced through the ``view_*``
signals so the window paints it; every other collaborator the controller drives
directly.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from comms.handshake import PlcHandshake
from comms.plc_client import PlcClient
from comms.protocol import Evt
from models import Sensor
from ui.actuator_panel import ActuatorPanel
from ui.recovery_action_bar import RecoveryActionBar
from ui.scada_state import ScadaState, STATE_CONTROLS, from_plc
from ui.sensor_panel import SensorPanel
from ui.temperature_control import TemperatureControl
from ui.widgets.state_label import StateLabel

# What to tell the operator when the PLC leaves PAUSE.  Resuming returns to
# MANUAL only if the pause interrupted MANUAL; any other pause resumes into
# CHECKUP, where the sensors are re-verified before actuators are re-enabled.
_RESUME_MESSAGE: dict[ScadaState, str] = {
    ScadaState.MANUAL: "Sistema reanudado en MANUAL.",
    ScadaState.CHECKUP: (
        "La pausa no provino de MANUAL: el PLC vuelve a CHEQUEO y se re-verifican "
        "los sensores antes de habilitar los actuadores."
    ),
}


class ScadaController(QObject):
    """Coordinates the PLC session and the view: lifecycle, FSM, gating, reconciliation."""

    #: Human-readable message to surface in the log window.
    log = Signal(str)
    #: A connection attempt has started — the window shows the "cancel" affordance.
    view_connecting = Signal()
    #: The PLC is connected — carries (host, port) for the connection indicator.
    view_connected = Signal(str, int)
    #: The session is down — the window shows the disconnected baseline.
    view_disconnected = Signal()

    def __init__(
        self,
        plc: PlcClient,
        init_seq: PlcHandshake,
        sensor_panel: SensorPanel,
        actuator_panel: ActuatorPanel,
        temp_control: TemperatureControl,
        recovery_bar: RecoveryActionBar,
        state_label: StateLabel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._plc = plc
        self._init_seq = init_seq
        self._sensor_panel = sensor_panel
        self._actuator_panel = actuator_panel
        self._temp_control = temp_control
        self._recovery_bar = recovery_bar
        self._state_label = state_label

        self._scada_state = ScadaState.DISCONNECTED
        self._host = ""
        self._port = 0
        self._faulted: set[Sensor] = set()  # sensors that failed the init probe

        # ── Connection lifecycle ────────────────────────────────────────────────
        self._plc.connecting.connect(self._on_tcp_connecting)
        self._plc.connected.connect(self._on_tcp_connected)
        self._plc.disconnected.connect(self._on_tcp_disconnected)
        self._plc.error.connect(self._on_tcp_error)

        # ── State polling ───────────────────────────────────────────────────────
        self._plc.state_received.connect(self._on_state_polled)

        # ── Per-sensor re-init results (the PLC's reply to a SYST:REINIT command).
        self._plc.sensor_reinit_result.connect(self._on_sensor_reinit_result)

        # ── Init sequence ───────────────────────────────────────────────────────
        self._init_seq.progress.connect(self.log)
        self._init_seq.sensor_result.connect(self._on_init_sensor_result)
        self._init_seq.finished.connect(self._on_init_finished)

        # ── Recovery / runtime actions (the bar emits intent; the controller acts).
        self._recovery_bar.pause.connect(self._on_pause)
        self._recovery_bar.resume.connect(self._on_resume)
        self._recovery_bar.stop.connect(self._on_stop)
        self._recovery_bar.ack.connect(self._on_ack)
        self._recovery_bar.retry.connect(self._on_retry)
        self._recovery_bar.reinit.connect(self._on_reinit)

    # ── Public API ─────────────────────────────────────────────────────────────

    def toggle_connection(self, host: str, port: int) -> None:
        """Connect, cancel a pending attempt, or disconnect — per the current state."""
        if self._plc.is_connected:
            # Request a safe state before closing.  Qt flushes the write buffer
            # before the TCP FIN, so the FW receives PAUSE even though
            # disconnect_from() is called immediately after.
            self._plc.send_event(Evt.PAUSE)
            self._plc.disconnect_from()
        elif self._plc.is_connecting:
            self._plc.abort()
            self.log.emit("Intento de conexión cancelado.")
            self._reset()
        else:
            self._host = host
            self._port = port
            self.log.emit(f"Conectando a {host}:{port}...")
            self._plc.connect_to(host, port)

    # ── Connection lifecycle slots ──────────────────────────────────────────────

    def _on_tcp_connecting(self) -> None:
        self._transition(ScadaState.CONNECTING)
        self.view_connecting.emit()

    def _on_tcp_connected(self) -> None:
        """Announce the connection and start the initialization handshake.

        Interactivity is NOT enabled here — it is gated by _apply_state_gating and
        only unlocked when the PLC confirms MANUAL.
        """
        self.view_connected.emit(self._host, self._port)
        self._recovery_bar.fade_in()
        self.log.emit(f"Conectado a {self._host}:{self._port}.")
        self._transition(ScadaState.INITIALIZING)
        self._init_seq.start()

    def _on_tcp_disconnected(self) -> None:
        self._init_seq.abort()
        self._reset()
        self.log.emit("Desconectado del PLC.")

    def _on_tcp_error(self, msg: str) -> None:
        self._init_seq.abort()
        self._reset()
        self.log.emit(f"Error de conexión: {msg}")

    # ── Init sequence slots ───────────────────────────────────────────────────────

    def _on_init_sensor_result(self, sensor: Sensor, ok: bool) -> None:
        """Mark a probed sensor's card and log the failing ones."""
        self._sensor_panel.mark_init_fault(sensor, ok)
        if ok:
            self._faulted.discard(sensor)
        else:
            self._faulted.add(sensor)
            self.log.emit(f"  Sensor con fallo: {self._sensor_panel.card_title(sensor)}")

    def _on_init_finished(self, success: bool, msg: str) -> None:
        """React to the end of the initialization handshake."""
        if success:
            self.log.emit(f"Inicialización completa: {msg}")
        else:
            self.log.emit(f"Error de inicialización: {msg}")

        # Always start the periodic STATE? poll — even after a failed init — so
        # the SCADA tracks state changes during fault recovery.
        self._plc.start_state_polling()
        # Query state once immediately: the resulting transition reconciles all
        # controls from the PLC (see _transition), so this works for both the
        # MANUAL (success) and fault (failure) paths without a special case.
        self._plc.query_state()

    # ── State polling slot ────────────────────────────────────────────────────────

    def _on_state_polled(self, raw: str) -> None:
        """Handle a STATE? reply from the init sequence or the periodic poll.

        Explains a resume in the log — the PLC may also unpause on its own when
        the link comes back, so the operator sees why the state moved even
        without pressing anything.  If the PLC is in CHECKUP and no handshake is
        in progress, start one automatically (e.g. an ACK FAULT that returned to
        CHECKUP, or any unexpected CHECKUP re-entry).
        """
        self._state_label.set_state(raw)
        plc_state = from_plc(raw)
        previous = self._scada_state
        self._transition(plc_state)
        if plc_state == previous and STATE_CONTROLS[plc_state].actuator_queries:
            # Re-read the actuators with every state poll: the FW also switches them on its own
            # (temperature control, the temperature limit, safe outputs), and the rows must follow.
            self._actuator_panel.reconcile()
        if previous == ScadaState.PAUSE and plc_state != ScadaState.PAUSE:
            self.log.emit(_RESUME_MESSAGE.get(plc_state, f"El PLC salió de PAUSE al estado «{raw}»."))
        if plc_state == ScadaState.CHECKUP and not self._init_seq.is_running:
            # The controller only notices the drift back to CHECKUP; the handshake
            # itself decides how to react.
            self._init_seq.reprobe_sensors()

    # ── Recovery / runtime actions ────────────────────────────────────────────────

    def _on_pause(self) -> None:
        self._plc.send_event(Evt.PAUSE)

    def _on_resume(self) -> None:
        self.log.emit("Reanudando el sistema...")
        self._plc.send_event(Evt.UNPAUSE)

    def _on_stop(self) -> None:
        """Send a graceful shutdown and disconnect.

        ``EVT:SHUTDOWN`` (kShutdown) is the correct operator stop: the FW turns
        off all actuators and closes valves via ShutdownState, then returns to
        STARTUP automatically.  ``EVT:STOP`` (kEStop) is intentionally not used —
        it is only handled in SoftErrorState; ManualState and PauseState ignore
        it, so it is a no-op from the states where this button is active.  After
        SHUTDOWN the SCADA disconnects so the operator must reconnect explicitly.
        """
        self._plc.send_event(Evt.SHUTDOWN)
        self._plc.disconnect_from()

    def _on_ack(self) -> None:
        """Accept the fault and reach MANUAL without re-probing sensors.

        :meth:`PlcHandshake.skip_probe` exits SOFT ERROR if necessary and
        sends EVT:SCADA OK + EVT:SENSORS OK directly — bypassing the probe — so
        the PLC reaches MANUAL even if some sensors are permanently offline.
        """
        self._sensor_panel.clear_faults()
        self._faulted.clear()
        self._init_seq.skip_probe()

    def _on_retry(self) -> None:
        """Request a full sensor re-probe and re-run the init handshake."""
        self._sensor_panel.clear_faults()
        self._faulted.clear()
        self._init_seq.reprobe_sensors()

    def _on_reinit(self) -> None:
        """Re-initialise every currently faulted sensor on the PLC. No state Change occurs.

        Fires one SYST:REINIT command per faulted sensor over a snapshot of the
        set (the results mutate it as they arrive).  Re-init is a command, not a
        state event: cards clear as sensors recover, but the PLC stays in SOFT
        ERROR — the operator then uses Reintentar Chequeo or Aceptar to
        leave it.
        """
        if not self._faulted:
            self.log.emit("No hay sensores en falla para reinicializar.")
            return
        for sensor in sorted(self._faulted, key=lambda s: s.value):
            self.log.emit(f"Reinicializando sensor: {self._sensor_panel.card_title(sensor)}...")
            self._plc.reinit_sensor(sensor)

    def _on_sensor_reinit_result(self, sensor: Sensor, ok: bool) -> None:
        """Clear the card and drop the sensor on success; keep the fault and log on failure."""
        title = self._sensor_panel.card_title(sensor)
        if ok:
            self._faulted.discard(sensor)
            self._sensor_panel.clear_fault(sensor)
            self.log.emit(f"  Sensor reinicializado: {title}")
        else:
            self.log.emit(f"  Falló la reinicialización: {title}")

    # ── State machine ─────────────────────────────────────────────────────────────

    def _transition(self, new_state: ScadaState) -> None:
        """Move to a new SCADA state, apply control permissions, and reconcile on change.

        On entry to MANUAL every control is re-synced from the PLC (never
        assumed); on exit from MANUAL the temperature-control indicator is
        cleared, because the FW disables that control outside MANUAL.
        """
        previous = self._scada_state
        self._scada_state = new_state
        self._apply_state_gating()

        if new_state == previous:
            return
        if STATE_CONTROLS[new_state].actuator_queries:
            self._reconcile_controls()
        else:
            # The FW rejects actuator queries here: show unknown rather than a stale state.
            self._actuator_panel.reset()
        if previous == ScadaState.MANUAL:
            self._temp_control.clear()

    def _reconcile_controls(self) -> None:
        """Re-sync every control from the PLC on entry to MANUAL.

        Delegates to the panels, which repaint only from the PLC's replies, so
        the UI reflects the PLC and never a SCADA-side assumption.
        """
        self._actuator_panel.reconcile()

    def _apply_state_gating(self) -> None:
        """Enable or disable controls by looking up the current state in STATE_CONTROLS."""
        c = STATE_CONTROLS[self._scada_state]
        self._sensor_panel.set_polling_allowed(c.sensors)
        self._actuator_panel.set_enabled(c.actuators)
        self._temp_control.set_enabled(c.actuators)
        self._recovery_bar.set_permissions(pause=c.pause, resume=c.resume, stop=c.stop, ack=c.ack, retry=c.retry, reinit=c.reinit)

    def _reset(self) -> None:
        """Reset all connection-dependent state and view to the disconnected baseline."""
        self._faulted.clear()
        self._state_label.reset()
        self._transition(ScadaState.DISCONNECTED)
        self._sensor_panel.reset()
        self._sensor_panel.set_interactive(False)
        self._actuator_panel.reset()
        self._temp_control.clear()
        self._recovery_bar.reset_fade()
        self.view_disconnected.emit()
