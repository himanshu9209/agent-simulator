from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from simulator.config import RootConfig

logger = logging.getLogger(__name__)

_RESOURCE = Resource.create(
    {
        "service.name": "agent-simulator",
        "service.version": "0.2.0",
    }
)


def _resolve_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Resolve ``${ENV_VAR}`` references in OTLP header values.

    Literal values are passed through unchanged.  A value like
    ``"${HONEYCOMB_API_KEY}"`` is replaced with the contents of that
    environment variable.  If the variable is unset an empty string is used
    and a warning is logged so the user knows something is misconfigured.
    """
    resolved: Dict[str, str] = {}
    for key, value in headers.items():
        if value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            resolved_val = os.environ.get(env_var, "")
            if not resolved_val:
                logger.warning(
                    "OTLP header '%s' references unset env var '%s' — sending empty value",
                    key,
                    env_var,
                )
            resolved[key] = resolved_val
        else:
            resolved[key] = value
    return resolved


def build_tracer_provider(config: RootConfig) -> TracerProvider:
    headers: Optional[Dict[str, str]] = (
        _resolve_headers(config.telemetry.headers)
        if config.telemetry.headers
        else None
    )
    exporter = OTLPSpanExporter(
        endpoint=config.telemetry.exporter_endpoint,
        insecure=config.telemetry.tls.insecure,
        headers=headers,
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
