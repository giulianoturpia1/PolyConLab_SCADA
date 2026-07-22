from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMainWindow, QMessageBox

from comms.init_sequence import InitSequence
from comms.plc_client import PlcClient
from comms.protocol import Evt
from models import Device, Sensor
from ui.main_window_ui import Ui_MainWindow
from ui.scada_state import ScadaState, STATE_CONTROLS, from_plc
from ui.sensor_panel import SensorPanel
from ui.style import palette as col
from ui.style.anim import ACTION_BTN_FADE_MS, Fade, STATE_LABEL_FADE_MS
from ui.widgets.actuator_row import ActuatorRow
from ui.widgets.sensor_card import SensorCard
from ui.widgets.temperature_chart import TemperatureChart
from ui.windows.log_window import LogWindow
from ui.windows.settings_dialog import SettingsDialog
from utils import resource_path

_LOGO_PATH = resource_path("assets", "images", "logo.png")
_DEFAULT_HOST = "192.168.1.1"
_DEFAULT_PORT = 80

# ── UI sizing constants ───────────────────────────────────────────────────────
_LOGO_SIZE_PX = 36          # logo scaled to a square of this many pixels

# ── Connection label stylesheet values ───────────────────────────────────────
_CONN_FONT_PX = 13
_CONN_MARGIN_LEFT_PX = 8

# ── State label stylesheet values ─────────────────────────────────────────────
_STATE_FONT_PX = 18
_STATE_BORDER_RADIUS_PX = 6
_STATE_PADDING = "14px 8px"


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

        self._scada_state = ScadaState.DISCONNECTED

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
        self._state_fade = Fade(self._ui.lbl_state, duration=STATE_LABEL_FADE_MS)

        # Fades action buttons in when the connection is established.
        self._action_fades = [Fade(btn, duration=ACTION_BTN_FADE_MS) for btn in self._action_btns]

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
        self._ui.action_download.triggered.connect(self._download_data)

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
            self._reset_to_disconnected()
        else:
            self.log(f"Conectando a {self._host}:{self._port}...")
            self._plc.connect_to(self._host, self._port)

    def _on_tcp_connecting(self) -> None:
        self._transition(ScadaState.CONNECTING)
        self._ui.btn_connect.setText("Cancelar")

    def _on_tcp_connected(self) -> None:
        """Update connection indicator and start the initialization handshake.

        Sensor card interactivity is NOT enabled here — it is gated by
        _apply_state_gating and only unlocked when the PLC confirms MANUAL.
        """
        self._ui.lbl_conn.setText(f"● Conectado  {self._host}:{self._port}")
        self._ui.lbl_conn.setStyleSheet(
            f"color:{col.GREEN};font-size:{_CONN_FONT_PX}px;margin-left:{_CONN_MARGIN_LEFT_PX}px;"
        )
        self._ui.btn_connect.setText("Desconectar")
        for fade in self._action_fades:
            fade.play(0.0, 1.0)
        self.log(f"Conectado a {self._host}:{self._port}.")
        self._transition(ScadaState.INITIALIZING)
        self._init_seq.start()

    def _on_tcp_disconnected(self) -> None:
        self._init_seq.abort()
        self._reset_to_disconnected()
        self.log("Desconectado del PLC.")

    def _on_tcp_error(self, msg: str) -> None:
        self._init_seq.abort()
        self._reset_to_disconnected()
        self.log(f"Error de conexión: {msg}")

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

    def _on_state_polled(self, raw: str) -> None:
        """Handle a STATE? reply from either the init sequence or the periodic poll.

        If the PLC is in CHECKUP and no handshake is in progress, start one
        automatically.  This handles: ACK FAULT that returned to CHECKUP (because
        previous state was CHECKUP), or any unexpected CHECKUP re-entry.
        """
        self._update_state_label(raw)
        plc_state = from_plc(raw)
        self._transition(plc_state)
        if plc_state == ScadaState.CHECKUP and not self._init_seq.is_running:
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

    def _download_data(self) -> None:
        """Export a configurable number of measurements to CSV on the user's computer.

        Prompts the user for how many measurements to save (default 50).
        """
        # Ask user for number of measurements
        default_limit = 50
        limit, ok = QInputDialog.getInt(self, "Cantidad de mediciones", "Número de mediciones a guardar:", default_limit, 1, 100000, 1)
        if not ok:
            return

        default_name = f"mediciones_{QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar datos",
            default_name,
            "Archivos CSV (*.csv)",
        )
        if not file_path:
            return

        if self._chart.export_history(file_path, limit=limit):
            self.log(f"Datos descargados en {file_path} ({limit} filas).")
        else:
            QMessageBox.information(self, "Sin datos", "No hay mediciones disponibles para descargar.")

    def _on_log_message(self, msg: str) -> None:
        """Send a raw message typed in the log window to the PLC."""
        if not self._plc.send_raw(msg):
            self.log("No conectado — mensaje no enviado.")

    # ── State machine ─────────────────────────────────────────────────────────

    def _transition(self, new_state: ScadaState) -> None:
        """Move to a new SCADA state and apply the corresponding control permissions."""
        self._scada_state = new_state
        self._apply_state_gating()

    def _apply_state_gating(self) -> None:
        """Enable or disable controls by looking up the current state in STATE_CONTROLS."""
        c = STATE_CONTROLS[self._scada_state]
        self._sensor_panel.set_polling_allowed(c.sensors)
        for row in self._act_rows:
            row.set_enabled_buttons(c.actuators)
        self._ui.heater_slider.setEnabled(c.actuators)
        self._ui.heater_spinbox.setEnabled(c.actuators)
        self._ui.btn_pause.setEnabled(c.pause)
        self._ui.btn_resume.setEnabled(c.resume)
        self._ui.btn_estop.setEnabled(c.stop)
        self._ui.btn_ack.setEnabled(c.ack)
        self._ui.btn_retry.setEnabled(c.retry)

    def _update_state_label(self, raw: str) -> None:
        """Repaint the FSM state label and fade it in."""
        color = col.STATE_COLOR.get(raw, col.GRAY)
        self._ui.lbl_state.setText(raw)
        self._ui.lbl_state.setStyleSheet(
            f"color:{color};background:{col.PANEL};border:2px solid {color};"
            f"border-radius:{_STATE_BORDER_RADIUS_PX}px;font-size:{_STATE_FONT_PX}px;"
            f"font-weight:bold;padding:{_STATE_PADDING};"
        )
        self._state_fade.play(0.2, 1.0)

    def _reset_to_disconnected(self) -> None:
        """Reset all connection-dependent UI to the disconnected baseline."""
        self._update_state_label("--")
        self._transition(ScadaState.DISCONNECTED)
        self._sensor_panel.reset()
        self._sensor_panel.set_interactive(False)
        self._ui.lbl_conn.setText("● Desconectado")
        self._ui.lbl_conn.setStyleSheet(
            f"color:{col.GRAY};font-size:{_CONN_FONT_PX}px;margin-left:{_CONN_MARGIN_LEFT_PX}px;"
        )
        self._ui.btn_connect.setText("Conectar")
        for fade in self._action_fades:
            fade.set_opacity(1.0)

    # ── Public API ───────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        """Append a timestamped message to the log window."""
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log_win.append(f"[{ts}]  {msg}")
