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
from math import ceil

from PySide6.QtCore import QDateTime, QObject, QTimer, Signal

from comms.link_stats import LinkStats
from comms.protocol import (
    ACTUATORS,
    REINIT,
    SENSORS,
    Cmd,
    ErrCode,
    Resp,
    error_code,
    is_error,
    parse_temp_limits,
    parse_value,
)
from config.polling import (
    FW_APP_TICK_MS,
    FW_SM_TICK_MS,
    LINK_STATS_WINDOW,
    MAX_IN_FLIGHT_COMMANDS,
    PENDING_TTL_MS,
    SAMPLE_PERIOD_HEADROOM,
    SENSOR_POLL_INTERVAL_MS,
    STATE_POLL_INTERVAL_MS,
)
from models import Device, Sensor
from network.tcp_client import TcpClient



@dataclass
class _Pending:
    """A command awaiting its reply — written to the wire, or held until a command slot frees.

    ``resolve(line)`` returns True if the line belonged to this command (and was
    handled), False if it should be left for a later listener. ``quiet`` marks
    poll traffic so it is kept out of the interactive log.
    """

    resolve: Callable[[str], bool]
    line: str = field(default="")  # the command text, written when a slot is free
    quiet: bool = field(default=False)
    is_poll: bool = field(default=False)  # counted in _polls_outstanding, so a drop must uncount it
    sent: bool = field(default=False)  # written to the wire (occupies one of the PLC's command slots)
    sent_ms: int = field(default=0)  # when the command was written, for the reply latency
    deadline_ms: int = field(default=0)  # after this, with no reply, the command is abandoned


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
    sensor_reinit_result = Signal(object, bool)  # (Sensor, ok) — reply to a SYST:REINIT command
    temp_control_changed = Signal(bool)  # (on) — PLC's control state after a TEMP:SET:IN toggle
    temp_limits_received = Signal(object)  # (TempLimits | None) — reply to TEMP:LIM?; None if the PLC refused it

    # Diagnostic / init events.
    state_received = Signal(str)  # reply to a STATE? query — carries the raw state name string

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the transport, timer, and wire signals into protocol handling."""
        super().__init__(parent)
        self._tcp = TcpClient(self)
        self._rx_buffer = b""
        self._pending: deque[_Pending] = deque()
        self._polls_outstanding = 0
        self._round_start_ms = 0
        self._stats = LinkStats(LINK_STATS_WINDOW, self._now_ms())

        # Sensors currently included in each poll round.  Starts empty; each
        # sensor is added only when the user clicks its card to enable polling.
        self._enabled_sensors: set[Sensor] = set()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(SENSOR_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_sensors)

        # Periodic STATE? poll — started by the owner (MainWindow) after the init
        # sequence completes; stopped automatically on disconnect.
        self._state_poll_timer = QTimer(self)
        self._state_poll_timer.setInterval(STATE_POLL_INTERVAL_MS)
        self._state_poll_timer.timeout.connect(self.query_state)

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

    # ── Sampling period and link statistics ────────────────────────────────────

    @property
    def sample_period_ms(self) -> int:
        """Current sensor sampling period (ms): one poll round per period."""
        return self._poll_timer.interval()

    def set_sample_period(self, period_ms: int) -> None:
        """Change the sampling period, effective immediately, and start a fresh statistics window."""
        self._poll_timer.setInterval(period_ms)
        self.reset_link_stats()

    @staticmethod
    def recommended_min_period_ms() -> int:
        """Fastest period the firmware is expected to sustain with every sensor enabled.

        A whole round fits in the firmware's in-flight window, so it costs one worst-case round
        trip (two App ticks and two SM ticks), and SAMPLE_PERIOD_HEADROOM leaves room for the
        state/actuator queries sharing the link. An estimate — the bench test with
        :meth:`link_stats_summary` gives the real limit.
        """
        return ceil(2 * (FW_APP_TICK_MS + FW_SM_TICK_MS) * SAMPLE_PERIOD_HEADROOM)

    def link_stats_summary(self) -> str:
        """One log line describing link health since the last reset (connect or period change)."""
        return self._stats.summary(self._now_ms(), self.sample_period_ms)

    def reset_link_stats(self) -> None:
        """Start a new statistics window now."""
        self._stats.reset(self._now_ms())

    # ── Sending ──────────────────────────────────────────────────────────────

    def set_actuator(self, dev: Device, on: bool) -> None:
        """Command an actuator on/off and queue the command for reply confirmation.

        The state change is not reported until the PLC echoes the expected reply,
        which then surfaces as :attr:`actuator_changed`; a rejection surfaces as
        :attr:`actuator_rejected`.
        """
        spec = ACTUATORS[dev]
        expected = spec.on_resp if on else spec.off_resp
        self._request(spec.on_cmd if on else spec.off_cmd, partial(self._resolve_actuator, dev, on, expected))

    def send_event(self, evt: str) -> bool:
        """Queue a state-machine event line (``EVT:…``) like a command. Returns False if not connected."""
        return self._request(evt, self._resolve_event)

    def send_raw(self, text: str) -> bool:
        """Send an arbitrary line typed in the log terminal. Returns False if not connected.

        Commands and events are queued like any other, so the reply is matched to the line (and
        shown in the log) instead of being taken by whichever poll happens to be waiting.
        """
        return self._request(text.strip(), self._resolve_raw)

    def set_sensor_enabled(self, sensor: Sensor, enabled: bool) -> None:
        """Include or exclude a sensor from the periodic poll round."""
        if enabled:
            self._enabled_sensors.add(sensor)
        else:
            self._enabled_sensors.discard(sensor)

    def query_state(self) -> bool:
        """Send a STATE? query; the reply surfaces as :attr:`state_received`.

        Returns False if not connected.  Multiple back-to-back calls are safe:
        each one appends a resolver to the FIFO queue, so replies are matched
        in order.
        """
        return self._request(Cmd.STATE, self._resolve_state, quiet=True)

    def query_all_actuator_states(self) -> bool:
        """Query the state of all actuators and emit :attr:`actuator_changed` for each.

        Returns False if not connected. Multiple back-to-back calls are safe.
        """
        if not self._tcp.is_connected:
            return False

        queries = [
            (Device.HEATER, Cmd.HEAT_STATE),
            (Device.PUMP, Cmd.PUMP_STATE),
            (Device.MIXER, Cmd.MIX_STATE),
            (Device.VALVE1, Cmd.valve_state(1)),
        ]

        for dev, query in queries:
            self._request(query, partial(self._resolve_actuator_state, dev), quiet=True)

        return True

    def reinit_sensor(self, sensor: Sensor) -> bool:
        """Ask the PLC to re-initialise *sensor*; the reply surfaces as :attr:`sensor_reinit_result`.

        Returns False if not connected. Sent non-quiet so the operator sees the
        recovery attempt in the log terminal.
        """
        return self._request(REINIT[sensor], partial(self._resolve_reinit, sensor))

    def set_temperature_control(self, value: float) -> bool:
        """Send the inlet setpoint, which the PLC treats as a toggle, and correlate its reply.

        The PLC answers with the resulting control state (ON/OFF), so the command needs a resolver
        like any other — an unclaimed reply would otherwise be offered to whatever command happens
        to be at the head of the queue.
        """
        return self._request(Cmd.temp_set_in(value), self._resolve_temp_control)

    def query_temp_limits(self) -> bool:
        """Ask the PLC for its temperature limits; the reply surfaces as :attr:`temp_limits_received`."""
        return self._request(Cmd.TEMP_LIM, self._resolve_temp_limits, quiet=True)

    def probe_sensors(self, on_done: Callable[[dict[Sensor, bool]], None]) -> bool:
        """Query every sensor once and report pass/fail per sensor via *on_done*.

        Sends one MEAS query per sensor through the normal FIFO correlator.
        *on_done* is called with a ``{Sensor: bool}`` dict once all issued
        queries have been answered (True = valid reading, False = error/fault).
        Returns False if not connected or no queries could be issued.
        """
        if not self._tcp.is_connected:
            return False

        results: dict[Sensor, bool] = {}
        # Use a one-element list so the inner closure can observe the final count.
        pending_count: list[int] = [0]

        def check_done() -> None:
            if len(results) >= pending_count[0] > 0:
                on_done(dict(results))

        for sensor, query in SENSORS.items():

            def make_resolver(s: Sensor) -> Callable[[str], bool]:
                def resolve(line: str) -> bool:
                    results[s] = not is_error(line) and (parse_value(line) is not None or line in (Resp.HIGH, Resp.LOW))
                    check_done()
                    return True

                return resolve

            if self._request(query, make_resolver(sensor), quiet=True):
                pending_count[0] += 1

        return pending_count[0] > 0

    def start_state_polling(self) -> None:
        """Start the periodic STATE? poll (interval = ``config.polling.STATE_POLL_INTERVAL_MS``)."""
        self._state_poll_timer.start()

    def _request(self, line: str, resolve: Callable[[str], bool], quiet: bool = False, is_poll: bool = False) -> bool:
        """Queue a command and the resolver for its reply; write it now if a PLC command slot is free.

        Returns False if not connected. Commands are written in queue order and at most
        MAX_IN_FLIGHT_COMMANDS wait for a reply at once, so the PLC never has to refuse one
        with BUSY; the rest are written by :meth:`_pump` as replies come back.
        """
        if not self._tcp.is_connected:
            return False
        self._pending.append(_Pending(resolve, line=line, quiet=quiet, is_poll=is_poll))
        self._pump()
        return True

    def _pump(self) -> None:
        """Write held commands, oldest first, while the PLC has a free command slot."""
        in_flight = sum(1 for p in self._pending if p.sent)
        for p in self._pending:
            if in_flight >= MAX_IN_FLIGHT_COMMANDS:
                return
            if p.sent:
                continue
            if not self._send_line(p.line, quiet=p.quiet):
                return
            now = self._now_ms()
            p.sent, p.sent_ms, p.deadline_ms = True, now, now + PENDING_TTL_MS
            in_flight += 1

    @staticmethod
    def _now_ms() -> int:
        """Wall-clock milliseconds, the time base for deadlines, latencies and statistics."""
        return int(QDateTime.currentMSecsSinceEpoch())

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
        # Replies only expire when something arrives; if the PLC went silent, this tick does it.
        self._expire_overdue(self._now_ms())
        if self._polls_outstanding > 0:
            # The PLC has not answered the previous round yet: it is not keeping up with this period.
            self._stats.on_round_skipped()
            return
        self._round_start_ms = self._now_ms()
        for sensor, query in SENSORS.items():
            if sensor not in self._enabled_sensors:
                continue
            if self._request(query, partial(self._resolve_sensor, sensor), quiet=True, is_poll=True):
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
        now = self._now_ms()
        if error_code(line) == ErrCode.BUSY:
            self._stats.on_busy()
        self._expire_overdue(now)

        if self._pending and self._pending[0].sent:
            head = self._pending[0]
            if head.resolve(line):
                self._stats.on_reply(now - head.sent_ms)
                self._pending.popleft()
                if not self._pending:
                    # Nothing outstanding: re-assert the invariant so a dropped
                    # poll reply cannot stall _poll_sensors forever.
                    self._polls_outstanding = 0
                self._pump()  # a slot freed: write the next held command
                if not head.quiet:
                    self.line_received.emit(line)
                return
            # The oldest pending command did not claim this line: it arrived late or out of order.
            self._stats.on_unmatched()
        self.line_received.emit(line)

    def _expire_overdue(self, now: int) -> None:
        """Drop commands whose reply is overdue, then write any commands that were held back.

        Runs on every received line and on every sampling tick, so a PLC that stops answering
        altogether still frees the queue instead of leaving every later round skipped.
        """
        dropped_any = False
        # Only written commands can time out; the head is always written when anything is.
        while self._pending and self._pending[0].sent and self._pending[0].deadline_ms <= now:
            # A reply was lost: abandoning the entry keeps the queue moving instead of letting every
            # later reply be offered to a resolver that will never match. A dropped poll must also be
            # uncounted, or _poll_sensors would skip every round from here on.
            dropped = self._pending.popleft()
            dropped_any = True
            self._stats.on_timeout()
            if dropped.is_poll and self._polls_outstanding > 0:
                self._polls_outstanding -= 1
            if not self._pending:
                self._polls_outstanding = 0
        if dropped_any:
            self._pump()

    @staticmethod
    def _resolve_raw(line: str) -> bool:
        """Accept whatever reply comes back for a terminal command; the log shows it as it arrived."""
        return True

    @staticmethod
    def _resolve_event(line: str) -> bool:
        """Consume OK or an error; a rejection shows in the log and the STATE? poll reconciles."""
        return line == Resp.OK or is_error(line)

    def _resolve_state(self, line: str) -> bool:
        """Emit the reply as the FSM state name; consume an error reply without reporting a state.

        An error (e.g. -106 BUSY) says nothing about the PLC's state, so the last known state
        stands and the next periodic STATE? asks again.
        """
        if not is_error(line):
            self.state_received.emit(line)
        return True

    def _resolve_reinit(self, sensor: Sensor, line: str) -> bool:
        """Confirm on Resp.OK, fail on an error reply, ignore anything else."""
        if line == Resp.OK:
            self.sensor_reinit_result.emit(sensor, True)
            return True
        if is_error(line):
            self.sensor_reinit_result.emit(sensor, False)
            return True
        return False

    def _resolve_temp_control(self, line: str) -> bool:
        """Report the control state the PLC settled on; consume an error without reporting one."""
        if line == Resp.ON:
            self.temp_control_changed.emit(True)
            return True
        if line == Resp.OFF:
            self.temp_control_changed.emit(False)
            return True
        if is_error(line):
            return True
        return False

    def _resolve_temp_limits(self, line: str) -> bool:
        """Report the PLC's limits; an error (e.g. older firmware without TEMP:LIM?) reports None."""
        if is_error(line):
            self.temp_limits_received.emit(None)
            return True
        limits = parse_temp_limits(line)
        if limits is None:
            return False
        self.temp_limits_received.emit(limits)
        return True

    def _resolve_actuator(self, dev: Device, on: bool, expected: str, line: str) -> bool:
        """Confirm on the expected reply, reject on an error, ignore anything else."""
        if line == expected:
            self.actuator_changed.emit(dev, on)
            return True
        if is_error(line):
            self.actuator_rejected.emit(dev)
            return True
        return False

    def _resolve_actuator_state(self, dev: Device, line: str) -> bool:
        """Resolve a state query response and emit the actual state.

        Maps ON/OPEN to True, OFF/CLOSED to False.  An error reply is consumed
        without touching the indicator — the SCADA never assumes a state the PLC
        did not report, and the next poll re-asks.  Consuming it is what keeps
        the FIFO correlator from jamming on its head entry.
        """
        if line in (Resp.ON, Resp.OPEN):
            self.actuator_changed.emit(dev, True)
            return True
        if line in (Resp.OFF, Resp.CLOSED):
            self.actuator_changed.emit(dev, False)
            return True
        if is_error(line):
            return True
        return False

    def _resolve_sensor(self, sensor: Sensor, line: str) -> bool:
        """Consume a numeric reading, a HIGH/LOW status or an error; ignore anything else."""
        if error_code(line) == ErrCode.BUSY:
            # Not a sensor fault: the PLC had no free slot. Keep the last reading; the next round re-asks.
            self._on_poll_answered()
            return True
        if is_error(line):
            self._on_poll_answered()
            self.sensor_fault.emit(sensor)
            return True
        if parse_value(line) is not None or line in (Resp.HIGH, Resp.LOW):
            self._on_poll_answered()
            self.sensor_updated.emit(sensor, line)
            return True
        return False

    def _on_poll_answered(self) -> None:
        """Count one poll reply; the last reply of a round closes it in the statistics."""
        self._polls_outstanding -= 1
        if self._polls_outstanding == 0:
            self._stats.on_round_done(self._now_ms() - self._round_start_ms)

    # ── Internals: lifecycle ────────────────────────────────────────────────────

    def _on_connected(self) -> None:
        self.reset_link_stats()
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
        self._state_poll_timer.stop()
        self._pending.clear()
        self._rx_buffer = b""
        self._polls_outstanding = 0
        self._enabled_sensors = set()
