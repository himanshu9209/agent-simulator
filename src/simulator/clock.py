from __future__ import annotations

import asyncio
import time


class ClockController:
    """Scales asyncio sleep durations by a multiplier so simulated time runs faster than wall clock."""

    def __init__(self, clock_multiplier: float) -> None:
        if clock_multiplier <= 0:
            raise ValueError(f"clock_multiplier must be > 0, got {clock_multiplier}")
        self._multiplier = clock_multiplier
        self._real_start_ns: int = time.time_ns()

    @property
    def multiplier(self) -> float:
        return self._multiplier

    async def scaled_sleep(self, real_seconds: float) -> None:
        """Sleep for real_seconds / clock_multiplier wall-clock seconds."""
        await asyncio.sleep(real_seconds / self._multiplier)

    def simulated_time_ns(self) -> int:
        """
        Current simulated time in nanoseconds.

        Advances clock_multiplier times faster than wall-clock time.
        """
        elapsed_real_ns = time.time_ns() - self._real_start_ns
        return self._real_start_ns + int(elapsed_real_ns * self._multiplier)
