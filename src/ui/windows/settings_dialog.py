"""
Settings dialog: connection (host + port) and sensor sampling period.

Opens modally from the Configuración menu.  Returns the new values only
if the user clicks Aceptar; clicking Cancelar leaves settings unchanged.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from config.network import DEFAULT_HOST, PORT_MAX, PORT_MIN
from config.polling import SAMPLE_PERIOD_MAX_MS, SAMPLE_PERIOD_MIN_MS, SAMPLE_PERIOD_STEP_MS
from ui.style import metrics as m
from ui.style import palette as col


class SettingsDialog(QDialog):
    """Modal form for editing the TCP connection settings and the sensor sampling period."""

    def __init__(self, host: str, port: int, period_ms: int, recommended_min_ms: int, parent=None) -> None:
        super().__init__(parent)
        self._recommended_min_ms = recommended_min_ms
        self.setWindowTitle("Configuración")
        self.setFixedSize(m.SETTINGS_DIALOG_W_PX, m.SETTINGS_DIALOG_H_PX)
        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background-color: {col.BG};
                color: {col.WHITE};
                font-size: {m.DIALOG_FONT_PX}px;
            }}
            QLineEdit, QSpinBox {{
                background-color: {col.PANEL};
                color: {col.WHITE};
                border: {m.BORDER_PX}px solid {col.BORDER};
                border-radius: {m.CONTROL_RADIUS_PX}px;
                padding: {m.INPUT_PADDING};
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {col.BLUE};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {col.BORDER};
                border: none;
                width: {m.SETTINGS_SPIN_BUTTON_W_PX}px;
            }}
            QPushButton {{
                background-color: {col.PANEL};
                color: {col.WHITE};
                border: {m.BORDER_PX}px solid {col.BORDER};
                border-radius: {m.CONTROL_RADIUS_PX}px;
                padding: {m.SETTINGS_BUTTON_PADDING};
            }}
            QPushButton:hover {{ background-color: {col.PANEL_HOVER}; border-color: {col.BLUE}; }}
            QPushButton:pressed {{ background-color: {col.PRESSED}; }}
        """)
        self._build_ui(host, port, period_ms)

    def _build_ui(self, host: str, port: int, period_ms: int) -> None:
        """Create the IP/port/sampling-period form and the Accept/Cancel button box."""
        root = QVBoxLayout(self)
        root.setContentsMargins(*m.SETTINGS_MARGINS)
        root.setSpacing(m.SETTINGS_SPACING_PX)

        form = QFormLayout()
        form.setSpacing(m.SETTINGS_FORM_SPACING_PX)

        self._inp_host = QLineEdit(host)
        self._inp_host.setPlaceholderText(DEFAULT_HOST)
        form.addRow("Dirección IP:", self._inp_host)

        self._inp_port = QSpinBox()
        self._inp_port.setRange(PORT_MIN, PORT_MAX)
        self._inp_port.setValue(port)
        form.addRow("Puerto:", self._inp_port)

        self._inp_period = QSpinBox()
        self._inp_period.setRange(SAMPLE_PERIOD_MIN_MS, SAMPLE_PERIOD_MAX_MS)
        self._inp_period.setSingleStep(SAMPLE_PERIOD_STEP_MS)
        self._inp_period.setSuffix(" ms")
        self._inp_period.setValue(period_ms)
        form.addRow("Período de muestreo:", self._inp_period)

        # Warning shown only while the period is below the recommended minimum. With the current
        # bounds the field cannot go that low, so it appears only if those values ever change.
        self._form = form
        self._lbl_period_hint = QLabel()
        self._lbl_period_hint.setWordWrap(True)
        self._lbl_period_hint.setStyleSheet(f"color:{col.ORANGE};font-size:{m.SETTINGS_HINT_FONT_PX}px;")
        form.addRow("", self._lbl_period_hint)
        self._inp_period.valueChanged.connect(self._update_period_hint)
        self._update_period_hint(period_ms)

        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ── Public API ───────────────────────────────────────────────────────────

    def host(self) -> str:
        """Return the trimmed IP/hostname entered by the user."""
        return self._inp_host.text().strip()

    def port(self) -> int:
        """Return the port number entered by the user."""
        return self._inp_port.value()

    def sample_period_ms(self) -> int:
        """Return the sampling period entered by the user, in milliseconds."""
        return self._inp_period.value()

    # ── Internals ────────────────────────────────────────────────────────────

    def _update_period_hint(self, period_ms: int) -> None:
        """Show the warning row only while the period is below the recommended minimum."""
        below = period_ms < self._recommended_min_ms
        self._lbl_period_hint.setText(
            f"Por debajo del mínimo recomendado ({self._recommended_min_ms} ms): el PLC puede no responder a tiempo."
        )
        self._form.setRowVisible(self._lbl_period_hint, below)
