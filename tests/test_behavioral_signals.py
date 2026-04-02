"""
tests/test_behavioral_signals.py
Verifies that behavioral signals declared in profiles appear on the correct
span types, that tool sequences are enforced, that model switching is reflected
on inference spans, and that the dynamic ScenarioEngine.evaluate() respects
per-profile probabilities.
"""
from __future__ import annotations

import pytest

from simulator.behavior.engine import run_agent_session
from simulator.config import (
    AgentProfile,
    AttributeType,
    BehavioralSignalConfig,
    BehavioralSignalsSchema,
    GaussianDistribution,
    ToolSequenceConfig,
    UniformIntDistribution,
)
from simulator.scenarios.engine import ScenarioEngine
from simulator.scenarios.types import ScenarioType
from simulator.config import ScenarioConfig


# ---------------------------------------------------------------------------
# Profile fixtures
# ---------------------------------------------------------------------------

def _base_profile(**kwargs) -> AgentProfile:
    """Minimal profile; override any field via kwargs."""
    defaults = dict(
        tools=["search", "rerank", "summarise"],
        llm_model="gpt-4o",
        llm_input_tokens=GaussianDistribution(mean=500, std=1),
        llm_output_tokens=GaussianDistribution(mean=100, std=1),
        planning_latency_ms=GaussianDistribution(mean=100, std=10),
        tool_call_count=UniformIntDistribution(min=3, max=3),  # fixed at 3 for determinism
        failure_rate=0.0,
    )
    defaults.update(kwargs)
    return AgentProfile(**defaults)


# ---------------------------------------------------------------------------
# planning.quality_score
# ---------------------------------------------------------------------------

async def test_planning_quality_appears_on_planning_span(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            planning_quality=BehavioralSignalConfig(
                type=AttributeType.FLOAT, span="planning", mean=0.85, std=0.1, min=0.0, max=1.0
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    planning = next(s for s in exporter.get_finished_spans() if s.name == "agent.planning")
    assert "planning.quality_score" in planning.attributes
    score = planning.attributes["planning.quality_score"]
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


async def test_planning_quality_absent_when_not_configured(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile()  # no behavioral_signals
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    planning = next(s for s in exporter.get_finished_spans() if s.name == "agent.planning")
    assert "planning.quality_score" not in planning.attributes


# ---------------------------------------------------------------------------
# tool.selection_quality and tool.sequence_position
# ---------------------------------------------------------------------------

async def test_tool_selection_quality_on_every_tool_span(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            tool_selection_quality=BehavioralSignalConfig(
                type=AttributeType.FLOAT, span="tool", mean=0.8, std=0.1, min=0.0, max=1.0
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    tool_spans = [s for s in exporter.get_finished_spans() if s.name == "tool.call"]
    assert len(tool_spans) == 3
    for span in tool_spans:
        assert "tool.selection_quality" in span.attributes
        assert 0.0 <= span.attributes["tool.selection_quality"] <= 1.0


async def test_tool_sequence_position_always_emitted(
    memory_tracer, fast_clock, seeded_dist
):
    """tool.sequence_position is emitted on every tool call regardless of sequence config."""
    profile = _base_profile()
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    tool_spans = sorted(
        [s for s in exporter.get_finished_spans() if s.name == "tool.call"],
        key=lambda s: s.attributes["tool.sequence_position"],
    )
    positions = [s.attributes["tool.sequence_position"] for s in tool_spans]
    assert positions == [0, 1, 2]


# ---------------------------------------------------------------------------
# Tool sequence enforcement
# ---------------------------------------------------------------------------

async def test_enforced_tool_sequence_picks_correct_tools(
    memory_tracer, fast_clock, seeded_dist
):
    """With 0% deviation, every tool call must follow the declared order."""
    profile = _base_profile(
        tools=["search", "rerank", "summarise"],
        tool_call_count=UniformIntDistribution(min=3, max=3),
        behavioral_signals=BehavioralSignalsSchema(
            tool_sequence=ToolSequenceConfig(
                enforced=True,
                order=["search", "rerank", "summarise"],
                deviation_probability=0.0,
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    tool_spans = sorted(
        [s for s in exporter.get_finished_spans() if s.name == "tool.call"],
        key=lambda s: s.attributes["tool.sequence_position"],
    )
    tool_names = [s.attributes["tool.name"] for s in tool_spans]
    assert tool_names == ["search", "rerank", "summarise"]


async def test_enforced_sequence_deviation_flag_set(
    memory_tracer, fast_clock, seeded_dist
):
    """tool.sequence_deviation is only present when sequence enforcement is on."""
    profile_with_seq = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            tool_sequence=ToolSequenceConfig(
                enforced=True,
                order=["search", "rerank", "summarise"],
                deviation_probability=0.0,
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile_with_seq, seeded_dist, tracer, fast_clock)

    tool_spans = [s for s in exporter.get_finished_spans() if s.name == "tool.call"]
    for span in tool_spans:
        assert "tool.sequence_deviation" in span.attributes
        assert span.attributes["tool.sequence_deviation"] is False


async def test_no_sequence_deviation_attr_without_enforcement(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile()  # no tool_sequence
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    for span in exporter.get_finished_spans():
        assert "tool.sequence_deviation" not in span.attributes


async def test_enforced_sequence_wraps_for_extra_tool_calls(
    memory_tracer, fast_clock, seeded_dist
):
    """When tool_call_count > len(order), sequence wraps around."""
    profile = _base_profile(
        tools=["a", "b"],
        tool_call_count=UniformIntDistribution(min=4, max=4),
        behavioral_signals=BehavioralSignalsSchema(
            tool_sequence=ToolSequenceConfig(
                enforced=True, order=["a", "b"], deviation_probability=0.0
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    tool_spans = sorted(
        [s for s in exporter.get_finished_spans() if s.name == "tool.call"],
        key=lambda s: s.attributes["tool.sequence_position"],
    )
    tool_names = [s.attributes["tool.name"] for s in tool_spans]
    assert tool_names == ["a", "b", "a", "b"]


# ---------------------------------------------------------------------------
# Model switch
# ---------------------------------------------------------------------------

async def test_model_switch_changes_gen_ai_model_on_inference_span(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile(
        llm_model="claude-3-sonnet",
        behavioral_signals=BehavioralSignalsSchema(
            model_switch=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="inference",
                probability=1.0, target_model="gpt-4o",
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    inference_spans = [s for s in exporter.get_finished_spans() if s.name == "llm.inference"]
    for span in inference_spans:
        assert span.attributes["gen_ai.model"] == "gpt-4o"
        assert span.attributes["inference.model_switched"] is True
        assert span.attributes["inference.original_model"] == "claude-3-sonnet"


async def test_no_switch_keeps_original_model(memory_tracer, fast_clock, seeded_dist):
    profile = _base_profile(
        llm_model="gpt-4o",
        behavioral_signals=BehavioralSignalsSchema(
            model_switch=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="inference",
                probability=0.0, target_model="claude-3-sonnet",
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    for span in [s for s in exporter.get_finished_spans() if s.name == "llm.inference"]:
        assert span.attributes["gen_ai.model"] == "gpt-4o"
        assert "inference.model_switched" not in span.attributes


# ---------------------------------------------------------------------------
# Goal drift behavioral signal
# ---------------------------------------------------------------------------

async def test_goal_drift_signal_emits_three_attributes(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=1.0
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    session = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    assert session.attributes["session.goal_drift_detected"] is True
    assert "session.original_goal" in session.attributes
    assert "session.final_goal" in session.attributes
    # Drifted goal must be different from original
    assert session.attributes["session.original_goal"] != session.attributes["session.final_goal"]


async def test_goal_drift_signal_absent_at_zero_probability(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=0.0
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    session = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    assert "session.goal_drift_detected" not in session.attributes


# ---------------------------------------------------------------------------
# Replanning triggered
# ---------------------------------------------------------------------------

async def test_replanning_triggered_on_session_span(
    memory_tracer, fast_clock, seeded_dist
):
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            replanning_triggered=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=1.0
            )
        )
    )
    tracer, exporter = memory_tracer
    await run_agent_session("p", profile, seeded_dist, tracer, fast_clock)

    session = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    assert session.attributes.get("planning.replanning_triggered") is True


# ---------------------------------------------------------------------------
# ScenarioEngine.evaluate() — dynamic per-profile scenario selection
# ---------------------------------------------------------------------------

def test_evaluate_falls_back_to_select_when_no_behavioral_signals(seeded_dist):
    """Profile without behavioral_signals must behave identically to select()."""
    engine = ScenarioEngine(ScenarioConfig(enabled={"tool_timeout": 1.0}))
    profile = _base_profile()  # behavioral_signals=None
    result = engine.evaluate(profile, seeded_dist)
    assert result == ScenarioType.TOOL_TIMEOUT


def test_evaluate_uses_profile_goal_drift_probability(seeded_dist):
    """evaluate() should fire GOAL_DRIFT based on profile probability, not global."""
    # Global has goal_drift at 0.0 — would never fire via select().
    engine = ScenarioEngine(ScenarioConfig(enabled={"goal_drift": 0.0}))
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=1.0
            )
        )
    )
    result = engine.evaluate(profile, seeded_dist)
    assert result == ScenarioType.GOAL_DRIFT


def test_evaluate_skips_global_goal_drift_when_profile_owns_it(seeded_dist):
    """When profile has goal_drift=0.0 signal, global goal_drift is skipped."""
    # Global goal_drift probability=1.0, but profile overrides with 0.0.
    engine = ScenarioEngine(ScenarioConfig(enabled={"goal_drift": 1.0}))
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=0.0
            )
        )
    )
    results = {engine.evaluate(profile, seeded_dist) for _ in range(50)}
    assert ScenarioType.GOAL_DRIFT not in results


def test_evaluate_other_global_scenarios_still_fire(seeded_dist):
    """evaluate() must still consider global scenarios other than goal_drift."""
    engine = ScenarioEngine(ScenarioConfig(enabled={"tool_timeout": 1.0}))
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=0.0
            )
        )
    )
    result = engine.evaluate(profile, seeded_dist)
    assert result == ScenarioType.TOOL_TIMEOUT


def test_evaluate_returns_none_when_nothing_fires(seeded_dist):
    engine = ScenarioEngine(ScenarioConfig(enabled={}))
    profile = _base_profile(
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=0.0
            )
        )
    )
    assert engine.evaluate(profile, seeded_dist) is None


# ---------------------------------------------------------------------------
# Behavioral signal probability distributions over many samples
# ---------------------------------------------------------------------------

async def test_goal_drift_rate_matches_configured_probability():
    """Over 500 sessions, goal_drift rate should be within ±5% of declared probability."""
    import random
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from simulator.behavior.distributions import Distributions
    from simulator.clock import ClockController

    probability = 0.20
    profile = _base_profile(
        tool_call_count=UniformIntDistribution(min=1, max=1),
        behavioral_signals=BehavioralSignalsSchema(
            goal_drift=BehavioralSignalConfig(
                type=AttributeType.BOOLEAN, span="session", probability=probability
            )
        )
    )
    clock = ClockController(10_000.0)
    drift_count = 0
    total = 500

    for seed in range(total):
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        dist = Distributions.from_seed(seed)
        await run_agent_session("p", profile, dist, tracer, clock)
        spans = exporter.get_finished_spans()
        session = next(s for s in spans if s.name == "agent.session")
        if session.attributes.get("session.goal_drift_detected"):
            drift_count += 1

    observed_rate = drift_count / total
    assert abs(observed_rate - probability) < 0.05, (
        f"Expected drift rate ~{probability:.0%}, got {observed_rate:.0%}"
    )


# ---------------------------------------------------------------------------
# Default YAML — all 5 profiles load behavioral signals
# ---------------------------------------------------------------------------

def test_default_yaml_all_profiles_have_behavioral_signals():
    from pathlib import Path
    from simulator.config import load_config

    config = load_config(Path(__file__).parent.parent / "config" / "default.yaml")
    for name, profile in config.agent_profiles.items():
        assert profile.behavioral_signals is not None, (
            f"Profile '{name}' has no behavioral_signals"
        )
