"""
Non-blocking TCP client built on QTcpSocket.

Emits plain Python signals so the rest of the application never has to
touch the socket directly.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket


class TcpClient(QObject):
    """Thin wrapper around QTcpSocket that exposes connection lifecycle signals."""

    connected = Signal()  # socket reached ConnectedState
    disconnected = Signal()  # socket left ConnectedState
    error = Signal(str)  # human-readable error string
    data_received = Signal(bytes)  # raw bytes from the remote end

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the socket and wire its low-level signals to the public ones."""
        super().__init__(parent)
        self._socket = QTcpSocket(self)
        self._socket.connected.connect(self.connected)
        self._socket.disconnected.connect(self.disconnected)
        self._socket.errorOccurred.connect(self._on_error)
        self._socket.readyRead.connect(self._on_data)

    # ── Public API ───────────────────────────────────────────────────────────

    def connect_to(self, host: str, port: int) -> None:
        """Initiate a non-blocking connection to host:port."""
        self._socket.connectToHost(host, port)

    def disconnect_from(self) -> None:
        """Close the connection gracefully."""
        self._socket.disconnectFromHost()

    def send(self, data: bytes) -> None:
        """Write raw bytes to the socket (no-op if not connected)."""
        if self.is_connected:
            self._socket.write(data)

    @property
    def is_connected(self) -> bool:
        """Return True when the socket is in the ConnectedState."""
        return self._socket.state() == QAbstractSocket.SocketState.ConnectedState

    # ── Internals ────────────────────────────────────────────────────────────

    def _on_error(self, _: QAbstractSocket.SocketError) -> None:
        """Forward the socket error as a human-readable string."""
        self.error.emit(self._socket.errorString())

    def _on_data(self) -> None:
        """Read all pending bytes and emit them as a single data_received signal."""
        self.data_received.emit(bytes(self._socket.readAll()))
