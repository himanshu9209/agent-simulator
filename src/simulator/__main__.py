"""
Entry point: python -m simulator [--config path/to/config.yaml]
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from simulator.config import load_config
from simulator.telemetry.emitter import build_tracer_provider, get_tracer
from simulator.telemetry.metrics import SimulatorMetrics, build_meter_provider


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent Simulator")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/default.yaml"),
        help="Path to YAML config file (default: config/default.yaml)",
    )
    return parser.parse_args()


async def _main(config_path: Path) -> None:
    from simulator.core import run

    config = load_config(config_path)
    tracer_provider = build_tracer_provider(config)
    meter_provider = build_meter_provider(config)
    tracer = get_tracer()
    sim_metrics = SimulatorMetrics.from_config(config)

    print(
        f"[simulator] starting — concurrency={config.simulator.concurrency} "
        f"duration={config.simulator.run_duration_seconds}s "
        f"clock_multiplier={config.simulator.clock_multiplier}x "
        f"profiles={list(config.agent_profiles)}"
    )

    await run(config, tracer, sim_metrics)

    print("[simulator] run complete — flushing telemetry...")
    tracer_provider.force_flush()
    meter_provider.force_flush(timeout_millis=10_000)
    meter_provider.shutdown()
    print("[simulator] done.")


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_main(args.config))
