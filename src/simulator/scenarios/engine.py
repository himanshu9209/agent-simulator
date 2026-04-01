from __future__ import annotations

from simulator.behavior.distributions import Distributions
from simulator.config import ScenarioConfig
from simulator.scenarios.types import ScenarioType


class ScenarioEngine:

    def __init__(self, config: ScenarioConfig) -> None:
        # Validate all keys are known ScenarioType values at startup.
        self._scenarios: list[tuple[ScenarioType, float]] = [
            (ScenarioType(name), prob)
            for name, prob in config.enabled.items()
        ]

    def select(self, dist: Distributions) -> ScenarioType | None:
        """Returns the first scenario whose Bernoulli trial passes, or None."""
        for scenario_type, probability in self._scenarios:
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
