from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMainWindow, QMessageBox

from comms.handshake import PlcHandshake
from comms.plc_client import PlcClient
from config.data import EXPORT_DEFAULT_ROWS, EXPORT_MAX_ROWS
from config.network import DEFAULT_HOST, DEFAULT_PORT
from models import Device, Sensor
from ui.actuator_panel import ActuatorPanel
from ui.main_window_ui import Ui_MainWindow
from ui.measurement_log import MeasurementLog
from ui.recovery_action_bar import RecoveryActionBar
from ui.scada_controller import ScadaController
from ui.sensor_panel import SensorPanel
from ui.style import metrics as m
from ui.style import palette as col
from ui.temperature_control import TemperatureControl
from ui.widgets.actuator_row import ActuatorRow
from ui.widgets.sensor_card import SensorCard
from ui.widgets.state_label import StateLabel
from ui.widgets.temperature_chart import TemperatureChart
from ui.windows.log_window import LogWindow
from ui.windows.settings_dialog import SettingsDialog
from utils import resource_path

_LOGO_PATH = resource_path("assets", "images", "logo.png")

# ── UI sizing constants ───────────────────────────────────────────────────────

# ── Connection label stylesheet values ───────────────────────────────────────


class MainWindow(QMainWindow):
    """Top-level window: builds the UI, wires the collaborators, and owns the menu,

    the log/CSV export, and the connection-indicator chrome.  All SCADA decision
    logic lives in :class:`~ui.scada_controller.ScadaController`; the panels own
    their widgets; this class only composes and paints its own header.
    """

    def __init__(self) -> None:
        """Build the UI, construct every collaborator, and wire the top-level signals."""
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)

        self._host = DEFAULT_HOST
        self._port = DEFAULT_PORT

        self._chart = TemperatureChart(self._ui.chart_view)
        self._log_win = LogWindow(self)
        self._plc = PlcClient(self)
        self._init_seq = PlcHandshake(self._plc, self)
        # Constructed before SensorPanel so the log is already listening to PLC status
        # signals by the time SensorPanel starts feeding it recorded measurements.
        self._log = MeasurementLog(self._plc, self)

        self._configure_widgets()

        # Panels are created after _configure_widgets so their reference dicts and
        # the chart are fully set up before each panel wires its own signals.
        self._sensor_panel = SensorPanel(self._cards, self._chart, self._log, self._plc, self)
        self._actuator_panel = ActuatorPanel(self._rows, self._plc, self)
        self._temp_control = TemperatureControl(
            self._ui.btn_temp_control, self._ui.heater_spinbox, self._ui.heater_slider, self._plc, self
        )
        self._recovery_bar = RecoveryActionBar(
            self._ui.btn_pause, self._ui.btn_resume, self._ui.btn_estop, self._ui.btn_ack, self._ui.btn_retry, self._ui.btn_reinit, self
        )

        # The controller owns the state machine and drives the collaborators above.
        self._controller = ScadaController(
            self._plc,
            self._init_seq,
            self._sensor_panel,
            self._actuator_panel,
            self._temp_control,
            self._recovery_bar,
            self._state_label,
            self,
        )

        self._connect_signals()
        self._load_logo()
        self.log("Interfaz Lista. Conectese al PLC para Comenzar.")

    # ── Post-setupUi configuration ───────────────────────────────────────────

    def _configure_widgets(self) -> None:
        """Set labels on promoted widgets and build the reference dicts for the panels."""
        self._ui.card_tin.configure("T. Entrada", "°C")
        self._ui.card_tout.configure("T. Salida", "°C")
        self._ui.card_tcam.configure("T. Camisa", "°C")
        self._ui.card_tmez.configure("T. Mezcla", "°C")
        self._ui.card_flow.configure("Caudal", "L/min")
        self._ui.card_lvl.configure("Nivel", "")

        self._ui.row_heater.configure("Calentador")
        self._ui.row_pump.configure("Bomba")
        self._ui.row_mixer.configure("Mezclador")
        self._ui.row_valve1.configure("Válvula 1", "Abrir", "Cerrar")

        # Logical device → its row widget.  Passed to ActuatorPanel after this method.
        self._rows: dict[Device, ActuatorRow] = {
            Device.HEATER: self._ui.row_heater,
            Device.PUMP: self._ui.row_pump,
            Device.MIXER: self._ui.row_mixer,
            Device.VALVE1: self._ui.row_valve1,
        }

        # Logical sensor → its display card.  Passed to SensorPanel after this method.
        self._cards: dict[Sensor, SensorCard] = {
            Sensor.TEMP_IN: self._ui.card_tin,
            Sensor.TEMP_OUT: self._ui.card_tout,
            Sensor.TEMP_BATH: self._ui.card_tcam,
            Sensor.TEMP_MIX: self._ui.card_tmez,
            Sensor.FLOW: self._ui.card_flow,
            Sensor.LEVEL: self._ui.card_lvl,
        }

        # Owns the FSM state label: text, colour, and fade on every change.
        self._state_label = StateLabel(self._ui.lbl_state)

    def _load_logo(self) -> None:
        """Load logo.png into the header label and window icon.

        If the file does not exist the label is hidden and no icon is set,
        so the app starts cleanly even without a logo asset.
        """
        if not _LOGO_PATH.exists():
            self._ui.lbl_logo.hide()
            return

        pixmap = QPixmap(str(_LOGO_PATH)).scaled(
            m.LOGO_SIZE_PX,
            m.LOGO_SIZE_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._ui.lbl_logo.setPixmap(pixmap)
        self.setWindowIcon(QIcon(str(_LOGO_PATH)))

    def _connect_signals(self) -> None:
        """Wire the top-level signals between the UI, the collaborators, and the controller."""
        # ── Menu ──────────────────────────────────────────────────────────────
        self._ui.action_log.triggered.connect(self._toggle_log)
        self._ui.action_connection.triggered.connect(self._open_settings)
        self._ui.action_download.triggered.connect(self._download_data)
        self._ui.action_link_stats.triggered.connect(self._show_link_stats)

        # ── Connection button → controller ─────────────────────────────────────
        self._ui.btn_connect.clicked.connect(lambda: self._controller.toggle_connection(self._host, self._port))

        # ── PLC traffic (log window) ───────────────────────────────────────────
        self._plc.command_sent.connect(lambda line: self.log(f"> {line}"))
        self._plc.line_received.connect(lambda line: self.log(f"< {line}"))
        self._log_win.message_send.connect(self._on_log_message)

        # ── Log routing from the collaborators ──────────────────────────────────
        self._actuator_panel.log.connect(self.log)
        self._temp_control.log.connect(self.log)
        self._controller.log.connect(self.log)

        # ── Connection-indicator chrome driven by the controller ────────────────
        self._controller.view_connecting.connect(self._on_view_connecting)
        self._controller.view_connected.connect(self._on_view_connected)
        self._controller.view_disconnected.connect(self._on_view_disconnected)

    # ── Menu slots ──────────────────────────────────────────────────────────────

    def _toggle_log(self) -> None:
        """Show the log window, or bring it to front if already open."""
        if self._log_win.isVisible():
            self._log_win.activateWindow()
            self._log_win.raise_()
        else:
            self._log_win.show()

    def _open_settings(self) -> None:
        """Open the settings dialog; store the new host/port and apply the sampling period at once."""
        recommended_min = PlcClient.recommended_min_period_ms()
        dlg = SettingsDialog(self._host, self._port, self._plc.sample_period_ms, recommended_min, self)
        if not dlg.exec():
            return
        self._host = dlg.host()
        self._port = dlg.port()
        self.log(f"Configuración Actualizada: {self._host}:{self._port}.")

        period = dlg.sample_period_ms()
        if period != self._plc.sample_period_ms:
            if self._plc.is_connected:
                # Close the previous period's statistics window before a new one starts.
                self.log(self._plc.link_stats_summary())
            self._plc.set_sample_period(period)
            self.log(f"Período de muestreo: {period} ms.")
            if period < recommended_min:
                self.log(f"Aviso: por debajo del mínimo recomendado ({recommended_min} ms).")

    def _show_link_stats(self) -> None:
        """Write the link statistics since the last connect or period change to the log, and show it."""
        self.log(self._plc.link_stats_summary())
        self._toggle_log()

    # ── Connection-indicator chrome ───────────────────────────────────────────────

    def _on_view_connecting(self) -> None:
        """A connection attempt has started — offer to cancel it."""
        self._ui.btn_connect.setText("Cancelar")

    def _on_view_connected(self, host: str, port: int) -> None:
        """The PLC is connected — paint the indicator green."""
        self._ui.lbl_conn.setText(f"● Conectado  {host}:{port}")
        self._ui.lbl_conn.setStyleSheet(
            f"color:{col.GREEN};font-size:{m.CONN_FONT_PX}px;margin-left:{m.CONN_MARGIN_LEFT_PX}px;"
        )
        self._ui.btn_connect.setText("Desconectar")

    def _on_view_disconnected(self) -> None:
        """The session is down — paint the disconnected baseline."""
        self._ui.lbl_conn.setText("● Desconectado")
        self._ui.lbl_conn.setStyleSheet(
            f"color:{col.GRAY};font-size:{m.CONN_FONT_PX}px;margin-left:{m.CONN_MARGIN_LEFT_PX}px;"
        )
        self._ui.btn_connect.setText("Conectar")

    # ── Misc slots ────────────────────────────────────────────────────────────────

    def _download_data(self) -> None:
        """Export a configurable number of measurements to CSV on the user's computer.

        Prompts the user for how many measurements to save (default EXPORT_DEFAULT_ROWS).
        """
        limit, ok = QInputDialog.getInt(
            self, "Cantidad de mediciones", "Número de mediciones a guardar:", EXPORT_DEFAULT_ROWS, 1, EXPORT_MAX_ROWS, 1
        )
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

        if self._log.export_csv(file_path, limit=limit):
            self.log(f"Datos descargados en {file_path} ({limit} filas).")
        else:
            QMessageBox.information(self, "Sin datos", "No hay mediciones disponibles para descargar.")

    def _on_log_message(self, msg: str) -> None:
        """Send a raw message typed in the log window to the PLC."""
        if not self._plc.send_raw(msg):
            self.log("No conectado — mensaje no enviado.")

    # ── Public API ───────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        """Append a timestamped message to the log window."""
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log_win.append(f"[{ts}]  {msg}")
