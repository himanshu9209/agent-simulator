import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from simulator.behavior.distributions import Distributions
from simulator.clock import ClockController
from simulator.config import (
    AgentProfile,
    GaussianDistribution,
    UniformIntDistribution,
)


@pytest.fixture
def seeded_dist() -> Distributions:
    return Distributions.from_seed(42)


@pytest.fixture
def rag_profile() -> AgentProfile:
    return AgentProfile(
        tools=["vector_search", "reranker", "summariser"],
        llm_model="gpt-4o",
        llm_input_tokens=GaussianDistribution(mean=1200, std=300),
        llm_output_tokens=GaussianDistribution(mean=250, std=80),
        planning_latency_ms=GaussianDistribution(mean=200, std=50),
        tool_call_count=UniformIntDistribution(min=1, max=5),
        failure_rate=0.0,
    )


@pytest.fixture
def memory_tracer():
    """OTel TracerProvider backed by InMemorySpanExporter. Returns (tracer, exporter)."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    return tracer, exporter


@pytest.fixture
def fast_clock() -> ClockController:
    return ClockController(clock_multiplier=10_000.0)
