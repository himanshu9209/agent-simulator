from __future__ import annotations

import pytest

from opentelemetry.trace import StatusCode

from simulator.behavior.engine import run_agent_session
from simulator.config import ScenarioConfig
from simulator.scenarios.engine import ScenarioEngine
from simulator.scenarios.types import ScenarioType
from simulator.telemetry import attributes as A


def spans_by_name(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


def span_by_name(exporter, name):
    return next(s for s in exporter.get_finished_spans() if s.name == name)


async def test_tool_timeout_sets_error_type_attribute(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.TOOL_TIMEOUT,
    )

    tool_spans = spans_by_name(exporter, "tool.call")
    assert len(tool_spans) == 1, "tool_timeout should produce exactly one tool.call span"
    assert tool_spans[0].attributes[A.ERROR_TYPE] == "timeout"


async def test_tool_timeout_sets_error_status_on_tool_and_session(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.TOOL_TIMEOUT,
    )

    tool_span = spans_by_name(exporter, "tool.call")[0]
    session_span = span_by_name(exporter, "agent.session")

    assert tool_span.status.status_code == StatusCode.ERROR
    assert session_span.status.status_code == StatusCode.ERROR


async def test_tool_timeout_produces_no_agent_output(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.TOOL_TIMEOUT,
    )

    assert spans_by_name(exporter, "agent.output") == []


async def test_infinite_retry_loop_produces_10_to_20_tool_calls(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.INFINITE_RETRY_LOOP,
    )

    tool_spans = spans_by_name(exporter, "tool.call")
    assert 10 <= len(tool_spans) <= 20, (
        f"infinite_retry_loop must produce 10–20 tool.call spans, got {len(tool_spans)}"
    )


async def test_infinite_retry_loop_tool_count_on_session_span(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.INFINITE_RETRY_LOOP,
    )

    session = span_by_name(exporter, "agent.session")
    tool_spans = spans_by_name(exporter, "tool.call")
    assert session.attributes[A.TOOL_CALL_COUNT] == len(tool_spans)


async def test_goal_drift_sets_scenario_type(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.GOAL_DRIFT,
    )

    session = span_by_name(exporter, "agent.session")
    assert session.attributes[A.SCENARIO_TYPE] == ScenarioType.GOAL_DRIFT.value


async def test_goal_drift_goal_is_valid_string(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    from simulator.behavior.engine import AGENT_GOALS

    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.GOAL_DRIFT,
    )

    session = span_by_name(exporter, "agent.session")
    assert session.attributes[A.AGENT_GOAL] in AGENT_GOALS


async def test_context_overflow_input_tokens_exceed_8000(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.CONTEXT_OVERFLOW,
    )

    llm_spans = spans_by_name(exporter, "llm.inference")
    assert len(llm_spans) >= 1
    for span in llm_spans:
        assert span.attributes[A.GEN_AI_INPUT_TOKENS] > 8000, (
            f"context_overflow must produce input_tokens > 8000, "
            f"got {span.attributes[A.GEN_AI_INPUT_TOKENS]}"
        )


async def test_silent_failure_agent_output_is_success(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.SILENT_FAILURE,
    )

    output_spans = spans_by_name(exporter, "agent.output")
    assert len(output_spans) >= 1
    for span in output_spans:
        assert span.attributes[A.AGENT_STATUS] == "success"
        assert span.status.status_code != StatusCode.ERROR


async def test_silent_failure_output_score_is_zero(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=ScenarioType.SILENT_FAILURE,
    )

    output_spans = spans_by_name(exporter, "agent.output")
    for span in output_spans:
        assert span.attributes["agent.output.score"] == 0


async def test_scenario_type_set_on_session_span_for_all_scenarios(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    for scenario in (
        ScenarioType.TOOL_TIMEOUT,
        ScenarioType.INFINITE_RETRY_LOOP,
        ScenarioType.GOAL_DRIFT,
        ScenarioType.CONTEXT_OVERFLOW,
        ScenarioType.SILENT_FAILURE,
    ):
        exporter = memory_tracer[1]
        exporter.clear()
        tracer = memory_tracer[0]
        await run_agent_session(
            profile_name="rag_researcher",
            profile=rag_profile,
            dist=seeded_dist,
            tracer=tracer,
            clock=fast_clock,
            scenario=scenario,
        )
        session = span_by_name(exporter, "agent.session")
        assert session.attributes[A.SCENARIO_TYPE] == scenario.value, (
            f"Expected scenario.type={scenario.value!r} on session span"
        )


async def test_no_scenario_type_on_normal_session(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
        scenario=None,
    )

    session = span_by_name(exporter, "agent.session")
    assert A.SCENARIO_TYPE not in (session.attributes or {})


def test_scenario_engine_always_returns_none_when_empty(seeded_dist):
    engine = ScenarioEngine(ScenarioConfig(enabled={}))
    for _ in range(50):
        assert engine.select(seeded_dist) is None


def test_scenario_engine_returns_correct_type_at_probability_one(seeded_dist):
    engine = ScenarioEngine(ScenarioConfig(enabled={"tool_timeout": 1.0}))
    result = engine.select(seeded_dist)
    assert result == ScenarioType.TOOL_TIMEOUT


def test_scenario_engine_never_selects_at_probability_zero(seeded_dist):
    engine = ScenarioEngine(ScenarioConfig(enabled={"context_overflow": 0.0}))
    for _ in range(100):
        assert engine.select(seeded_dist) is None
