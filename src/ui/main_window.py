from __future__ import annotations

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QMainWindow

from ui import palette as col
from ui.main_window_ui import Ui_MainWindow
from ui.temperature_chart import TemperatureChart


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self._chart = TemperatureChart(self._ui.chart_view, self._ui.series_toggles_container)
        self._configure_widgets()
        self.log("Interfaz lista. Conectá al PLC para comenzar.")

    # ── Post-setupUi configuration ───────────────────────────────────────────

    def _configure_widgets(self) -> None:
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

    # ── Public API ───────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._ui.log_view.appendPlainText(f"[{ts}]  {msg}")

    def set_connected(self, connected: bool, host: str = "") -> None:
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
        for row in self._act_rows:
            row.set_enabled_buttons(connected)
        self._ui.heater_slider.setEnabled(connected)
        self._ui.heater_spinbox.setEnabled(connected)

    def set_state(self, state: str) -> None:
        color = col.STATE_COLOR.get(state, col.GRAY)
        self._ui.lbl_state.setText(state)
        self._ui.lbl_state.setStyleSheet(
            f"color:{color};background:{col.PANEL};border:2px solid {color};"
            f"border-radius:6px;font-size:18px;font-weight:bold;padding:14px 8px;"
        )

    def push_temps(self, tin: float, tout: float, tcam: float, tmez: float) -> None:
        self._chart.push(tin, tout, tcam, tmez)
