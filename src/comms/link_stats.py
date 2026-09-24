"""Link statistics: how well the PLC keeps up with the SCADA's traffic.

Pure bookkeeping, no Qt: :class:`~comms.plc_client.PlcClient` feeds it every reply, lost
reply, out-of-order line and poll round, and :meth:`LinkStats.summary` turns that into one
log line. Used to find the fastest sampling period the firmware sustains on the bench.
"""

from __future__ import annotations

from collections import deque


class LinkStats:
    """Counters and latency samples for one measurement window (reset on connect or period change)."""

    def __init__(self, window: int, now_ms: int = 0) -> None:
        """Keep the last *window* reply latencies; start counting at *now_ms*."""
        self._window = window
        self.reset(now_ms)

    def reset(self, now_ms: int) -> None:
        """Clear every counter and start a new window at *now_ms*."""
        self._start_ms = now_ms
        self._latencies: deque[int] = deque(maxlen=self._window)
        self._round_ms: deque[int] = deque(maxlen=self._window)
        self.replies = 0
        self.timeouts = 0
        self.unmatched = 0
        self.rounds_done = 0
        self.rounds_skipped = 0

    # ── Events ───────────────────────────────────────────────────────────────

    def on_reply(self, latency_ms: int) -> None:
        """A command got its reply *latency_ms* after it was sent."""
        self.replies += 1
        self._latencies.append(max(latency_ms, 0))

    def on_timeout(self) -> None:
        """A command's reply never arrived and it was dropped from the queue."""
        self.timeouts += 1

    def on_unmatched(self) -> None:
        """A line arrived that the oldest pending command did not accept (late or out of order)."""
        self.unmatched += 1

    def on_round_done(self, duration_ms: int) -> None:
        """Every query of a poll round was answered, *duration_ms* after the round was sent."""
        self.rounds_done += 1
        self._round_ms.append(max(duration_ms, 0))

    def on_round_skipped(self) -> None:
        """A poll tick fired while the previous round was still unanswered, so no round was sent."""
        self.rounds_skipped += 1

    # ── Report ───────────────────────────────────────────────────────────────

    def samples_per_second(self, now_ms: int) -> float:
        """Completed rounds per second since the window started."""
        elapsed_s = (now_ms - self._start_ms) / 1000
        return self.rounds_done / elapsed_s if elapsed_s > 0 else 0.0

    def summary(self, now_ms: int, period_ms: int) -> str:
        """One human-readable line (Spanish, for the log window) describing the current window."""
        elapsed_s = (now_ms - self._start_ms) / 1000
        target = 1000 / period_ms if period_ms > 0 else 0.0
        lat = sorted(self._latencies)
        rnd = list(self._round_ms)
        lat_txt = (
            f"latencia media {sum(lat) / len(lat):.0f} ms, p95 {self._percentile(lat, 0.95)} ms, máx {lat[-1]} ms"
            if lat
            else "latencia: sin respuestas"
        )
        rnd_txt = f"ronda media {sum(rnd) / len(rnd):.0f} ms, máx {max(rnd)} ms" if rnd else "ronda: sin rondas completas"
        return (
            f"Enlace a {period_ms} ms durante {elapsed_s:.0f} s: "
            f"{self.rounds_done} rondas completas, {self.rounds_skipped} salteadas "
            f"-> {self.samples_per_second(now_ms):.2f} muestras/s (objetivo {target:.2f}); "
            f"{rnd_txt}; {lat_txt}; "
            f"{self.timeouts} respuestas perdidas, {self.unmatched} fuera de orden."
        )

    @staticmethod
    def _percentile(sorted_values: list[int], q: float) -> int:
        """Nearest-rank percentile *q* (0..1) of an already sorted, non-empty list."""
        idx = min(len(sorted_values) - 1, max(0, round(q * len(sorted_values)) - 1))
        return sorted_values[idx]
