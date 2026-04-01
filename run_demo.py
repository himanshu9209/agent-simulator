"""
Quick demo: runs one agent session and prints spans to stdout.
No Docker or OTel Collector required.

Usage: python run_demo.py
"""
import asyncio

from simulator.config import load_config
from simulator.behavior.distributions import Distributions
from simulator.behavior.engine import build_tracer_provider, run_agent_session


async def main() -> None:
    config = load_config("config/default.yaml")
    provider = build_tracer_provider(config)
    tracer = provider.get_tracer("agent-simulator")

    profile_name = "rag_researcher"
    profile = config.agent_profiles[profile_name]
    dist = Distributions.from_seed(config.simulator.random_seed)

    print("Running one agent session...\n")
    await run_agent_session(
        profile_name=profile_name,
        profile=profile,
        dist=dist,
        tracer=tracer,
        clock_multiplier=10.0,  # 10x speed so it finishes quickly
    )

    provider.force_flush()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
