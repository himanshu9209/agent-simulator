"""
tests/test_dynamic_attributes.py
Verifies that custom observability_attributes declared in profiles appear on the
correct span types and do not break the existing span structure.
"""
from __future__ import annotations

import pytest

from simulator.behavior.engine import run_agent_session
from simulator.behavior.distributions import Distributions
from simulator.config import (
    AgentProfile,
    AttributeConfig,
    AttributeType,
    GaussianDistribution,
    SpanAttributeSchema,
    UniformIntDistribution,
)
from simulator.telemetry import attributes as A


@pytest.fixture
def profile_with_all_attrs() -> AgentProfile:
    """Profile with one attribute on each span type."""
    return AgentProfile(
        tools=["vector_search", "reranker"],
        llm_model="gpt-4o",
        llm_input_tokens=GaussianDistribution(mean=1200, std=300),
        llm_output_tokens=GaussianDistribution(mean=250, std=80),
        planning_latency_ms=GaussianDistribution(mean=200, std=50),
        tool_call_count=UniformIntDistribution(min=2, max=2),  # fixed count for determinism
        failure_rate=0.0,
        observability_attributes=SpanAttributeSchema(
            session={
                "retrieval.score": AttributeConfig(type=AttributeType.FLOAT, min=0.6, max=1.0),
                "index.name": AttributeConfig(type=AttributeType.ENUM, values=["prod", "staging"]),
            },
            tool={
                "tool.cache_hit": AttributeConfig(type=AttributeType.BOOLEAN, probability=0.3),
                "tool.input_size_kb": AttributeConfig(type=AttributeType.FLOAT, min=0.5, max=50.0),
            },
            inference={
                "inference.temperature": AttributeConfig(type=AttributeType.FLOAT, min=0.0, max=1.0),
            },
        ),
    )


async def test_session_span_has_dynamic_attributes(
    profile_with_all_attrs, memory_tracer, fast_clock, seeded_dist
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="test_profile",
        profile=profile_with_all_attrs,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    session = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    attrs = session.attributes

    assert "retrieval.score" in attrs
    assert isinstance(attrs["retrieval.score"], float)
    assert 0.6 <= attrs["retrieval.score"] <= 1.0

    assert "index.name" in attrs
    assert attrs["index.name"] in {"prod", "staging"}


async def test_tool_span_has_dynamic_attributes(
    profile_with_all_attrs, memory_tracer, fast_clock, seeded_dist
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="test_profile",
        profile=profile_with_all_attrs,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    tool_spans = [s for s in exporter.get_finished_spans() if s.name == "tool.call"]
    assert len(tool_spans) == 2  # tool_call_count is fixed at min=max=2

    for span in tool_spans:
        assert "tool.cache_hit" in span.attributes
        assert isinstance(span.attributes["tool.cache_hit"], bool)

        assert "tool.input_size_kb" in span.attributes
        assert 0.5 <= span.attributes["tool.input_size_kb"] <= 50.0


async def test_inference_span_has_dynamic_attributes(
    profile_with_all_attrs, memory_tracer, fast_clock, seeded_dist
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="test_profile",
        profile=profile_with_all_attrs,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    inference_spans = [s for s in exporter.get_finished_spans() if s.name == "llm.inference"]
    assert len(inference_spans) >= 1

    for span in inference_spans:
        assert "inference.temperature" in span.attributes
        assert 0.0 <= span.attributes["inference.temperature"] <= 1.0


async def test_dynamic_attributes_do_not_remove_existing_attributes(
    profile_with_all_attrs, memory_tracer, fast_clock, seeded_dist
):
    """Adding custom attrs must not drop V1 span attributes."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="test_profile",
        profile=profile_with_all_attrs,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    spans = exporter.get_finished_spans()
    session = next(s for s in spans if s.name == "agent.session")
    inference_spans = [s for s in spans if s.name == "llm.inference"]
    tool_spans = [s for s in spans if s.name == "tool.call"]

    # V1 session attributes still present
    assert A.GEN_AI_SYSTEM in session.attributes
    assert A.AGENT_PROFILE_TYPE in session.attributes

    # V1 inference attributes still present
    for span in inference_spans:
        assert A.GEN_AI_MODEL in span.attributes
        assert A.GEN_AI_INPUT_TOKENS in span.attributes
        assert A.GEN_AI_OUTPUT_TOKENS in span.attributes

    # V1 tool attributes still present
    for span in tool_spans:
        assert A.TOOL_NAME in span.attributes
        assert A.TOOL_CALL_INDEX in span.attributes


async def test_empty_observability_attributes_does_not_crash(
    memory_tracer, fast_clock, seeded_dist
):
    """A profile with no observability_attributes must run without error."""
    from simulator.config import AgentProfile, GaussianDistribution, UniformIntDistribution

    profile = AgentProfile(
        tools=["search"],
        llm_model="gpt-4o",
        llm_input_tokens=GaussianDistribution(mean=500, std=100),
        llm_output_tokens=GaussianDistribution(mean=100, std=30),
        planning_latency_ms=GaussianDistribution(mean=100, std=20),
        tool_call_count=UniformIntDistribution(min=1, max=1),
        failure_rate=0.0,
        # observability_attributes uses default empty SpanAttributeSchema
    )
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="minimal",
        profile=profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )
    span_names = {s.name for s in exporter.get_finished_spans()}
    assert "agent.session" in span_names


async def test_default_yaml_profiles_load_with_observability_attributes():
    """All 5 profiles in default.yaml must load and have non-empty obs attrs."""
    from pathlib import Path
    from simulator.config import load_config

    config = load_config(Path(__file__).parent.parent / "config" / "default.yaml")
    for name, profile in config.agent_profiles.items():
        obs = profile.observability_attributes
        total_attrs = (
            len(obs.session) + len(obs.tool) + len(obs.inference)
        )
        assert total_attrs > 0, f"Profile '{name}' has no observability_attributes"
