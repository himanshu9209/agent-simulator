from __future__ import annotations

import asyncio
import random
import time
from contextvars import copy_context

from opentelemetry import trace

from simulator.behavior.distributions import Distributions
from simulator.behavior.engine import run_agent_session
from simulator.clock import ClockController
from simulator.config import AgentProfile, RootConfig
from simulator.scenarios.engine import ScenarioEngine
from simulator.telemetry.metrics import SimulatorMetrics


def _select_profile(
    profiles: dict[str, AgentProfile],
    rng: random.Random,
) -> tuple[str, AgentProfile]:
    """Pick a profile name+object weighted by mix_weight."""
    names = list(profiles.keys())
    weights = [profiles[n].mix_weight for n in names]
    name = rng.choices(names, weights=weights, k=1)[0]
    return name, profiles[name]


async def _run_session_task(
    session_index: int,
    profile_name: str,
    profile: AgentProfile,
    tracer: trace.Tracer,
    clock: ClockController,
    base_seed: int | None,
    scenario_engine: ScenarioEngine,
    metrics: SimulatorMetrics,
) -> None:
    seed = None if base_seed is None else base_seed + session_index
    dist = Distributions.from_seed(seed)
    scenario = scenario_engine.select(dist)
    await run_agent_session(
        profile_name=profile_name,
        profile=profile,
        dist=dist,
        tracer=tracer,
        clock=clock,
        scenario=scenario,
        metrics=metrics,
    )


async def run(config: RootConfig, tracer: trace.Tracer, metrics: SimulatorMetrics) -> None:
    clock = ClockController(config.simulator.clock_multiplier)
    sem = asyncio.Semaphore(config.simulator.concurrency)
    rng = random.Random(config.simulator.random_seed)
    scenario_engine = ScenarioEngine(config.scenarios)

    deadline = time.monotonic() + config.simulator.run_duration_seconds / clock.multiplier
    session_index = 0
    pending: set[asyncio.Task] = set()

    async def launch_one() -> None:
        nonlocal session_index
        profile_name, profile = _select_profile(config.agent_profiles, rng)
        idx = session_index
        session_index += 1

        async def _guarded() -> None:
            async with sem:
                ctx = copy_context()
                await ctx.run(
                    _run_session_task,
                    idx,
                    profile_name,
                    profile,
                    tracer,
                    clock,
                    config.simulator.random_seed,
                    scenario_engine,
                    metrics,
                )

        task = asyncio.create_task(_guarded())
        pending.add(task)
        task.add_done_callback(pending.discard)

    # Seed the pool up to concurrency
    for _ in range(config.simulator.concurrency):
        if time.monotonic() < deadline:
            await launch_one()

    # Keep the pool full until the deadline
    while time.monotonic() < deadline and pending:
        done, _ = await asyncio.wait(pending, timeout=0.1)
        for task in done:
            if task.exception():
                # Log but don't crash the pool on a single session error
                print(f"[core] session error: {task.exception()}")
            if time.monotonic() < deadline:
                await launch_one()

    # Wait for in-flight sessions to finish
    if pending:
        await asyncio.wait(pending)
