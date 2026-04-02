"""
behavior/cost.py
Calculates the USD cost of a single LLM inference call from token counts and
the YAML-configured pricing table.

Supports:
  - Standard pricing (all providers)
  - OpenAI cached input tokens (cached_input_per_million)
  - Anthropic cache write/read tokens (cache_write_per_million / cache_read_per_million)

Unknown models return zero cost rather than raising, so a missing pricing entry
never crashes a running simulation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from simulator.config import ModelPricing


@dataclass(frozen=True)
class InferenceCost:
    input_cost_usd:  float
    output_cost_usd: float
    total_cost_usd:  float


class CostCalculator:
    def __init__(self, pricing_cfg: Dict[str, ModelPricing]) -> None:
        self._pricing = pricing_cfg

    def calculate(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> InferenceCost:
        pricing = self._pricing.get(model)
        if not pricing:
            return InferenceCost(0.0, 0.0, 0.0)

        non_cached = max(0, input_tokens - cached_tokens)
        cached_rate = (
            pricing.cached_input_per_million
            if pricing.cached_input_per_million is not None
            else pricing.input_per_million
        )

        input_cost  = non_cached   * pricing.input_per_million  / 1_000_000
        cached_cost = cached_tokens * cached_rate               / 1_000_000
        output_cost = output_tokens * pricing.output_per_million / 1_000_000
        total       = input_cost + cached_cost + output_cost

        return InferenceCost(
            input_cost_usd=round(input_cost + cached_cost, 8),
            output_cost_usd=round(output_cost, 8),
            total_cost_usd=round(total, 8),
        )
