from __future__ import annotations

from PySide6.QtCore import QDateTime, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QMainWindow

from network.tcp_client import TcpClient
from ui import palette as col
from ui.log_window import LogWindow
from ui.main_window_ui import Ui_MainWindow
from ui.settings_dialog import SettingsDialog
from ui.temperature_chart import TemperatureChart
from utils import resource_path

_LOGO_PATH = resource_path("assets", "images", "logo.png")
_DEFAULT_HOST = "192.168.1.1"
_DEFAULT_PORT = 80


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
        self._tcp = TcpClient(self)

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
        self._act_rows = [
            self._ui.row_heater,
            self._ui.row_pump,
            self._ui.row_chiller,
            self._ui.row_valve1,
            self._ui.row_valve2,
        ]

        # Opacity animation for the state label: fades in on every state change.
        self._state_effect = QGraphicsOpacityEffect(self._ui.lbl_state)
        self._state_effect.setOpacity(1.0)
        self._ui.lbl_state.setGraphicsEffect(self._state_effect)
        self._state_anim = QPropertyAnimation(self._state_effect, b"opacity", self)
        self._state_anim.setDuration(400)
        self._state_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Opacity animations for action buttons: fade in when the connection is established.
        self._action_btn_anims: list[tuple[QGraphicsOpacityEffect, QPropertyAnimation]] = []
        for btn in self._action_btns:
            effect = QGraphicsOpacityEffect(btn)
            effect.setOpacity(1.0)
            btn.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(500)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._action_btn_anims.append((effect, anim))

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

        # TCP client lifecycle
        self._tcp.connected.connect(self._on_tcp_connected)
        self._tcp.disconnected.connect(self._on_tcp_disconnected)
        self._tcp.error.connect(self._on_tcp_error)

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
        if self._tcp.is_connected:
            self._tcp.disconnect_from()
        else:
            self.log(f"Conectando a {self._host}:{self._port}...")
            self._tcp.connect_to(self._host, self._port)

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

        for btn in self._action_btns:
            btn.setEnabled(connected)

        # Fade action buttons in when connecting, snap back to full opacity when disconnecting.
        for effect, anim in self._action_btn_anims:
            anim.stop()
            if connected:
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.start()
            else:
                effect.setOpacity(1.0)
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
        self._state_anim.stop()
        self._state_anim.setStartValue(0.2)
        self._state_anim.setEndValue(1.0)
        self._state_anim.start()

    def push_temps(self, tin: float, tout: float, tcam: float, tmez: float) -> None:
        """Forward a new temperature sample to the chart for all four sensors."""
        self._chart.push(tin, tout, tcam, tmez)
