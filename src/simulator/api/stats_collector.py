"""
simulator/api/stats_collector.py
Extends SimulatorMetrics with in-process readable counters.

The RunManager creates one StatsCollector per run and reads from it via
snapshot() to drive the WebSocket live-stats stream.  All counter updates
are thread-safe via a single lock.
"""
from __future__ import annotations

import threading

from opentelemetry import metrics

from simulator.telemetry.metrics import SimulatorMetrics


class StatsCollector(SimulatorMetrics):
    """SimulatorMetrics subclass that also maintains readable Python counters."""

    def __init__(self, meter: metrics.Meter) -> None:
        super().__init__(meter)
        self._lock = threading.Lock()
        self._sessions_completed: int = 0
        self._sessions_error: int = 0
        self._total_cost_usd: float = 0.0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._tool_calls: int = 0

    # ------------------------------------------------------------------
    # Override record methods to also bump internal counters
    # ------------------------------------------------------------------

    def record_session_completed(self, profile: str) -> None:
        super().record_session_completed(profile)
        with self._lock:
            self._sessions_completed += 1

    def record_session_end(
        self, duration_s: float, profile: str, scenario: str | None, error: bool
    ) -> None:
        super().record_session_end(duration_s, profile, scenario, error)
        if error:
            with self._lock:
                self._sessions_error += 1

    def record_cost(self, session_cost_usd: float, model: str, profile: str) -> None:
        super().record_cost(session_cost_usd, model, profile)
        with self._lock:
            self._total_cost_usd += session_cost_usd

    def record_tokens(
        self, input_tokens: int, output_tokens: int, model: str, profile: str
    ) -> None:
        super().record_tokens(input_tokens, output_tokens, model, profile)
        with self._lock:
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens

    def record_tool_call(self, tool_name: str, profile: str) -> None:
        super().record_tool_call(tool_name, profile)
        with self._lock:
            self._tool_calls += 1

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Return a thread-safe copy of the current counters."""
        with self._lock:
            return {
                "sessions_completed": self._sessions_completed,
                "sessions_error": self._sessions_error,
                "total_cost_usd": round(self._total_cost_usd, 6),
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "tool_calls": self._tool_calls,
            }

    @classmethod
    def from_config(cls, config) -> "StatsCollector":  # noqa: ANN001
        meter = metrics.get_meter("agent-simulator")
        return cls(meter)
