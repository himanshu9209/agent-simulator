"""
tools/schema_generator.py
Generates a starter YAML agent profile from a real OTLP JSON export.

Usage:
  python -m tools.schema_generator \\
      --input path/to/real_traces.json \\
      --profile-name my_real_agent \\
      --output config/profiles/my_real_agent.yaml

What it does:
  1. Reads all spans from the OTLP JSON export.
  2. Groups spans by name into session / tool / inference buckets.
  3. For each attribute on each span type:
     - Infers the attribute type (float, int, enum, boolean).
     - Computes observed min/max/mean/std (numeric) or value list (enum).
  4. Emits a ready-to-use YAML profile the simulator can run immediately.

The output is a complete agent_profiles block that can be dropped into
config/default.yaml or used as a standalone config file.
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

# Allow running as `python -m tools.schema_generator` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._otel_parser import group_by_span_name, parse_otlp_json


# ---------------------------------------------------------------------------
# Span-name buckets
# ---------------------------------------------------------------------------

_SESSION_SPANS = {"agent.session"}
_TOOL_SPANS = {"tool.call"}
_INFERENCE_SPANS = {"llm.inference"}

_INTERNAL_KEYS = {
    # Keys the simulator manages internally — skip in observability_attributes.
    "gen_ai.system", "gen_ai.operation.name", "gen_ai.model",
    "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
    "gen_ai.usage.cost_usd", "gen_ai.usage.input_cost_usd",
    "gen_ai.usage.output_cost_usd",
    "agent.id", "agent.profile_type", "agent.goal", "agent.status",
    "tool.call_count", "tool.name", "tool.call_index",
    "scenario.type", "error.type",
    "tool.sequence_position", "tool.sequence_deviation",
    "tool.selection_quality", "tool.retry_reason",
    "tool.sandbox_escalation",
    "planning.quality_score", "planning.replanning_triggered",
    "inference.model_switched", "inference.original_model",
    "session.goal_drift_detected", "session.original_goal", "session.final_goal",
    "session.total_cost_usd", "session.avg_cost_per_tool_call_usd",
}


# ---------------------------------------------------------------------------
# Type inference and stats
# ---------------------------------------------------------------------------

def _infer_type(values: list[Any]) -> str:
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "int"
    if all(isinstance(v, float) for v in values):
        return "float"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "float"
    return "enum"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _build_attr_config(attr_type: str, values: list[Any]) -> dict:
    """Return the YAML dict for a single observability_attribute entry."""
    if attr_type == "boolean":
        true_count = sum(1 for v in values if v)
        probability = round(true_count / len(values), 3) if values else 0.5
        return {"type": "boolean", "probability": probability}

    if attr_type == "enum":
        unique = sorted({str(v) for v in values})
        return {"type": "enum", "values": unique}

    numerics = [float(v) for v in values]
    mn = min(numerics)
    mx = max(numerics)
    avg = _mean(numerics)
    sd = _std(numerics, avg)

    if attr_type == "int":
        return {
            "type": "int",
            "min": int(mn),
            "max": int(mx),
        }

    # float
    cfg: dict = {
        "type": "float",
        "min": round(mn, 4),
        "max": round(mx, 4),
    }
    if sd > 0:
        cfg["mean"] = round(avg, 4)
        cfg["std"] = round(sd, 4)
    return cfg


def _collect_attrs(spans: list, skip: set) -> dict[str, dict]:
    """Gather per-attribute value lists across a list of SpanRecord objects."""
    collector: dict[str, list] = defaultdict(list)
    for span in spans:
        for key, value in span.attributes.items():
            if key in skip or not key:
                continue
            collector[key].append(value)
    return {key: vals for key, vals in collector.items() if vals}


def _build_span_schema(spans: list, skip: set) -> dict[str, dict]:
    attrs = _collect_attrs(spans, skip)
    schema: dict[str, dict] = {}
    for key, values in attrs.items():
        inferred = _infer_type(values)
        schema[key] = _build_attr_config(inferred, values)
    return schema


# ---------------------------------------------------------------------------
# Profile-level stats from session spans
# ---------------------------------------------------------------------------

def _extract_llm_stats(inference_spans: list) -> dict:
    """Estimate token distributions from llm.inference spans."""
    input_tokens = [
        s.attributes["gen_ai.usage.input_tokens"]
        for s in inference_spans
        if "gen_ai.usage.input_tokens" in s.attributes
    ]
    output_tokens = [
        s.attributes["gen_ai.usage.output_tokens"]
        for s in inference_spans
        if "gen_ai.usage.output_tokens" in s.attributes
    ]
    models = [
        s.attributes["gen_ai.model"]
        for s in inference_spans
        if "gen_ai.model" in s.attributes
    ]

    result: dict = {}
    if models:
        from collections import Counter
        most_common = Counter(models).most_common(1)[0][0]
        result["llm_model"] = most_common

    if input_tokens:
        avg = _mean([float(t) for t in input_tokens])
        sd = _std([float(t) for t in input_tokens], avg)
        result["llm_input_tokens"] = {
            "mean": round(avg),
            "std": max(1, round(sd)),
        }
    if output_tokens:
        avg = _mean([float(t) for t in output_tokens])
        sd = _std([float(t) for t in output_tokens], avg)
        result["llm_output_tokens"] = {
            "mean": round(avg),
            "std": max(1, round(sd)),
        }
    return result


def _extract_tool_names(tool_spans: list) -> list[str]:
    names = sorted({
        s.attributes["tool.name"]
        for s in tool_spans
        if "tool.name" in s.attributes
    })
    return names or ["unknown_tool"]


def _extract_tool_call_count(session_spans: list) -> dict:
    counts = [
        s.attributes["tool.call_count"]
        for s in session_spans
        if "tool.call_count" in s.attributes
    ]
    if not counts:
        return {"min": 1, "max": 5}
    return {"min": int(min(counts)), "max": int(max(counts))}


def _extract_planning_latency(planning_spans: list) -> dict:
    durations_ms = [
        round(s.duration_ns / 1_000_000)
        for s in planning_spans
        if s.duration_ns > 0
    ]
    if not durations_ms:
        return {"mean": 200, "std": 50}
    avg = _mean([float(d) for d in durations_ms])
    sd = _std([float(d) for d in durations_ms], avg)
    return {"mean": round(avg), "std": max(1, round(sd))}


def _extract_failure_rate(session_spans: list) -> float:
    statuses = [
        s.attributes.get("agent.status", "success")
        for s in session_spans
    ]
    if not statuses:
        return 0.05
    errors = sum(1 for s in statuses if s == "error")
    return round(errors / len(statuses), 4)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_profile(
    otlp_path: str | Path,
    profile_name: str,
) -> dict:
    """
    Parse an OTLP JSON export and return a dict representing a single
    agent_profiles entry ready to be serialised as YAML.
    """
    spans = parse_otlp_json(otlp_path)
    by_name = group_by_span_name(spans)

    session_spans = [s for name in _SESSION_SPANS for s in by_name.get(name, [])]
    tool_spans = [s for name in _TOOL_SPANS for s in by_name.get(name, [])]
    inference_spans = [s for name in _INFERENCE_SPANS for s in by_name.get(name, [])]
    planning_spans = by_name.get("agent.planning", [])

    llm_stats = _extract_llm_stats(inference_spans)
    planning_lat = _extract_planning_latency(planning_spans)

    profile: dict = {
        "mix_weight": 1.0,
        "tools": _extract_tool_names(tool_spans),
        "llm_model": llm_stats.get("llm_model", "gpt-4o"),
        "llm_input_tokens": llm_stats.get("llm_input_tokens", {"mean": 800, "std": 200}),
        "llm_output_tokens": llm_stats.get("llm_output_tokens", {"mean": 300, "std": 80}),
        "planning_latency_ms": planning_lat,
        "tool_call_count": _extract_tool_call_count(session_spans),
        "failure_rate": _extract_failure_rate(session_spans),
    }

    # Build observability_attributes schema
    session_schema = _build_span_schema(session_spans, _INTERNAL_KEYS)
    tool_schema = _build_span_schema(tool_spans, _INTERNAL_KEYS)
    inference_schema = _build_span_schema(inference_spans, _INTERNAL_KEYS)

    obs_attrs: dict = {}
    if session_schema:
        obs_attrs["session"] = session_schema
    if tool_schema:
        obs_attrs["tool"] = tool_schema
    if inference_schema:
        obs_attrs["inference"] = inference_schema

    if obs_attrs:
        profile["observability_attributes"] = obs_attrs

    return {profile_name: profile}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a simulator YAML profile from a real OTLP JSON export."
    )
    parser.add_argument("--input", required=True, help="Path to OTLP JSON export")
    parser.add_argument("--profile-name", required=True, help="Name for the generated profile")
    parser.add_argument(
        "--output",
        default=None,
        help="Output YAML path (default: stdout)",
    )
    args = parser.parse_args()

    profile_dict = generate_profile(args.input, args.profile_name)
    output = yaml.dump(
        {"agent_profiles": profile_dict},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Profile written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
