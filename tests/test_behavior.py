from __future__ import annotations

from opentelemetry.trace import SpanKind

from simulator.behavior.engine import run_agent_session
from simulator.telemetry import attributes as A


async def test_span_tree_has_required_span_names(seeded_dist, rag_profile, memory_tracer, fast_clock):
    """Every session must produce the expected span names."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    span_names = {s.name for s in exporter.get_finished_spans()}
    assert "agent.session" in span_names
    assert "agent.planning" in span_names
    assert "tool.call" in span_names
    assert "llm.inference" in span_names
    assert "agent.output" in span_names


async def test_root_span_is_server_kind(seeded_dist, rag_profile, memory_tracer, fast_clock):
    """agent.session must be SpanKind.SERVER."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    root = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    assert root.kind == SpanKind.SERVER


async def test_root_span_has_required_attributes(seeded_dist, rag_profile, memory_tracer, fast_clock):
    """GenAI semantic convention attributes must be present on agent.session."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    root = next(s for s in exporter.get_finished_spans() if s.name == "agent.session")
    attrs = root.attributes

    assert attrs[A.GEN_AI_SYSTEM] == A.SYSTEM_SIMULATED
    assert attrs[A.GEN_AI_OPERATION_NAME] == A.OP_AGENT_SESSION
    assert A.AGENT_ID in attrs
    assert attrs[A.AGENT_PROFILE_TYPE] == "rag_researcher"
    assert A.AGENT_GOAL in attrs
    assert isinstance(attrs[A.TOOL_CALL_COUNT], int)
    assert attrs[A.TOOL_CALL_COUNT] >= 1


async def test_llm_inference_token_attributes(seeded_dist, rag_profile, memory_tracer, fast_clock):
    """llm.inference spans must carry positive integer token counts and model name."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    llm_spans = [s for s in exporter.get_finished_spans() if s.name == "llm.inference"]
    assert len(llm_spans) >= 1

    for span in llm_spans:
        assert span.attributes[A.GEN_AI_INPUT_TOKENS] >= 1
        assert span.attributes[A.GEN_AI_OUTPUT_TOKENS] >= 1
        assert span.attributes[A.GEN_AI_MODEL] == "gpt-4o"


async def test_all_spans_share_trace_id(seeded_dist, rag_profile, memory_tracer, fast_clock):
    """All spans in a session must share the same trace_id."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    spans = exporter.get_finished_spans()
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1, f"Expected 1 trace_id, got: {trace_ids}"


async def test_tool_call_count_matches_span_count(seeded_dist, rag_profile, memory_tracer, fast_clock):
    """Number of tool.call spans must match tool.call.count on the root span."""
    tracer, exporter = memory_tracer
    await run_agent_session(
        profile_name="rag_researcher",
        profile=rag_profile,
        dist=seeded_dist,
        tracer=tracer,
        clock=fast_clock,
    )

    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "agent.session")
    tool_spans = [s for s in spans if s.name == "tool.call"]

    assert len(tool_spans) == root.attributes[A.TOOL_CALL_COUNT]


async def test_gaussian_int_always_positive(seeded_dist, rag_profile):
    """gaussian_int must never return a value below 1."""
    for _ in range(200):
        val = seeded_dist.gaussian_int(rag_profile.llm_input_tokens)
        assert val >= 1


async def test_config_loads_all_five_profiles():
    """default.yaml must load all five agent profiles with valid mix_weights."""
    from pathlib import Path
    from simulator.config import load_config

    config_path = Path(__file__).parent.parent / "config" / "default.yaml"
    config = load_config(config_path)

    expected = {"rag_researcher", "code_executor", "web_scraper", "data_analyst", "api_orchestrator"}
    assert set(config.agent_profiles) == expected

    for name, profile in config.agent_profiles.items():
        assert profile.mix_weight > 0, f"{name}.mix_weight must be > 0"
        assert len(profile.tools) > 0, f"{name} must have at least one tool"

    assert config.simulator.random_seed == 42
    assert config.simulator.concurrency >= 1


async def test_clock_controller_scaled_sleep(fast_clock):
    """scaled_sleep at 10000x should return almost instantly."""
    import time
    start = time.monotonic()
    await fast_clock.scaled_sleep(10.0)  # 10 real seconds → ~1ms
    elapsed = time.monotonic() - start
    assert elapsed < 0.1, f"Expected <0.1s, got {elapsed:.3f}s"


async def test_profile_mix_selection():
    """Profile selection must respect mix_weight proportions over many draws."""
    import random
    from simulator.core import _select_profile
    from simulator.config import load_config
    from pathlib import Path

    config = load_config(Path(__file__).parent.parent / "config" / "default.yaml")
    rng = random.Random(0)
    counts: dict[str, int] = {k: 0 for k in config.agent_profiles}

    for _ in range(1000):
        name, _ = _select_profile(config.agent_profiles, rng)
        counts[name] += 1

    # rag_researcher has weight 3.0, api_orchestrator has 1.0 — rag should appear ~3x more
    assert counts["rag_researcher"] > counts["api_orchestrator"] * 1.5
