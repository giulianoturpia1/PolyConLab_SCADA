"""
Standalone log viewer window for advanced users.

Opened via the main-window header button; non-modal so it can stay
open alongside the main window during normal operation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui import palette as col


class LogWindow(QWidget):
    """Separate non-modal window that displays the system event log."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Log del Sistema")
        self.resize(800, 450)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {col.BG};
                color: {col.WHITE};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }}
            QPlainTextEdit {{
                background-color: #151820;
                color: #7E8898;
                border: 1px solid {col.BORDER};
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }}
            QPushButton {{
                background-color: {col.PANEL};
                color: {col.WHITE};
                border: 1px solid {col.BORDER};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #353A47;
                border-color: {col.BLUE};
            }}
            QPushButton:pressed {{
                background-color: #23272E;
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        """Create the log view and the clear button."""
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        root.addWidget(self._log_view)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_clear = QPushButton("Limpiar")
        btn_clear.setFixedWidth(80)
        btn_clear.clicked.connect(self._log_view.clear)
        btn_row.addWidget(btn_clear)
        root.addLayout(btn_row)

    # ── Public API ───────────────────────────────────────────────────────────

    def append(self, msg: str) -> None:
        """Append a pre-formatted message to the log view."""
        self._log_view.appendPlainText(msg)
