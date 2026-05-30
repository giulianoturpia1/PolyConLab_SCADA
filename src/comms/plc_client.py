"""High-level PLC client: protocol logic on top of the raw TCP transport.

Wraps :class:`TcpClient` and owns everything protocol-related — line framing,
the actuator confirmation queue and reply correlation — so the UI deals only in
domain terms (devices, confirmations) and never touches the wire format.
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, Signal

from comms.protocol import ACTUATORS, Device, is_error
from network.tcp_client import TcpClient


class PlcClient(QObject):
    """Stateful PLC session: sends commands and emits domain events from replies."""

    # Connection lifecycle (re-exposed from the underlying TcpClient).
    connecting = Signal()
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    # Domain events.
    command_sent = Signal(str)  # a line was written to the PLC
    line_received = Signal(str)  # a complete reply line arrived from the PLC
    actuator_changed = Signal(object, bool)  # (Device, on) — PLC confirmed the new state
    actuator_rejected = Signal(object)  # (Device) — PLC refused the command

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the transport and wire its signals into protocol handling."""
        super().__init__(parent)
        self._tcp = TcpClient(self)
        self._rx_buffer = b""
        self._pending: deque[tuple[Device, bool, str]] = deque()

        self._tcp.connecting.connect(self.connecting)
        self._tcp.connected.connect(self.connected)
        self._tcp.disconnected.connect(self._on_disconnected)
        self._tcp.error.connect(self._on_error)
        self._tcp.data_received.connect(self._on_data)

    # ── Connection control ───────────────────────────────────────────────────

    def connect_to(self, host: str, port: int) -> None:
        """Initiate a connection, discarding any leftover state from a prior session."""
        self._reset_session()
        self._tcp.connect_to(host, port)

    def disconnect_from(self) -> None:
        """Close the connection gracefully."""
        self._tcp.disconnect_from()

    def abort(self) -> None:
        """Abort a pending or active connection."""
        self._tcp.abort()

    @property
    def is_connected(self) -> bool:
        """True while the socket is connected."""
        return self._tcp.is_connected

    @property
    def is_connecting(self) -> bool:
        """True while a connection attempt is in progress."""
        return self._tcp.is_connecting

    # ── Sending ──────────────────────────────────────────────────────────────

    def set_actuator(self, dev: Device, on: bool) -> None:
        """Command an actuator on/off and queue the command for reply confirmation.

        The state change is not reported until the PLC echoes the expected reply,
        which then surfaces as :attr:`actuator_changed`. A rejection surfaces as
        :attr:`actuator_rejected`.
        """
        spec = ACTUATORS[dev]
        if not self._send_line(spec.on_cmd if on else spec.off_cmd):
            return
        self._pending.append((dev, on, spec.on_resp if on else spec.off_resp))

    def send_event(self, evt: str) -> bool:
        """Send a state-machine event line (``EVT:…``). Returns False if not connected."""
        return self._send_line(evt)

    def send_raw(self, text: str) -> bool:
        """Send an arbitrary line (e.g. from the log terminal). Returns False if not connected."""
        return self._send_line(text)

    # ── Internals ────────────────────────────────────────────────────────────

    def _send_line(self, line: str) -> bool:
        """Write a single newline-terminated line; emit command_sent on success."""
        if not self._tcp.is_connected:
            return False
        self._tcp.send((line + "\n").encode())
        self.command_sent.emit(line)
        return True

    def _on_data(self, data: bytes) -> None:
        """Accumulate bytes and dispatch each complete (newline-terminated) line."""
        self._rx_buffer += data
        while b"\n" in self._rx_buffer:
            raw, self._rx_buffer = self._rx_buffer.split(b"\n", 1)
            line = raw.decode(errors="replace").strip()
            if line:
                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        """Emit the raw line and resolve it against the head of the pending queue.

        Matched FIFO: the head's expected reply confirms its actuator, an error
        reply rejects it, and any other line is left for listeners without
        disturbing the queue.
        """
        self.line_received.emit(line)
        if not self._pending:
            return

        dev, on, expected = self._pending[0]
        if line == expected:
            self._pending.popleft()
            self.actuator_changed.emit(dev, on)
        elif is_error(line):
            self._pending.popleft()
            self.actuator_rejected.emit(dev)

    def _on_disconnected(self) -> None:
        self._reset_session()
        self.disconnected.emit()

    def _on_error(self, msg: str) -> None:
        self._reset_session()
        self.error.emit(msg)

    def _reset_session(self) -> None:
        """Drop in-flight confirmations and partial bytes from the previous session."""
        self._pending.clear()
        self._rx_buffer = b""
