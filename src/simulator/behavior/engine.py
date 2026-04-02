from __future__ import annotations

import time
import uuid

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from simulator.behavior.distributions import Distributions
from simulator.behavior.sampler import AttributeSampler
from simulator.clock import ClockController
from simulator.config import AgentProfile
from simulator.scenarios.types import ScenarioType
from simulator.telemetry import attributes as A

_SAMPLER = AttributeSampler()


AGENT_GOALS = [
    "Summarise Q3 financial results",
    "Research competitor pricing for SaaS market",
    "Generate executive briefing from meeting notes",
    "Analyse customer churn signals in CRM data",
    "Draft technical design for new auth service",
    "Evaluate third-party vendor security posture",
    "Generate weekly pipeline health report",
    "Identify anomalies in production error logs",
]


async def run_agent_session(
    profile_name: str,
    profile: AgentProfile,
    dist: Distributions,
    tracer: trace.Tracer,
    clock: ClockController,
    scenario: ScenarioType | None = None,
    metrics=None,
) -> None:
    agent_id = str(uuid.uuid4())
    goal = dist.choice(AGENT_GOALS)
    tool_count = dist.uniform_int(profile.tool_call_count)
    session_error = False

    if scenario == ScenarioType.INFINITE_RETRY_LOOP:
        tool_count = dist.randint(10, 20)

    session_attrs: dict = {
        A.GEN_AI_SYSTEM: A.SYSTEM_SIMULATED,
        A.GEN_AI_OPERATION_NAME: A.OP_AGENT_SESSION,
        A.AGENT_ID: agent_id,
        A.AGENT_PROFILE_TYPE: profile_name,
        A.AGENT_GOAL: goal,
        A.TOOL_CALL_COUNT: tool_count,
    }
    if scenario is not None:
        session_attrs[A.SCENARIO_TYPE] = scenario.value

    session_start = time.monotonic()

    with tracer.start_as_current_span(
        "agent.session",
        kind=SpanKind.SERVER,
        attributes=session_attrs,
    ) as session_span:

        for attr_name, attr_cfg in profile.observability_attributes.session.items():
            session_span.set_attribute(attr_name, _SAMPLER.sample(attr_cfg, dist._rng))

        with tracer.start_as_current_span(
            "agent.planning",
            attributes={
                A.GEN_AI_SYSTEM: A.SYSTEM_SIMULATED,
                A.GEN_AI_OPERATION_NAME: A.OP_AGENT_SESSION,
                A.AGENT_ID: agent_id,
            },
        ):
            latency_ms = dist.gaussian_ms(profile.planning_latency_ms)
            await clock.scaled_sleep(latency_ms / 1000.0)

            if scenario == ScenarioType.GOAL_DRIFT:
                other_goals = [g for g in AGENT_GOALS if g != goal]
                new_goal = dist.choice(other_goals)
                session_span.set_attribute(A.AGENT_GOAL, new_goal)

        for i in range(tool_count):
            tool_name = dist.choice(profile.tools)

            if metrics:
                metrics.record_tool_call(tool_name, profile_name)

            with tracer.start_as_current_span(
                "tool.call",
                attributes={
                    A.GEN_AI_SYSTEM: A.SYSTEM_SIMULATED,
                    A.GEN_AI_OPERATION_NAME: A.OP_TOOL_CALL,
                    A.TOOL_NAME: tool_name,
                    A.TOOL_CALL_INDEX: i,
                    A.AGENT_ID: agent_id,
                },
            ) as tool_span:

                if scenario == ScenarioType.TOOL_TIMEOUT:
                    tool_span.set_attribute(A.ERROR_TYPE, "timeout")
                    tool_span.set_status(Status(StatusCode.ERROR, "Tool timeout"))
                    session_span.set_status(Status(StatusCode.ERROR, "Tool timeout"))
                    await clock.scaled_sleep(
                        dist.gaussian_ms(profile.planning_latency_ms) / 1000.0
                    )
                    if metrics:
                        elapsed = (time.monotonic() - session_start) * clock.multiplier
                        metrics.record_session_end(
                            elapsed, profile_name,
                            scenario.value if scenario else None, error=True
                        )
                    return

                tool_latency_ms = dist.gaussian_ms(
                    profile.planning_latency_ms, minimum_ms=10.0
                )
                await clock.scaled_sleep(tool_latency_ms / 1000.0)

                for attr_name, attr_cfg in profile.observability_attributes.tool.items():
                    tool_span.set_attribute(attr_name, _SAMPLER.sample(attr_cfg, dist._rng))

                input_tokens = dist.gaussian_int(profile.llm_input_tokens)
                output_tokens = dist.gaussian_int(profile.llm_output_tokens)

                if scenario == ScenarioType.CONTEXT_OVERFLOW:
                    input_tokens = dist.randint(8001, 12000)

                with tracer.start_as_current_span(
                    "llm.inference",
                    attributes={
                        A.GEN_AI_SYSTEM: A.SYSTEM_SIMULATED,
                        A.GEN_AI_OPERATION_NAME: A.OP_CHAT,
                        A.GEN_AI_MODEL: profile.llm_model,
                        A.GEN_AI_INPUT_TOKENS: input_tokens,
                        A.GEN_AI_OUTPUT_TOKENS: output_tokens,
                        A.AGENT_ID: agent_id,
                    },
                ) as inference_span:
                    llm_start = time.monotonic()
                    for attr_name, attr_cfg in profile.observability_attributes.inference.items():
                        inference_span.set_attribute(attr_name, _SAMPLER.sample(attr_cfg, dist._rng))
                    await clock.scaled_sleep(output_tokens * 5.0 / 1000.0)

                    if metrics:
                        llm_ms = (time.monotonic() - llm_start) * 1000 * clock.multiplier
                        metrics.record_tokens(
                            input_tokens, output_tokens, profile.llm_model, profile_name
                        )
                        metrics.record_llm_latency(llm_ms, profile.llm_model, profile_name)

                    if scenario == ScenarioType.SILENT_FAILURE:
                        is_failure = False
                        output_attrs: dict = {
                            A.GEN_AI_SYSTEM: A.SYSTEM_SIMULATED,
                            A.GEN_AI_OPERATION_NAME: A.OP_AGENT_SESSION,
                            A.AGENT_ID: agent_id,
                            A.AGENT_STATUS: "success",
                            "agent.output.score": 0,
                        }
                    else:
                        is_failure = dist.bernoulli(profile.failure_rate)
                        output_attrs = {
                            A.GEN_AI_SYSTEM: A.SYSTEM_SIMULATED,
                            A.GEN_AI_OPERATION_NAME: A.OP_AGENT_SESSION,
                            A.AGENT_ID: agent_id,
                            A.AGENT_STATUS: "error" if is_failure else "success",
                        }

                    with tracer.start_as_current_span(
                        "agent.output",
                        attributes=output_attrs,
                    ) as output_span:
                        if is_failure:
                            session_error = True
                            output_span.set_status(
                                Status(StatusCode.ERROR, "Simulated agent failure")
                            )
                            session_span.set_status(
                                Status(StatusCode.ERROR, "Simulated agent failure")
                            )

    if metrics:
        elapsed = (time.monotonic() - session_start) * clock.multiplier
        metrics.record_session_end(
            elapsed, profile_name,
            scenario.value if scenario else None, error=session_error
        )
