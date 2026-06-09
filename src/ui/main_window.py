from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow

from comms.init_sequence import InitSequence
from comms.plc_client import PlcClient
from comms.protocol import Device, Evt, Sensor
from ui import palette as col
from ui.actuator_row import ActuatorRow
from ui.anim import Fade
from ui.log_window import LogWindow
from ui.main_window_ui import Ui_MainWindow
from ui.sensor_card import SensorCard
from ui.sensor_panel import SensorPanel
from ui.settings_dialog import SettingsDialog
from ui.temperature_chart import TemperatureChart
from utils import resource_path

_LOGO_PATH = resource_path("assets", "images", "logo.png")
_DEFAULT_HOST = "192.168.1.1"
_DEFAULT_PORT = 80

# ── UI timing / sizing constants ──────────────────────────────────────────────
_LOGO_SIZE_PX = 36  # logo scaled to a square of this many pixels
_STATE_FADE_MS = 400  # fade duration for the FSM state label
_ACTION_FADE_MS = 500  # fade duration for the action button group


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        """Initialise UI, chart, log window, PLC client and sensor panel; wire all signals."""
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._host = _DEFAULT_HOST
        self._port = _DEFAULT_PORT

        self._chart = TemperatureChart(self._ui.chart_view)
        self._log_win = LogWindow(self)
        self._plc = PlcClient(self)
        self._init_seq = InitSequence(self._plc, self)

        # Last known FSM state name — kept in sync by the init sequence and the
        # periodic STATE? poll.  Used by _apply_state_gating().
        self._current_state: str = "--"

        self._configure_widgets()

        # SensorPanel is created after _configure_widgets so the card dict and
        # chart are fully set up before signals are wired inside the panel.
        self._sensor_panel = SensorPanel(self._cards, self._chart, self._plc, self)

        self._connect_signals()
        self._load_logo()
        self.log("Interfaz Lista. Conectese al PLC para Comenzar.")

    # ── Post-setupUi configuration ───────────────────────────────────────────

    def _configure_widgets(self) -> None:
        """Set labels on promoted widgets and build reference dicts."""
        self._ui.card_tin.configure("T. Entrada", "°C")
        self._ui.card_tout.configure("T. Salida", "°C")
        self._ui.card_tcam.configure("T. Cámara", "°C")
        self._ui.card_tmez.configure("T. Mezcla", "°C")
        self._ui.card_flow.configure("Caudal", "L/min")
        self._ui.card_lvl.configure("Nivel", "")

        self._ui.row_heater.configure("Calentador")
        self._ui.row_pump.configure("Bomba")
        self._ui.row_chiller.configure("Enfriador")
        self._ui.row_valve1.configure("Válvula 1", "Abrir", "Cerrar")
        self._ui.row_valve2.configure("Válvula 2", "Abrir", "Cerrar")

        self._action_btns = [
            self._ui.btn_pause,
            self._ui.btn_resume,
            self._ui.btn_estop,
            self._ui.btn_ack,
            self._ui.btn_retry,
        ]

        # Logical device → its row widget.
        self._rows: dict[Device, ActuatorRow] = {
            Device.HEATER: self._ui.row_heater,
            Device.PUMP: self._ui.row_pump,
            Device.CHILLER: self._ui.row_chiller,
            Device.VALVE1: self._ui.row_valve1,
            Device.VALVE2: self._ui.row_valve2,
        }
        self._act_rows = list(self._rows.values())

        # Logical sensor → its display card.  Passed to SensorPanel after this method.
        self._cards: dict[Sensor, SensorCard] = {
            Sensor.TEMP_IN: self._ui.card_tin,
            Sensor.TEMP_OUT: self._ui.card_tout,
            Sensor.TEMP_BATH: self._ui.card_tcam,
            Sensor.TEMP_MIX: self._ui.card_tmez,
            Sensor.FLOW: self._ui.card_flow,
            Sensor.LEVEL: self._ui.card_lvl,
        }

        # Fades in the state label on every state change.
        self._state_fade = Fade(self._ui.lbl_state, duration=_STATE_FADE_MS)

        # Fades action buttons in when the connection is established.
        self._action_fades = [Fade(btn, duration=_ACTION_FADE_MS) for btn in self._action_btns]

    def _load_logo(self) -> None:
        """Load logo.png into the header label and window icon.

        If the file does not exist the label is hidden and no icon is set,
        so the app starts cleanly even without a logo asset.
        """
        if not _LOGO_PATH.exists():
            self._ui.lbl_logo.hide()
            return

        pixmap = QPixmap(str(_LOGO_PATH)).scaled(
            _LOGO_SIZE_PX,
            _LOGO_SIZE_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._ui.lbl_logo.setPixmap(pixmap)
        self.setWindowIcon(QIcon(str(_LOGO_PATH)))

    def _connect_signals(self) -> None:
        """Connect all Qt signals to their slot methods."""
        # ── Menu ──────────────────────────────────────────────────────────────
        self._ui.action_log.triggered.connect(self._toggle_log)
        self._ui.action_connection.triggered.connect(self._open_settings)

        # ── Connection lifecycle ───────────────────────────────────────────────
        self._ui.btn_connect.clicked.connect(self._on_btn_connect)
        self._plc.connecting.connect(self._on_tcp_connecting)
        self._plc.connected.connect(self._on_tcp_connected)
        self._plc.disconnected.connect(self._on_tcp_disconnected)
        self._plc.error.connect(self._on_tcp_error)

        # ── PLC traffic (log window) ───────────────────────────────────────────
        self._plc.command_sent.connect(lambda line: self.log(f"> {line}"))
        self._plc.line_received.connect(lambda line: self.log(f"< {line}"))
        self._log_win.message_send.connect(self._on_log_message)

        # ── Actuators ─────────────────────────────────────────────────────────
        self._plc.actuator_changed.connect(self._on_actuator_changed)
        self._plc.actuator_rejected.connect(self._on_actuator_rejected)
        for dev, row in self._rows.items():
            row.activated.connect(lambda on, d=dev: self._plc.set_actuator(d, on))

        # ── Init sequence ─────────────────────────────────────────────────────
        self._init_seq.progress.connect(self.log)
        self._init_seq.sensor_result.connect(self._on_init_sensor_result)
        self._init_seq.finished.connect(self._on_init_finished)

        # ── State polling ─────────────────────────────────────────────────────
        self._plc.state_received.connect(self._on_state_polled)

        # ── Action buttons ────────────────────────────────────────────────────
        self._ui.btn_pause.clicked.connect(lambda: self._plc.send_event(Evt.PAUSE))
        self._ui.btn_resume.clicked.connect(lambda: self._plc.send_event(Evt.UNPAUSE))
        self._ui.btn_estop.clicked.connect(self._on_stop_clicked)
        self._ui.btn_ack.clicked.connect(self._on_ack_clicked)
        self._ui.btn_retry.clicked.connect(self._on_retry_clicked)

    # ── Connection lifecycle slots ────────────────────────────────────────────

    def _toggle_log(self) -> None:
        """Show the log window, or bring it to front if already open."""
        if self._log_win.isVisible():
            self._log_win.activateWindow()
            self._log_win.raise_()
        else:
            self._log_win.show()

    def _open_settings(self) -> None:
        """Open the connection settings dialog."""
        dlg = SettingsDialog(self._host, self._port, self)
        if dlg.exec():
            self._host = dlg.host()
            self._port = dlg.port()
            self.log(f"Configuración Actualizada: {self._host}:{self._port}.")

    def _on_btn_connect(self) -> None:
        """Toggle the TCP connection on each button press."""
        if self._plc.is_connected:
            # Request a safe state before closing.  Qt flushes the write buffer
            # before sending the TCP FIN, so the FW receives PAUSE even though
            # disconnect_from() is called immediately after.
            self._plc.send_event(Evt.PAUSE)
            self._plc.disconnect_from()
        elif self._plc.is_connecting:
            self._plc.abort()
            self.log("Intento de conexión cancelado.")
            self.set_connected(False)
        else:
            self.log(f"Conectando a {self._host}:{self._port}...")
            self._plc.connect_to(self._host, self._port)

    def _on_tcp_connecting(self) -> None:
        self._ui.btn_connect.setText("Cancelar")

    def _on_tcp_connected(self) -> None:
        """Update connection indicator and start the initialization handshake.

        Sensor card interactivity is NOT enabled here — it is gated by
        _apply_state_gating and only unlocked when the PLC confirms MANUAL.
        """
        self._ui.lbl_conn.setText(f"● Conectado  {self._host}:{self._port}")
        self._ui.lbl_conn.setStyleSheet(f"color:{col.GREEN};font-size:13px;margin-left:8px;")
        self._ui.btn_connect.setText("Desconectar")
        for fade in self._action_fades:
            fade.play(0.0, 1.0)
        self.log(f"Conectado a {self._host}:{self._port}.")
        self._init_seq.start()

    def _on_tcp_disconnected(self) -> None:
        self._init_seq.abort()
        self.set_connected(False)
        self.log("Desconectado del PLC.")

    def _on_tcp_error(self, msg: str) -> None:
        self._init_seq.abort()
        self.log(f"Error de conexión: {msg}")
        self.set_connected(False)

    # ── Actuator slots ────────────────────────────────────────────────────────

    def _on_actuator_changed(self, dev: Device, on: bool) -> None:
        """Paint an actuator row once the PLC confirms its new state."""
        self._rows[dev].set_active(on)

    def _on_actuator_rejected(self, dev: Device) -> None:
        """Log that the PLC refused a command; the row is left unchanged."""
        self.log(f"  PLC rechazó el comando — {self._rows[dev].label()} sin cambios.")

    # ── Init sequence slots ───────────────────────────────────────────────────

    def _on_init_sensor_result(self, sensor: Sensor, ok: bool) -> None:
        """Delegate fault marking to the panel and log the sensor name."""
        self._sensor_panel.mark_init_fault(sensor, ok)
        if not ok:
            self.log(f"  Sensor con fallo: {self._sensor_panel.card_title(sensor)}")

    def _on_init_finished(self, success: bool, msg: str) -> None:
        """React to the end of the initialization handshake."""
        if success:
            self.log(f"Inicialización completa: {msg}")
        else:
            self.log(f"Error de inicialización: {msg}")
            # Query state once so the label and buttons reflect the current
            # PLC state (typically SOFT ERROR after a sensor fault).
            self._plc.query_state()

        # Always start the periodic STATE? poll — even after a failed init —
        # so the SCADA tracks state changes during fault recovery.
        self._plc.start_state_polling()

    # ── State polling slot ────────────────────────────────────────────────────

    def _on_state_polled(self, state: str) -> None:
        """Handle a STATE? reply from either the init sequence or the periodic poll.

        If the PLC is in CHECKUP and no handshake is in progress, start one
        automatically.  This handles: ACK FAULT that returned to CHECKUP (because
        previous state was CHECKUP), or any unexpected CHECKUP re-entry.
        """
        self.set_state(state)
        if state == "CHECKUP" and not self._init_seq.is_running:
            self._init_seq.restart()

    # ── Recovery action slots ─────────────────────────────────────────────────

    def _on_stop_clicked(self) -> None:
        """Send a graceful shutdown and disconnect.

        ``EVT:SHUTDOWN`` (kShutdown) is the correct event for an operator-initiated
        stop: the FW turns off all actuators and closes valves via ShutdownState, then
        returns to STARTUP automatically.

        ``EVT:STOP`` (kEStop) is intentionally not used here — kEStop is only handled
        in SoftErrorState (pushes to HardError); ManualState and PauseState silently
        ignore it, making it a no-op from the states where this button is active.

        After sending SHUTDOWN the SCADA disconnects so the operator gets a clean
        slate and must reconnect explicitly to start a new session.
        """
        self._plc.send_event(Evt.SHUTDOWN)
        self._plc.disconnect_from()

    def _on_ack_clicked(self) -> None:
        """Accept the fault and reach MANUAL without re-probing sensors.

        The init sequence's :meth:`~comms.init_sequence.InitSequence.force_proceed`
        exits SOFT ERROR if necessary and sends EVT:SCADA OK + EVT:SENSORS OK
        directly — bypassing the sensor probe — so the PLC reaches MANUAL even
        if some sensors are permanently offline.
        """
        self._sensor_panel.clear_faults()
        self._init_seq.force_proceed()

    def _on_retry_clicked(self) -> None:
        """Request a full sensor re-probe and re-run the init handshake."""
        self._plc.send_event(Evt.RETRY_CHECKUP)
        self._sensor_panel.clear_faults()
        self._init_seq.restart()

    # ── Misc slots ────────────────────────────────────────────────────────────

    def _on_log_message(self, msg: str) -> None:
        """Send a raw message typed in the log window to the PLC."""
        if not self._plc.send_raw(msg):
            self.log("No conectado — mensaje no enviado.")

    def _apply_state_gating(self, state: str) -> None:
        """Enable or disable controls based on the current PLC FSM state.

        Single authoritative place that maps FSM state names to button enable
        states.  Called from :meth:`set_state` on every state change.
        """
        connected = self._plc.is_connected
        is_manual = state == "MANUAL"
        is_pause = state == "PAUSE"
        is_soft_error = state == "SOFT ERROR"

        # Sensor cards are only interactive in MANUAL — the only state where the
        # FW accepts MEAS read commands.  In all other states (PAUSE, SOFT ERROR,
        # etc.) the FW replies COMMAND REJECTED, which would show ERR on the cards.
        self._sensor_panel.set_polling_allowed(connected and is_manual)

        # Actuators are only accepted by the PLC in MANUAL.
        actuator_on = connected and is_manual
        for row in self._act_rows:
            row.set_enabled_buttons(actuator_on)
        self._ui.heater_slider.setEnabled(actuator_on)
        self._ui.heater_spinbox.setEnabled(actuator_on)

        self._ui.btn_pause.setEnabled(connected and is_manual)
        self._ui.btn_resume.setEnabled(connected and is_pause)
        self._ui.btn_estop.setEnabled(connected and (is_manual or is_pause))
        self._ui.btn_ack.setEnabled(connected and is_soft_error)
        self._ui.btn_retry.setEnabled(connected and is_soft_error)

    # ── Public API ───────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        """Append a timestamped message to the log window."""
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log_win.append(f"[{ts}]  {msg}")

    def set_connected(self, connected: bool, host: str = "") -> None:
        """Update the connection indicator and reset the UI on disconnect.

        Button enable states are managed entirely by :meth:`_apply_state_gating`
        (called from :meth:`set_state`) once the PLC state is known — they are
        never bulk-enabled here, preventing accidental actuator commands before
        the PLC is in MANUAL.
        """
        if not connected:
            self._ui.lbl_conn.setText("● Desconectado")
            self._ui.lbl_conn.setStyleSheet(f"color:{col.GRAY};font-size:13px;margin-left:8px;")
            self._ui.btn_connect.setText("Conectar")
            self.set_state("--")
            self._sensor_panel.reset()
            self._sensor_panel.set_interactive(False)
            for fade in self._action_fades:
                fade.set_opacity(1.0)

    def set_state(self, state: str) -> None:
        """Update the state label, apply button gating and fade the label in."""
        self._current_state = state
        color = col.STATE_COLOR.get(state, col.GRAY)
        self._ui.lbl_state.setText(state)
        self._ui.lbl_state.setStyleSheet(
            f"color:{color};background:{col.PANEL};border:2px solid {color};"
            f"border-radius:6px;font-size:18px;font-weight:bold;padding:14px 8px;"
        )
        self._state_fade.play(0.2, 1.0)
        self._apply_state_gating(state)
