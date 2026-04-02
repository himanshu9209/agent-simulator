from __future__ import annotations

from typing import TYPE_CHECKING

from simulator.behavior.distributions import Distributions
from simulator.config import ScenarioConfig
from simulator.scenarios.types import ScenarioType

if TYPE_CHECKING:
    from simulator.config import AgentProfile


class ScenarioEngine:

    def __init__(self, config: ScenarioConfig) -> None:
        # Validate all keys are known ScenarioType values at startup.
        self._scenarios: list[tuple[ScenarioType, float]] = [
            (ScenarioType(name), prob)
            for name, prob in config.enabled.items()
        ]

    def select(self, dist: Distributions) -> ScenarioType | None:
        """Returns the first scenario whose Bernoulli trial passes, or None.
        Uses the global scenarios.enabled probability table — applies equally
        to all profiles.  Kept for backward compatibility.
        """
        for scenario_type, probability in self._scenarios:
            if dist.bernoulli(probability):
                return scenario_type
        return None

    def evaluate(self, profile: "AgentProfile", dist: Distributions) -> ScenarioType | None:
        """Dynamic scenario selection driven by per-profile behavioral_signals config.

        Replaces the flat global probability list with per-profile evaluation:
          1. If the profile declares a goal_drift signal, use its probability
             instead of (or in addition to) the global value.
          2. All other scenario types still come from the global scenarios.enabled
             table, giving forward compatibility as new scenario types are added.

        When no behavioral_signals are declared the method falls back to select().
        """
        bs = profile.behavioral_signals

        if bs is None:
            return self.select(dist)

        # Check profile-level goal drift first.
        if bs.goal_drift and dist.bernoulli(bs.goal_drift.probability or 0.0):
            return ScenarioType.GOAL_DRIFT

        # Check remaining global scenarios, skipping goal_drift if profile owns it.
        for scenario_type, probability in self._scenarios:
            if scenario_type == ScenarioType.GOAL_DRIFT and bs.goal_drift:
                continue  # profile probability already evaluated above
            if dist.bernoulli(probability):
                return scenario_type

        return None

    @staticmethod
    def retry_tool_count(dist: Distributions) -> int:
        """Tool call count for infinite_retry_loop (10–20 iterations)."""
        return dist.randint(10, 20)

    @staticmethod
    def overflow_input_tokens(dist: Distributions) -> int:
        """Input token count for context_overflow (8001–12000 tokens)."""
        return dist.randint(8001, 12000)
