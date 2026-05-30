from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow

from comms.plc_client import PlcClient
from comms.protocol import Device, Evt, Sensor, parse_value
from ui import palette as col
from ui.anim import Fade
from ui.log_window import LogWindow
from ui.main_window_ui import Ui_MainWindow
from ui.settings_dialog import SettingsDialog
from ui.temperature_chart import TemperatureChart
from ui.widgets import ActuatorRow, SensorCard
from utils import resource_path

_LOGO_PATH = resource_path("assets", "images", "logo.png")
_DEFAULT_HOST = "192.168.1.1"
_DEFAULT_PORT = 80

# The four temperatures the chart plots, in the order push_temps() expects.
_CHART_SENSORS = (Sensor.TEMP_IN, Sensor.TEMP_OUT, Sensor.TEMP_BATH, Sensor.TEMP_MIX)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        """Initialise UI, chart, log window and TCP client; wire all signals."""
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._host = _DEFAULT_HOST
        self._port = _DEFAULT_PORT

        self._chart = TemperatureChart(self._ui.chart_view, self._ui.series_toggles_container)
        self._log_win = LogWindow(self)
        self._plc = PlcClient(self)

        self._configure_widgets()
        self._connect_signals()
        self._load_logo()
        self.log("Interfaz Lista. Conectese al PLC para Comenzar.")

    # ── Post-setupUi configuration ───────────────────────────────────────────

    def _configure_widgets(self) -> None:
        """Set labels on promoted widgets and build reference lists for bulk enable/disable."""
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
        # The only actuator mapping the view keeps: logical device → its row widget.
        # All protocol knowledge lives in comms.protocol / PlcClient.
        self._rows: dict[Device, ActuatorRow] = {
            Device.HEATER: self._ui.row_heater,
            Device.PUMP: self._ui.row_pump,
            Device.CHILLER: self._ui.row_chiller,
            Device.VALVE1: self._ui.row_valve1,
            Device.VALVE2: self._ui.row_valve2,
        }
        self._act_rows = list(self._rows.values())

        # Logical sensor → its display card. Protocol knowledge stays in comms.
        self._cards: dict[Sensor, SensorCard] = {
            Sensor.TEMP_IN: self._ui.card_tin,
            Sensor.TEMP_OUT: self._ui.card_tout,
            Sensor.TEMP_BATH: self._ui.card_tcam,
            Sensor.TEMP_MIX: self._ui.card_tmez,
            Sensor.FLOW: self._ui.card_flow,
            Sensor.LEVEL: self._ui.card_lvl,
        }
        # Latest temperature readings, accumulated into a full set before the
        # chart is fed (push_temps wants all four at once).
        self._temp_batch: dict[Sensor, float] = {}

        # Fades in the state label on every state change.
        self._state_fade = Fade(self._ui.lbl_state, duration=400)

        # Fades action buttons in when the connection is established.
        self._action_fades = [Fade(btn, duration=500) for btn in self._action_btns]

    def _load_logo(self) -> None:
        """Load logo.png into the header label and window icon.

        If the file does not exist the label is hidden and no icon is set,
        so the app starts cleanly even without a logo asset.
        """
        if not _LOGO_PATH.exists():
            self._ui.lbl_logo.hide()
            return

        pixmap = QPixmap(str(_LOGO_PATH)).scaled(
            36,
            36,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._ui.lbl_logo.setPixmap(pixmap)
        self.setWindowIcon(QIcon(str(_LOGO_PATH)))

    def _connect_signals(self) -> None:
        """Connect all Qt signals to their slot methods."""
        # Menu actions
        self._ui.action_log.triggered.connect(self._toggle_log)
        self._ui.action_connection.triggered.connect(self._open_settings)

        # Header connect button
        self._ui.btn_connect.clicked.connect(self._on_btn_connect)

        # PLC client lifecycle
        self._plc.connecting.connect(self._on_tcp_connecting)
        self._plc.connected.connect(self._on_tcp_connected)
        self._plc.disconnected.connect(self._on_tcp_disconnected)
        self._plc.error.connect(self._on_tcp_error)

        # PLC client traffic + domain events
        self._plc.command_sent.connect(lambda line: self.log(f"> {line}"))
        self._plc.line_received.connect(lambda line: self.log(f"< {line}"))
        self._plc.actuator_changed.connect(self._on_actuator_changed)
        self._plc.actuator_rejected.connect(self._on_actuator_rejected)
        self._plc.sensor_updated.connect(self._on_sensor_updated)
        self._plc.sensor_fault.connect(self._on_sensor_fault)

        # Log-window message bar
        self._log_win.message_send.connect(self._on_log_message)

        # Action buttons → state-machine events
        self._ui.btn_pause.clicked.connect(lambda: self._plc.send_event(Evt.PAUSE))
        self._ui.btn_resume.clicked.connect(lambda: self._plc.send_event(Evt.UNPAUSE))
        self._ui.btn_estop.clicked.connect(lambda: self._plc.send_event(Evt.STOP))
        self._ui.btn_ack.clicked.connect(lambda: self._plc.send_event(Evt.ACK_FAULT))
        self._ui.btn_retry.clicked.connect(lambda: self._plc.send_event(Evt.RETRY_CHECKUP))

        # Actuator rows → device commands; the row updates only on PLC confirmation.
        for dev, row in self._rows.items():
            row.activated.connect(lambda on, d=dev: self._plc.set_actuator(d, on))

    # ── Slot handlers ────────────────────────────────────────────────────────

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
            self._plc.disconnect_from()
        elif self._plc.is_connecting:
            self._plc.abort()
            self.log("Intento de conexión cancelado.")
            self.set_connected(False)
        else:
            self.log(f"Conectando a {self._host}:{self._port}...")
            self._plc.connect_to(self._host, self._port)

    def _on_tcp_connecting(self) -> None:
        """Update button text while a connection attempt is in progress."""
        self._ui.btn_connect.setText("Cancelar")

    def _on_tcp_connected(self) -> None:
        """Update UI state when the TCP connection is established."""
        self.set_connected(True, f"{self._host}:{self._port}")
        self.log(f"Conectado a {self._host}:{self._port}.")

    def _on_tcp_disconnected(self) -> None:
        """Update UI state when the TCP connection is lost or closed."""
        self.set_connected(False)
        self.log("Desconectado del PLC.")

    def _on_tcp_error(self, msg: str) -> None:
        """Log the connection error and reset the UI to disconnected state."""
        self.log(f"Error de conexión: {msg}")
        self.set_connected(False)

    def _on_actuator_changed(self, dev: Device, on: bool) -> None:
        """Paint an actuator row once the PLC confirms its new state."""
        self._rows[dev].set_active(on)

    def _on_actuator_rejected(self, dev: Device) -> None:
        """Log that the PLC refused an actuator command; the row is left unchanged."""
        self.log(f"  PLC rechazó el comando — {self._rows[dev].label()} sin cambios.")

    def _on_sensor_updated(self, sensor: Sensor, value: str) -> None:
        """Show a fresh sensor reading on its card and feed the temperature chart."""
        self._cards[sensor].set_value(value)
        temp = parse_value(value)
        if temp is not None and sensor in _CHART_SENSORS:
            self._temp_batch[sensor] = temp
            if all(s in self._temp_batch for s in _CHART_SENSORS):
                self.push_temps(*(self._temp_batch[s] for s in _CHART_SENSORS))
                self._temp_batch.clear()

    def _on_sensor_fault(self, sensor: Sensor) -> None:
        """Mark a sensor card as faulted; drop any partial temperature batch."""
        self._cards[sensor].set_value("ERR", col.RED)
        self._temp_batch.pop(sensor, None)

    def _on_log_message(self, msg: str) -> None:
        """Send a raw message (command or event) typed in the log window to the PLC."""
        if not self._plc.send_raw(msg):
            self.log("No conectado — mensaje no enviado.")

    # ── Public API ───────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        """Append a timestamped message to the log window."""
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log_win.append(f"[{ts}]  {msg}")

    def set_connected(self, connected: bool, host: str = "") -> None:
        """Update the connection indicator, button text and actuator enable state."""
        if connected:
            self._ui.lbl_conn.setText(f"● Conectado  {host}")
            self._ui.lbl_conn.setStyleSheet(f"color:{col.GREEN};font-size:13px;margin-left:8px;")
            self._ui.btn_connect.setText("Desconectar")
        else:
            self._ui.lbl_conn.setText("● Desconectado")
            self._ui.lbl_conn.setStyleSheet(f"color:{col.GRAY};font-size:13px;margin-left:8px;")
            self._ui.btn_connect.setText("Conectar")
            self.set_state("--")
            self._temp_batch.clear()

        for btn in self._action_btns:
            btn.setEnabled(connected)

        # Fade action buttons in when connecting, snap back to full opacity when disconnecting.
        for fade in self._action_fades:
            if connected:
                fade.play(0.0, 1.0)
            else:
                fade.set_opacity(1.0)
        for row in self._act_rows:
            row.set_enabled_buttons(connected)
        self._ui.heater_slider.setEnabled(connected)
        self._ui.heater_spinbox.setEnabled(connected)

    def set_state(self, state: str) -> None:
        """Update the state label text and border colour, then fade it in."""
        color = col.STATE_COLOR.get(state, col.GRAY)
        self._ui.lbl_state.setText(state)
        self._ui.lbl_state.setStyleSheet(
            f"color:{color};background:{col.PANEL};border:2px solid {color};"
            f"border-radius:6px;font-size:18px;font-weight:bold;padding:14px 8px;"
        )
        self._state_fade.play(0.2, 1.0)

    def push_temps(self, tin: float, tout: float, tcam: float, tmez: float) -> None:
        """Forward a new temperature sample to the chart for all four sensors."""
        self._chart.push(tin, tout, tcam, tmez)
