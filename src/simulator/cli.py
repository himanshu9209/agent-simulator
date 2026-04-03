"""
simulator/cli.py
Main CLI entry point for the agent-simulator package.

Registered as ``agent-simulator`` console script in pyproject.toml so users
can run:

    agent-simulator                          # default config
    agent-simulator -c path/to/config.yaml   # custom config
    agent-simulator --dry-run                # validate + print plan, no spans

Additional flags allow run-time overrides without editing YAML:
    --profile rag_researcher   # single profile only
    --duration 120             # override run_duration_seconds
    --concurrency 10           # override concurrency
    --no-console               # suppress console span output (future use)
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from simulator.config import RootConfig, load_config
from simulator.errors import format_validation_error


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-simulator",
        description="Schema-driven OTel telemetry generator for AI agent observability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  agent-simulator                          # run with default config\n"
            "  agent-simulator -c config/my_agent.yaml  # custom config\n"
            "  agent-simulator --dry-run                # validate config, no spans\n"
            "  agent-simulator --profile rag_researcher # single profile\n"
            "  agent-simulator --duration 60 --concurrency 5  # quick test run\n"
        ),
    )
    parser.add_argument(
        "--config", "-c",
        default="config/default.yaml",
        metavar="PATH",
        help="Path to YAML config file (default: config/default.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Validate config and print what would run — no spans emitted",
    )
    parser.add_argument(
        "--profile",
        metavar="NAME",
        help="Run a single named profile only (overrides all profile mix weights)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        metavar="SECONDS",
        help="Override run_duration_seconds from config",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        metavar="N",
        help="Override concurrency from config",
    )
    parser.add_argument(
        "--no-console",
        action="store_true",
        dest="no_console",
        help="Suppress console span output (send to OTLP collector only)",
    )
    return parser


# ---------------------------------------------------------------------------
# Dry-run printer
# ---------------------------------------------------------------------------

def _print_dry_run(cfg: RootConfig, config_path: str) -> None:
    """Print a human-readable summary of what the simulator would do."""
    real_duration = cfg.simulator.run_duration_seconds / cfg.simulator.clock_multiplier
    total_weight = sum(p.mix_weight for p in cfg.agent_profiles.values()) or 1.0

    print("\n=== Agent Simulator — Dry Run ===\n")
    print(f"  Config:        {config_path}")
    print(f"  Concurrency:   {cfg.simulator.concurrency} agents")
    print(
        f"  Duration:      {cfg.simulator.run_duration_seconds}s simulated "
        f"({real_duration:.0f}s real time)"
    )
    print(f"  Clock:         {cfg.simulator.clock_multiplier}x")
    print(f"  Seed:          {cfg.simulator.random_seed}")
    print(f"  OTel endpoint: {cfg.telemetry.exporter_endpoint}")
    if cfg.telemetry.headers:
        header_keys = list(cfg.telemetry.headers.keys())
        print(f"  Auth headers:  {header_keys}")
    if not cfg.telemetry.tls.insecure:
        print(f"  TLS:           enabled")

    print(f"\n  Profiles ({len(cfg.agent_profiles)}):")
    for name, profile in cfg.agent_profiles.items():
        weight_pct = profile.mix_weight / total_weight * 100
        obs = profile.observability_attributes
        obs_count = len(obs.session) + len(obs.tool) + len(obs.inference)
        bs = profile.behavioral_signals
        if bs is not None:
            beh_count = sum(
                1
                for k, v in bs.model_dump().items()
                if v is not None and k not in ("extra",)
            )
        else:
            beh_count = 0
        print(
            f"    {name:<22} {weight_pct:5.1f}%  "
            f"model={profile.llm_model:<18}  "
            f"obs_attrs={obs_count}  behavioral_signals={beh_count}"
        )

    if cfg.pricing:
        print(f"\n  Pricing models: {list(cfg.pricing.keys())}")

    if cfg.scenarios.enabled:
        print(f"\n  Scenarios:")
        for scenario_name, prob in cfg.scenarios.enabled.items():
            print(f"    {scenario_name:<28} probability={prob}")

    print("\n✅ Config valid. Remove --dry-run to start.\n")


# ---------------------------------------------------------------------------
# Progress printer (runs as an asyncio background task)
# ---------------------------------------------------------------------------

async def _progress_task(
    concurrency: int,
    wall_duration: float,
    start_time: float,
) -> None:
    """Print a live status line every 5 seconds until cancelled."""
    try:
        while True:
            elapsed = time.monotonic() - start_time
            remaining = max(0.0, wall_duration - elapsed)
            mm = int(elapsed // 60)
            ss = int(elapsed % 60)
            print(
                f"\r[{mm:02d}:{ss:02d}] running  "
                f"agents={concurrency}  "
                f"elapsed={elapsed:.0f}s  "
                f"remaining={remaining:.0f}s          ",
                end="",
                flush=True,
            )
            await asyncio.sleep(5.0)
    except asyncio.CancelledError:
        print()  # newline so the next print starts on a fresh line


# ---------------------------------------------------------------------------
# Graceful shutdown helpers
# ---------------------------------------------------------------------------

def _install_signal_handlers(
    stop_event: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Register SIGINT/SIGTERM handlers that schedule stop_event.set()."""

    def _handler(*_: object) -> None:
        print("\n\nShutting down gracefully — flushing spans...", flush=True)
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _handler)
    try:
        signal.signal(signal.SIGTERM, _handler)
    except (OSError, AttributeError):
        # SIGTERM is not available on Windows
        pass


# ---------------------------------------------------------------------------
# Apply CLI overrides to a loaded config (returns a new RootConfig copy)
# ---------------------------------------------------------------------------

def _apply_overrides(cfg: RootConfig, args: argparse.Namespace) -> RootConfig:
    sim_updates: dict = {}
    if args.duration is not None:
        sim_updates["run_duration_seconds"] = args.duration
    if args.concurrency is not None:
        sim_updates["concurrency"] = args.concurrency

    if sim_updates:
        cfg = cfg.model_copy(
            update={"simulator": cfg.simulator.model_copy(update=sim_updates)}
        )

    if args.profile is not None:
        if args.profile not in cfg.agent_profiles:
            print(
                f"❌ Profile '{args.profile}' not found.\n"
                f"   Available profiles: {list(cfg.agent_profiles.keys())}",
                file=sys.stderr,
            )
            sys.exit(1)
        cfg = cfg.model_copy(
            update={"agent_profiles": {args.profile: cfg.agent_profiles[args.profile]}}
        )

    return cfg


# ---------------------------------------------------------------------------
# Async run with progress + graceful shutdown
# ---------------------------------------------------------------------------

async def _async_main(cfg: RootConfig, no_console: bool) -> None:
    from simulator.core import run
    from simulator.telemetry.emitter import build_tracer_provider, get_tracer
    from simulator.telemetry.metrics import SimulatorMetrics, build_meter_provider

    tracer_provider = build_tracer_provider(cfg)
    meter_provider = build_meter_provider(cfg)
    tracer = get_tracer()
    sim_metrics = SimulatorMetrics.from_config(cfg)

    wall_duration = cfg.simulator.run_duration_seconds / cfg.simulator.clock_multiplier
    start_time = time.monotonic()

    print(
        f"[simulator] starting — "
        f"concurrency={cfg.simulator.concurrency}  "
        f"duration={cfg.simulator.run_duration_seconds}s simulated "
        f"({wall_duration:.0f}s real)  "
        f"clock={cfg.simulator.clock_multiplier}x  "
        f"profiles={list(cfg.agent_profiles)}"
    )

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event, loop)

    progress = asyncio.create_task(
        _progress_task(cfg.simulator.concurrency, wall_duration, start_time)
    )
    run_task = asyncio.create_task(run(cfg, tracer, sim_metrics))
    stop_task = asyncio.create_task(stop_event.wait())

    done, _ = await asyncio.wait(
        [run_task, stop_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Stop the progress printer
    stop_event.set()
    progress.cancel()
    try:
        await progress
    except asyncio.CancelledError:
        pass

    # If stopped by signal, cancel the run
    if run_task not in done:
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
    elif run_task.exception():
        raise run_task.exception()  # type: ignore[misc]

    # Clean up the stop watcher if still pending
    if stop_task not in done:
        stop_task.cancel()

    print("\n[simulator] run complete — flushing telemetry...", flush=True)
    tracer_provider.force_flush()
    meter_provider.force_flush(timeout_millis=10_000)
    meter_provider.shutdown()
    print("[simulator] done.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config_path = args.config

    # Load and validate config
    try:
        cfg = load_config(config_path)
    except FileNotFoundError:
        print(
            f"❌ Config file not found: {config_path}\n"
            f"   Create one or run: agent-simulator -c config/default.yaml",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValidationError as exc:
        print(format_validation_error(exc, config_path), file=sys.stderr)
        sys.exit(1)

    # Apply CLI overrides (profile filter, duration, concurrency)
    cfg = _apply_overrides(cfg, args)

    # Dry run: print plan and exit
    if args.dry_run:
        _print_dry_run(cfg, config_path)
        return

    # Full run
    asyncio.run(_async_main(cfg, no_console=args.no_console))


if __name__ == "__main__":
    main()
