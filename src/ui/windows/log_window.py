"""
Standalone log viewer window for advanced users.

Opened via the main-window header button; non-modal so it can stay
open alongside the main window during normal operation.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.style import metrics as m
from ui.style import palette as col


class LogWindow(QWidget):
    """Separate non-modal window that displays the system event log."""

    message_send = Signal(str)  # emitted when the user submits a message (command or event)

    _MAX_HISTORY = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        self._history: list[str] = []  # oldest → newest
        self._history_idx: int = -1  # -1 = not browsing; 0..n-1 = position in history
        self._draft: str = ""  # input saved when the user starts navigating up
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Log del Sistema")
        self.resize(m.LOG_WINDOW_W_PX, m.LOG_WINDOW_H_PX)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {col.BG};
                color: {col.WHITE};
                font-family: {m.FONT_UI};
                font-size: {m.DIALOG_FONT_PX}px;
            }}
            QPlainTextEdit {{
                background-color: {col.CONSOLE_BG};
                color: {col.CONSOLE_TEXT};
                border: {m.BORDER_PX}px solid {col.BORDER};
                border-radius: {m.CONTROL_RADIUS_PX}px;
                font-family: {m.FONT_MONO};
                font-size: {m.SMALL_FONT_PX}px;
            }}
            QLineEdit {{
                background-color: {col.CONSOLE_BG};
                color: {col.WHITE};
                border: {m.BORDER_PX}px solid {col.BORDER};
                border-radius: {m.CONTROL_RADIUS_PX}px;
                padding: {m.INPUT_PADDING};
                font-family: {m.FONT_MONO};
                font-size: {m.CONTROL_FONT_PX}px;
            }}
            QLineEdit:focus {{
                border-color: {col.BLUE};
            }}
            QPushButton {{
                background-color: {col.PANEL};
                color: {col.WHITE};
                border: {m.BORDER_PX}px solid {col.BORDER};
                border-radius: {m.CONTROL_RADIUS_PX}px;
                padding: {m.LOG_BUTTON_PADDING};
                font-size: {m.CONTROL_FONT_PX}px;
            }}
            QPushButton:hover {{
                background-color: {col.PANEL_HOVER};
                border-color: {col.BLUE};
            }}
            QPushButton:pressed {{
                background-color: {col.PRESSED};
            }}
            QLabel#cmd_label {{
                color: {col.GRAY};
                font-size: {m.SMALL_FONT_PX}px;
            }}
        """)
        self._build_ui()

    def _build_ui(self) -> None:
        """Create the log view, command bar, and clear button."""
        root = QVBoxLayout(self)
        root.setContentsMargins(m.LOG_MARGIN_PX, m.LOG_MARGIN_PX, m.LOG_MARGIN_PX, m.LOG_MARGIN_PX)
        root.setSpacing(m.LOG_SPACING_PX)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        root.addWidget(self._log_view)

        # Message input row
        cmd_row = QHBoxLayout()
        cmd_label = QLabel("CMD")
        cmd_label.setObjectName("cmd_label")
        cmd_label.setFixedWidth(m.LOG_CMD_LABEL_W_PX)
        cmd_row.addWidget(cmd_label)

        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText("Ingrese comando o evento SCPI y presione Enter…")
        self._cmd_input.returnPressed.connect(self._send_message)
        self._cmd_input.installEventFilter(self)
        cmd_row.addWidget(self._cmd_input)

        btn_send = QPushButton("Enviar")
        btn_send.setFixedWidth(m.LOG_SEND_BTN_W_PX)
        btn_send.clicked.connect(self._send_message)
        cmd_row.addWidget(btn_send)

        root.addLayout(cmd_row)

        # Bottom button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_clear = QPushButton("Limpiar")
        btn_clear.setFixedWidth(m.LOG_CLEAR_BTN_W_PX)
        btn_clear.clicked.connect(self._log_view.clear)
        btn_row.addWidget(btn_clear)
        root.addLayout(btn_row)

    def eventFilter(self, source, event) -> bool:
        if source is self._cmd_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                self._history_navigate(-1)
                return True
            if key == Qt.Key.Key_Down:
                self._history_navigate(+1)
                return True
        return super().eventFilter(source, event)

    def _history_navigate(self, direction: int) -> None:
        """Move through history. direction=-1 is older (Up), +1 is newer (Down)."""
        if not self._history:
            return
        if self._history_idx == -1:
            # First Up press: save the current draft and jump to the newest entry.
            self._draft = self._cmd_input.text()
            self._history_idx = len(self._history) - 1
        else:
            new_idx = self._history_idx - direction  # Up subtracts (goes toward index 0)
            if new_idx < 0:
                return  # Already at oldest entry, do nothing.
            if new_idx >= len(self._history):
                # Stepped past the newest entry: restore the draft.
                self._history_idx = -1
                self._cmd_input.setText(self._draft)
                return
            self._history_idx = new_idx
        self._cmd_input.setText(self._history[self._history_idx])

    def _send_message(self) -> None:
        msg = self._cmd_input.text().strip()
        if not msg:
            return
        # Add to history: remove duplicate if present, append at end, cap to MAX_HISTORY.
        if msg in self._history:
            self._history.remove(msg)
        self._history.append(msg)
        if len(self._history) > self._MAX_HISTORY:
            self._history.pop(0)
        # Reset navigation state.
        self._history_idx = -1
        self._draft = ""
        self._cmd_input.clear()
        self.message_send.emit(msg)

    # ── Public API ───────────────────────────────────────────────────────────

    def append(self, msg: str) -> None:
        """Append a pre-formatted message to the log view."""
        self._log_view.appendPlainText(msg)
