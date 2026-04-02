from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from simulator.config import RootConfig
from simulator.telemetry.emitter import _RESOURCE


def build_meter_provider(config: RootConfig) -> MeterProvider:
    exporter = OTLPMetricExporter(
        endpoint=config.telemetry.exporter_endpoint,
        insecure=True,
    )
    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=config.telemetry.export_interval_ms,
    )
    provider = MeterProvider(resource=_RESOURCE, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    return provider


class SimulatorMetrics:

    def __init__(self, meter: metrics.Meter) -> None:
        self._input_tokens = meter.create_counter(
            "simulator.tokens.input",
            unit="tokens",
            description="Total LLM input tokens consumed",
        )
        self._output_tokens = meter.create_counter(
            "simulator.tokens.output",
            unit="tokens",
            description="Total LLM output tokens produced",
        )
        self._llm_latency = meter.create_histogram(
            "simulator.llm.latency",
            unit="ms",
            description="Simulated LLM inference latency",
        )
        self._session_duration = meter.create_histogram(
            "simulator.session.duration",
            unit="s",
            description="Simulated agent session duration",
        )
        self._session_errors = meter.create_counter(
            "simulator.session.errors",
            description="Agent sessions that ended in error",
        )
        self._tool_calls = meter.create_counter(
            "simulator.tool.calls",
            description="Tool calls executed",
        )
        self._cost_total = meter.create_counter(
            "agent.cost.total_usd",
            unit="USD",
            description="Cumulative LLM cost across all sessions",
        )
        self._cost_per_session = meter.create_histogram(
            "agent.cost.per_session_usd",
            unit="USD",
            description="LLM cost distribution per completed session",
        )

    @classmethod
    def from_config(cls, config: RootConfig) -> "SimulatorMetrics":
        meter = metrics.get_meter("agent-simulator")
        return cls(meter)

    def record_tokens(
        self, input_tokens: int, output_tokens: int, model: str, profile: str
    ) -> None:
        attrs = {"gen_ai.model": model, "agent.profile_type": profile}
        self._input_tokens.add(input_tokens, attrs)
        self._output_tokens.add(output_tokens, attrs)

    def record_llm_latency(self, latency_ms: float, model: str, profile: str) -> None:
        self._llm_latency.record(
            latency_ms, {"gen_ai.model": model, "agent.profile_type": profile}
        )

    def record_tool_call(self, tool_name: str, profile: str) -> None:
        self._tool_calls.add(1, {"tool.name": tool_name, "agent.profile_type": profile})

    def record_session_end(
        self,
        duration_s: float,
        profile: str,
        scenario: str | None,
        error: bool,
    ) -> None:
        attrs = {
            "agent.profile_type": profile,
            "scenario.type": scenario or "none",
            "error": str(error).lower(),
        }
        self._session_duration.record(duration_s, attrs)
        if error:
            self._session_errors.add(1, {"agent.profile_type": profile})

    def record_cost(self, session_cost_usd: float, model: str, profile: str) -> None:
        attrs = {"gen_ai.model": model, "agent.profile_type": profile}
        self._cost_total.add(session_cost_usd, attrs)
        self._cost_per_session.record(session_cost_usd, attrs)
