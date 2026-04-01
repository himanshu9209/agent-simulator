from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from simulator.config import RootConfig


_RESOURCE = Resource.create(
    {
        "service.name": "agent-simulator",
        "service.version": "0.2.0",
    }
)


def build_tracer_provider(config: RootConfig) -> TracerProvider:
    exporter = OTLPSpanExporter(
        endpoint=config.telemetry.exporter_endpoint,
        insecure=True,
    )
    processor = BatchSpanProcessor(
        exporter,
        max_export_batch_size=config.telemetry.batch_size,
        schedule_delay_millis=config.telemetry.export_interval_ms,
    )
    provider = TracerProvider(resource=_RESOURCE)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return provider


def get_tracer(name: str = "agent-simulator") -> trace.Tracer:
    return trace.get_tracer(name)
