"""High-level PLC client: protocol logic on top of the raw TCP transport.

Wraps :class:`TcpClient` and owns everything protocol-related — line framing,
the reply-correlation queue, actuator confirmation and periodic sensor polling —
so the UI deals only in domain terms (devices, sensors) and never touches the
wire format.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from PySide6.QtCore import QObject, QTimer, Signal

from comms.protocol import ACTUATORS, SENSORS, Device, Resp, Sensor, is_error, parse_value
from network.tcp_client import TcpClient

_POLL_INTERVAL_MS = 1000


@dataclass
class _Pending:
    """A command awaiting its reply.

    ``resolve(line)`` returns True if the line belonged to this command (and was
    handled), False if it should be left for a later listener. ``quiet`` marks
    poll traffic so it is kept out of the interactive log.
    """

    resolve: Callable[[str], bool]
    quiet: bool = field(default=False)


class PlcClient(QObject):
    """Stateful PLC session: sends commands and emits domain events from replies."""

    # Connection lifecycle (re-exposed from the underlying TcpClient).
    connecting = Signal()
    connected = Signal()
    disconnected = Signal()
    error = Signal(str)

    # Domain events.
    command_sent = Signal(str)  # an interactive line was written to the PLC
    line_received = Signal(str)  # an interactive reply line arrived from the PLC
    actuator_changed = Signal(object, bool)  # (Device, on) — PLC confirmed the new state
    actuator_rejected = Signal(object)  # (Device) — PLC refused the command
    sensor_updated = Signal(object, str)  # (Sensor, value) — fresh reading as a display string
    sensor_fault = Signal(object)  # (Sensor) — sensor reply was an error

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the transport, timer, and wire signals into protocol handling."""
        super().__init__(parent)
        self._tcp = TcpClient(self)
        self._rx_buffer = b""
        self._pending: deque[_Pending] = deque()
        self._polls_outstanding = 0

        # Sensors currently included in each poll round.  Starts empty; each
        # sensor is added only when the user clicks its card to enable polling.
        self._enabled_sensors: set[Sensor] = set()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_sensors)

        self._tcp.connecting.connect(self.connecting)
        self._tcp.connected.connect(self._on_connected)
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
        which then surfaces as :attr:`actuator_changed`; a rejection surfaces as
        :attr:`actuator_rejected`.
        """
        spec = ACTUATORS[dev]
        if not self._send_line(spec.on_cmd if on else spec.off_cmd):
            return
        expected = spec.on_resp if on else spec.off_resp
        self._pending.append(_Pending(partial(self._resolve_actuator, dev, on, expected)))

    def send_event(self, evt: str) -> bool:
        """Send a state-machine event line (``EVT:…``). Returns False if not connected."""
        return self._send_line(evt)

    def send_raw(self, text: str) -> bool:
        """Send an arbitrary line (e.g. from the log terminal). Returns False if not connected."""
        return self._send_line(text)

    def set_sensor_enabled(self, sensor: Sensor, enabled: bool) -> None:
        """Include or exclude a sensor from the periodic poll round."""
        if enabled:
            self._enabled_sensors.add(sensor)
        else:
            self._enabled_sensors.discard(sensor)

    # ── Internals: sending ─────────────────────────────────────────────────────

    def _send_line(self, line: str, quiet: bool = False) -> bool:
        """Write a newline-terminated line; emit command_sent unless quiet (poll traffic)."""
        if not self._tcp.is_connected:
            return False
        self._tcp.send((line + "\n").encode())
        if not quiet:
            self.command_sent.emit(line)
        return True

    def _poll_sensors(self) -> None:
        """Query each enabled sensor once. Skips a round while the previous one is still draining."""
        if self._polls_outstanding > 0:
            return
        for sensor, query in SENSORS.items():
            if sensor not in self._enabled_sensors:
                continue
            if self._send_line(query, quiet=True):
                self._pending.append(_Pending(partial(self._resolve_sensor, sensor), quiet=True))
                self._polls_outstanding += 1

    # ── Internals: receiving ────────────────────────────────────────────────────

    def _on_data(self, data: bytes) -> None:
        """Accumulate bytes and dispatch each complete (newline-terminated) line."""
        self._rx_buffer += data
        while b"\n" in self._rx_buffer:
            raw, self._rx_buffer = self._rx_buffer.split(b"\n", 1)
            line = raw.decode(errors="replace").strip()
            if line:
                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        """Resolve a reply against the head of the queue, then surface it for logging.

        Matched FIFO: the head entry's resolver consumes the line if it belongs to
        that command; otherwise the line is left for listeners (e.g. log-terminal
        queries) without disturbing the queue. Poll replies are resolved quietly.
        """
        if self._pending:
            head = self._pending[0]
            if head.resolve(line):
                self._pending.popleft()
                if not head.quiet:
                    self.line_received.emit(line)
                return
        self.line_received.emit(line)

    def _resolve_actuator(self, dev: Device, on: bool, expected: str, line: str) -> bool:
        """Confirm on the expected reply, reject on an error, ignore anything else."""
        if line == expected:
            self.actuator_changed.emit(dev, on)
            return True
        if is_error(line):
            self.actuator_rejected.emit(dev)
            return True
        return False

    def _resolve_sensor(self, sensor: Sensor, line: str) -> bool:
        """Consume a numeric reading, a HIGH/LOW status or an error; ignore anything else."""
        if is_error(line):
            self._polls_outstanding -= 1
            self.sensor_fault.emit(sensor)
            return True
        if parse_value(line) is not None or line in (Resp.HIGH, Resp.LOW):
            self._polls_outstanding -= 1
            self.sensor_updated.emit(sensor, line)
            return True
        return False

    # ── Internals: lifecycle ────────────────────────────────────────────────────

    def _on_connected(self) -> None:
        self._poll_timer.start()
        self.connected.emit()

    def _on_disconnected(self) -> None:
        self._reset_session()
        self.disconnected.emit()

    def _on_error(self, msg: str) -> None:
        self._reset_session()
        self.error.emit(msg)

    def _reset_session(self) -> None:
        """Stop polling and drop in-flight state from the previous session."""
        self._poll_timer.stop()
        self._pending.clear()
        self._rx_buffer = b""
        self._polls_outstanding = 0
        self._enabled_sensors = set()
