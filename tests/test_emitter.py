from __future__ import annotations

from simulator.behavior.engine import run_agent_session
from simulator.telemetry import attributes as A


def spans_by_name(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


def span_by_name(exporter, name):
    return next(s for s in exporter.get_finished_spans() if s.name == name)


def find_parent(spans, child):
    if child.parent is None:
        return None
    return next(
        (s for s in spans if s.context.span_id == child.parent.span_id), None
    )


async def _run(seeded_dist, rag_profile, memory_tracer, fast_clock):
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )
    return exporter.get_finished_spans()


async def test_gen_ai_system_is_simulated_on_all_spans(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    for span in spans:
        assert span.attributes.get(A.GEN_AI_SYSTEM) == A.SYSTEM_SIMULATED, (
            f"Span '{span.name}' missing gen_ai.system=simulated"
        )


async def test_gen_ai_operation_name_on_all_spans(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    valid_ops = {A.OP_AGENT_SESSION, A.OP_TOOL_CALL, A.OP_CHAT}
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    for span in spans:
        op = span.attributes.get(A.GEN_AI_OPERATION_NAME)
        assert op in valid_ops, (
            f"Span '{span.name}' has unexpected gen_ai.operation.name={op!r}"
        )


async def test_llm_inference_has_model_and_token_counts(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    llm_spans = [s for s in spans if s.name == "llm.inference"]
    assert len(llm_spans) >= 1

    for span in llm_spans:
        assert A.GEN_AI_MODEL in span.attributes
        assert isinstance(span.attributes[A.GEN_AI_INPUT_TOKENS], int)
        assert span.attributes[A.GEN_AI_INPUT_TOKENS] >= 1
        assert isinstance(span.attributes[A.GEN_AI_OUTPUT_TOKENS], int)
        assert span.attributes[A.GEN_AI_OUTPUT_TOKENS] >= 1


async def test_tool_call_has_tool_name_and_index(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    tool_spans = [s for s in spans if s.name == "tool.call"]
    assert len(tool_spans) >= 1

    for span in tool_spans:
        assert A.TOOL_NAME in span.attributes
        assert isinstance(span.attributes[A.TOOL_CALL_INDEX], int)
        assert span.attributes[A.TOOL_CALL_INDEX] >= 0


async def test_agent_output_has_agent_status(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    output_spans = [s for s in spans if s.name == "agent.output"]
    assert len(output_spans) >= 1

    for span in output_spans:
        status = span.attributes.get(A.AGENT_STATUS)
        assert status in ("success", "error"), (
            f"agent.output must have agent.status in {{success, error}}, got {status!r}"
        )


async def test_agent_session_has_all_required_attributes(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    session = span_by_name(memory_tracer[1], "agent.session")

    required = [
        A.GEN_AI_SYSTEM,
        A.GEN_AI_OPERATION_NAME,
        A.AGENT_ID,
        A.AGENT_PROFILE_TYPE,
        A.AGENT_GOAL,
        A.TOOL_CALL_COUNT,
    ]
    for attr in required:
        assert attr in session.attributes, f"agent.session missing attribute: {attr}"


async def test_agent_planning_parent_is_session(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    planning = span_by_name(memory_tracer[1], "agent.planning")
    parent = find_parent(spans, planning)
    assert parent is not None and parent.name == "agent.session"


async def test_tool_call_parent_is_session(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    tool_span = spans_by_name(memory_tracer[1], "tool.call")[0]
    parent = find_parent(spans, tool_span)
    assert parent is not None and parent.name == "agent.session"


async def test_llm_inference_parent_is_tool_call(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    llm_span = spans_by_name(memory_tracer[1], "llm.inference")[0]
    parent = find_parent(spans, llm_span)
    assert parent is not None and parent.name == "tool.call"


async def test_agent_output_parent_is_llm_inference(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    output_span = spans_by_name(memory_tracer[1], "agent.output")[0]
    parent = find_parent(spans, output_span)
    assert parent is not None and parent.name == "llm.inference"


async def test_all_spans_share_single_trace_id(
    seeded_dist, rag_profile, memory_tracer, fast_clock
):
    spans = await _run(seeded_dist, rag_profile, memory_tracer, fast_clock)
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1, f"Expected 1 trace_id, got {len(trace_ids)}"
