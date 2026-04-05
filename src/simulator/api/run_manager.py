"""
simulator/api/run_manager.py
RunManager — manages the simulator run lifecycle: start, stop, status.

One instance lives on app.state for the lifetime of the FastAPI process.
The simulator runs as an asyncio background task in the same event loop
as uvicorn, so no extra threads are needed.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional

from simulator.api.stats_collector import StatsCollector
from simulator.config import RootConfig


class RunManager:
    """Controls one simulator run at a time.  Thread-safe via asyncio semantics."""

    def __init__(self) -> None:
        self.status: str = "idle"
        self._cfg: Optional[RootConfig] = None
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._stats: Optional[StatsCollector] = None
        self._error: Optional[str] = None
        self._tracer_provider = None
        self._meter_provider = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    async def start(self, cfg: RootConfig) -> None:
        """Schedule the simulator as a background asyncio task."""
        if self.is_running:
            raise RuntimeError("A simulation is already running")
        self._cfg = cfg
        self._start_time = time.time()
        self._stop_time = None
        self._error = None
        self._stats = None
        self.status = "running"
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_simulation())

    async def stop(self) -> None:
        """Signal the running simulation to stop gracefully."""
        if self._stop_event is not None and self.is_running:
            self.status = "stopping"
            self._stop_event.set()

    def get_status(self) -> dict:
        """Return a dict whose keys match RunStatusResponse fields."""
        elapsed = 0.0
        if self._start_time is not None:
            end = self._stop_time if self._stop_time is not None else time.time()
            elapsed = end - self._start_time

        stats = self._stats.snapshot() if self._stats is not None else {}

        return {
            "status": self.status,
            "started_at": (
                datetime.fromtimestamp(self._start_time).isoformat()
                if self._start_time is not None
                else None
            ),
            "elapsed_seconds": round(elapsed, 1),
            "active_agents": (
                self._cfg.simulator.concurrency
                if self._cfg is not None and self.is_running
                else 0
            ),
            "sessions_completed": stats.get("sessions_completed", 0),
            "sessions_error": stats.get("sessions_error", 0),
            "total_cost_usd": stats.get("total_cost_usd", 0.0),
            "total_input_tokens": stats.get("total_input_tokens", 0),
            "total_output_tokens": stats.get("total_output_tokens", 0),
            "tool_calls": stats.get("tool_calls", 0),
            "error": self._error,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_simulation(self) -> None:
        """
        Background task: build OTel providers, run core.run(), tear down.
        Sets self.status to 'idle' on clean exit or 'error' on exception.
        """
        try:
            import os

            from simulator.telemetry.emitter import build_tracer_provider, get_tracer
            from simulator.telemetry.metrics import build_meter_provider
            from simulator.core import run

            # Allow the Docker Compose environment to override the OTLP
            # endpoint without editing config files.  The env var is set to
            # http://otel-collector:4317 in the simulator-api service so the
            # in-process simulator can reach the collector over the Docker
            # bridge network rather than trying localhost:4317.
            cfg = self._cfg
            otlp_override = os.environ.get("SIMULATOR_OTLP_ENDPOINT")
            if otlp_override:
                cfg = cfg.model_copy(
                    update={
                        "telemetry": cfg.telemetry.model_copy(
                            update={"exporter_endpoint": otlp_override}
                        )
                    }
                )

            self._tracer_provider = build_tracer_provider(cfg)
            self._meter_provider = build_meter_provider(cfg)
            tracer = get_tracer()
            self._stats = StatsCollector.from_config(cfg)

            run_task = asyncio.create_task(run(cfg, tracer, self._stats))
            stop_task = asyncio.create_task(self._stop_event.wait())

            done, _ = await asyncio.wait(
                [run_task, stop_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Stop requested before natural completion
            if run_task not in done:
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass
            elif run_task.exception() is not None:
                raise run_task.exception()  # type: ignore[misc]

            if stop_task not in done:
                stop_task.cancel()

        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self.status = "error"
        else:
            self.status = "idle"
        finally:
            self._stop_time = time.time()
            if self._tracer_provider is not None:
                try:
                    self._tracer_provider.force_flush()
                    self._tracer_provider.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            if self._meter_provider is not None:
                try:
                    self._meter_provider.force_flush(timeout_millis=5_000)
                    self._meter_provider.shutdown()
                except Exception:  # noqa: BLE001
                    pass
