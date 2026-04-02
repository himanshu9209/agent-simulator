"""
tests/test_cost.py
Verifies CostCalculator correctness, cost span attributes, and session totals.
"""
from __future__ import annotations

import pytest

from simulator.behavior.cost import CostCalculator, InferenceCost
from simulator.behavior.engine import run_agent_session
from simulator.config import (
    AgentProfile,
    GaussianDistribution,
    ModelPricing,
    UniformIntDistribution,
)


# ---------------------------------------------------------------------------
# Pricing fixtures
# ---------------------------------------------------------------------------

GPT4O_PRICING = ModelPricing(
    input_per_million=2.50,
    output_per_million=10.00,
    cached_input_per_million=1.25,
)

CLAUDE_SONNET_PRICING = ModelPricing(
    input_per_million=3.00,
    output_per_million=15.00,
    cache_write_per_million=3.75,
    cache_read_per_million=0.30,
)

PRICING = {
    "gpt-4o": GPT4O_PRICING,
    "claude-3-sonnet": CLAUDE_SONNET_PRICING,
}


@pytest.fixture
def calc() -> CostCalculator:
    return CostCalculator(PRICING)


# ---------------------------------------------------------------------------
# CostCalculator unit tests
# ---------------------------------------------------------------------------

def test_standard_cost_calculation(calc):
    """1000 input + 500 output on gpt-4o at known rates."""
    cost = calc.calculate("gpt-4o", input_tokens=1000, output_tokens=500)
    expected_input  = 1000 * 2.50  / 1_000_000   # 0.0025
    expected_output = 500  * 10.00 / 1_000_000   # 0.005
    assert abs(cost.input_cost_usd  - expected_input)  < 1e-7
    assert abs(cost.output_cost_usd - expected_output) < 1e-7
    assert abs(cost.total_cost_usd  - (expected_input + expected_output)) < 1e-7


def test_cached_input_uses_discounted_rate(calc):
    """Cached tokens should use cached_input_per_million, not input_per_million."""
    cost = calc.calculate("gpt-4o", input_tokens=1000, output_tokens=0, cached_tokens=400)
    # 600 non-cached @ 2.50, 400 cached @ 1.25
    expected_input  = (600 * 2.50 + 400 * 1.25) / 1_000_000
    assert abs(cost.input_cost_usd - expected_input) < 1e-7


def test_cached_tokens_exceeding_input_does_not_go_negative(calc):
    """If cached_tokens > input_tokens, non-cached portion should floor at 0."""
    cost = calc.calculate("gpt-4o", input_tokens=100, output_tokens=0, cached_tokens=500)
    assert cost.input_cost_usd >= 0.0
    assert cost.total_cost_usd >= 0.0


def test_unknown_model_returns_zero_cost(calc):
    """Missing pricing entry must return zero cost, not raise."""
    cost = calc.calculate("unknown-model-x", input_tokens=1000, output_tokens=500)
    assert cost == InferenceCost(0.0, 0.0, 0.0)


def test_zero_tokens_returns_zero_cost(calc):
    cost = calc.calculate("gpt-4o", input_tokens=0, output_tokens=0)
    assert cost.total_cost_usd == 0.0


def test_claude_sonnet_output_cost(calc):
    """claude-3-sonnet output at $15/M tokens."""
    cost = calc.calculate("claude-3-sonnet", input_tokens=0, output_tokens=1_000_000)
    assert abs(cost.output_cost_usd - 15.00) < 1e-4


def test_cost_is_rounded_to_8_decimal_places(calc):
    """Results must be rounded to 8dp to avoid floating-point noise in spans."""
    cost = calc.calculate("gpt-4o", input_tokens=1, output_tokens=1)
    # Just check it doesn't have more than 8 significant decimal digits
    assert len(str(cost.total_cost_usd).rstrip("0").split(".")[-1]) <= 8


def test_pricing_table_change_reflected_without_code_change():
    """Updating the pricing dict is sufficient — no Python changes required."""
    cheap = CostCalculator({"my-model": ModelPricing(input_per_million=0.01, output_per_million=0.02)})
    cost = cheap.calculate("my-model", input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost.input_cost_usd  - 0.01) < 1e-6
    assert abs(cost.output_cost_usd - 0.02) < 1e-6


def test_empty_pricing_table_returns_zero_for_any_model():
    calc_empty = CostCalculator({})
    cost = calc_empty.calculate("gpt-4o", input_tokens=5000, output_tokens=2000)
    assert cost.total_cost_usd == 0.0


# ---------------------------------------------------------------------------
# Integration: cost attributes appear on the correct spans
# ---------------------------------------------------------------------------

@pytest.fixture
def priced_profile() -> AgentProfile:
    return AgentProfile(
        tools=["search"],
        llm_model="gpt-4o",
        llm_input_tokens=GaussianDistribution(mean=1000, std=1),   # ~1000 tokens
        llm_output_tokens=GaussianDistribution(mean=500, std=1),    # ~500 tokens
        planning_latency_ms=GaussianDistribution(mean=100, std=10),
        tool_call_count=UniformIntDistribution(min=2, max=2),       # fixed for determinism
        failure_rate=0.0,
    )


async def test_inference_span_has_cost_attributes(
    priced_profile, memory_tracer, fast_clock, seeded_dist
):
    tracer, exporter = memory_tracer
    calc = CostCalculator(PRICING)
    await run_agent_session(
        profile_name="test",
        profile=priced_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        cost_calculator=calc,
    )

    inference_spans = [s for s in exporter.get_finished_spans() if s.name == "llm.inference"]
    assert len(inference_spans) == 2  # tool_call_count fixed at 2

    for span in inference_spans:
        assert "gen_ai.usage.cost_usd"        in span.attributes
        assert "gen_ai.usage.input_cost_usd"  in span.attributes
        assert "gen_ai.usage.output_cost_usd" in span.attributes
        assert span.attributes["gen_ai.usage.cost_usd"] > 0.0
        assert span.attributes["gen_ai.usage.input_cost_usd"] >= 0.0
        assert span.attributes["gen_ai.usage.output_cost_usd"] >= 0.0


async def test_session_span_has_total_cost(
    priced_profile, memory_tracer, fast_clock, seeded_dist
):
    tracer, exporter = memory_tracer
    calc = CostCalculator(PRICING)
    await run_agent_session(
        profile_name="test",
        profile=priced_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        cost_calculator=calc,
    )

    session = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    assert "session.total_cost_usd" in session.attributes
    assert "session.avg_cost_per_tool_call_usd" in session.attributes
    assert session.attributes["session.total_cost_usd"] > 0.0


async def test_session_total_equals_sum_of_inference_costs(
    priced_profile, memory_tracer, fast_clock, seeded_dist
):
    """session.total_cost_usd must equal the sum of gen_ai.usage.cost_usd across calls."""
    tracer, exporter = memory_tracer
    calc = CostCalculator(PRICING)
    await run_agent_session(
        profile_name="test",
        profile=priced_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        cost_calculator=calc,
    )

    spans = exporter.get_finished_spans()
    inference_total = sum(
        s.attributes["gen_ai.usage.cost_usd"]
        for s in spans if s.name == "llm.inference"
    )
    session = next(s for s in spans if s.name == "agent.session")
    assert abs(session.attributes["session.total_cost_usd"] - inference_total) < 1e-9


async def test_no_cost_calculator_emits_no_cost_attributes(
    priced_profile, memory_tracer, fast_clock, seeded_dist
):
    """Without a cost_calculator, no cost attributes appear on any span."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="test",
        profile=priced_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        # cost_calculator not passed — should default to None
    )

    for span in exporter.get_finished_spans():
        assert "gen_ai.usage.cost_usd"        not in span.attributes
        assert "session.total_cost_usd"       not in span.attributes


async def test_default_yaml_pricing_loads_all_used_models():
    """Pricing table must cover every llm_model referenced in the 5 profiles."""
    from pathlib import Path
    from simulator.config import load_config

    config = load_config(Path(__file__).parent.parent / "config" / "default.yaml")
    used_models = {p.llm_model for p in config.agent_profiles.values()}
    for model in used_models:
        assert model in config.pricing, (
            f"Model '{model}' used in a profile but missing from pricing table"
        )
