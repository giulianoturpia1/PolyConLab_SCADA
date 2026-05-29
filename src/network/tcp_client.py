"""
Non-blocking TCP client built on QTcpSocket.

Emits plain Python signals so the rest of the application never has to
touch the socket directly.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

_CONNECT_TIMEOUT_MS = 5_000


class TcpClient(QObject):
    """Thin wrapper around QTcpSocket that exposes connection lifecycle signals."""

    connecting = Signal()  # socket started connecting
    connected = Signal()  # socket reached ConnectedState
    disconnected = Signal()  # socket left ConnectedState
    error = Signal(str)  # human-readable error string
    data_received = Signal(bytes)  # raw bytes from the remote end

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the socket and wire its low-level signals to the public ones."""
        super().__init__(parent)
        self._socket = QTcpSocket(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self.disconnected)
        self._socket.errorOccurred.connect(self._on_error)
        self._socket.readyRead.connect(self._on_data)

        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(_CONNECT_TIMEOUT_MS)
        self._timeout.timeout.connect(self._on_timeout)

    # ── Public API ───────────────────────────────────────────────────────────

    def connect_to(self, host: str, port: int) -> None:
        """Initiate a non-blocking connection to host:port."""
        self._socket.connectToHost(host, port)
        self._timeout.start()
        self.connecting.emit()

    def abort(self) -> None:
        """Abort a pending or active connection immediately."""
        self._timeout.stop()
        self._socket.abort()

    def disconnect_from(self) -> None:
        """Close the connection gracefully."""
        self._timeout.stop()
        self._socket.disconnectFromHost()

    def send(self, data: bytes) -> None:
        """Write raw bytes to the socket and flush immediately (no-op if not connected)."""
        if self.is_connected:
            self._socket.write(data)
            self._socket.flush()

    @property
    def is_connected(self) -> bool:
        """Return True when the socket is in the ConnectedState."""
        return self._socket.state() == QAbstractSocket.SocketState.ConnectedState

    @property
    def is_connecting(self) -> bool:
        """Return True while a connection attempt is in progress."""
        return self._socket.state() == QAbstractSocket.SocketState.ConnectingState

    # ── Internals ────────────────────────────────────────────────────────────

    def _on_connected(self) -> None:
        self._timeout.stop()
        self.connected.emit()

    def _on_timeout(self) -> None:
        self._socket.abort()
        self.error.emit("Tiempo de conexión agotado (5 s)")

    def _on_error(self, _: QAbstractSocket.SocketError) -> None:
        """Forward the socket error as a human-readable string."""
        self._timeout.stop()
        self.error.emit(self._socket.errorString())

    def _on_data(self) -> None:
        """Read all pending bytes and emit them as a single data_received signal."""
        self.data_received.emit(bytes(self._socket.readAll()))
