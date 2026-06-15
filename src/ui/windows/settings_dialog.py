"""
Connection settings dialog (host + port).

Opens modally from the Configuración menu.  Returns the new values only
if the user clicks Aceptar; clicking Cancelar leaves settings unchanged.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from ui.style import palette as col


class SettingsDialog(QDialog):
    """Modal form for editing the TCP connection settings."""

    def __init__(self, host: str, port: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de Conexión")
        self.setFixedSize(320, 148)
        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background-color: {col.BG};
                color: {col.WHITE};
                font-size: 13px;
            }}
            QLineEdit, QSpinBox {{
                background-color: {col.PANEL};
                color: {col.WHITE};
                border: 1px solid {col.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {col.BLUE};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {col.BORDER};
                border: none;
                width: 16px;
            }}
            QPushButton {{
                background-color: {col.PANEL};
                color: {col.WHITE};
                border: 1px solid {col.BORDER};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background-color: #353A47; border-color: {col.BLUE}; }}
            QPushButton:pressed {{ background-color: #23272E; }}
        """)
        self._build_ui(host, port)

    def _build_ui(self, host: str, port: int) -> None:
        """Create the IP/port form and the Accept/Cancel button box."""
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self._inp_host = QLineEdit(host)
        self._inp_host.setPlaceholderText("192.168.1.1")
        form.addRow("Dirección IP:", self._inp_host)

        self._inp_port = QSpinBox()
        self._inp_port.setRange(1, 65535)
        self._inp_port.setValue(port)
        form.addRow("Puerto:", self._inp_port)

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
