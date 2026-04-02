"""
tests/test_digital_twin.py
Digital Twin Validation — Phase 5 tests.

Covers:
  1. OTLP JSON parsing (_otel_parser.py)
  2. Schema generation from parsed traces (schema_generator.py)
  3. Validation logic: missing attrs, type mismatches, range violations (validate.py)
  4. Pre-built schema YAML files load cleanly through load_config()
  5. ValidationConfig is honoured in RootConfig
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from simulator.config import (
    RootConfig,
    ValidationConfig,
    ValidationToleranceConfig,
    load_config,
)
from tools._otel_parser import (
    SpanRecord,
    _decode_value,
    group_by_span_name,
    parse_otlp_json_from_dict,
)
from tools.schema_generator import generate_profile
from tools.validate import ValidationIssue, ValidationReport, validate

# ---------------------------------------------------------------------------
# Helpers — minimal OTLP JSON builders
# ---------------------------------------------------------------------------

_SCHEMAS_DIR = Path(__file__).parent.parent / "config" / "schemas"


def _make_attr(key: str, value) -> dict:
    """Encode a key/value pair as an OTLP attribute dict."""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def _make_span(
    name: str,
    attrs: dict,
    span_id: str = "aaa",
    parent_id: str | None = None,
    start_ns: int = 0,
    end_ns: int = 1_000_000,
) -> dict:
    span: dict = {
        "name": name,
        "traceId": "trace1",
        "spanId": span_id,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": [_make_attr(k, v) for k, v in attrs.items()],
    }
    if parent_id:
        span["parentSpanId"] = parent_id
    return span


def _make_otlp(spans: list[dict]) -> dict:
    return {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {"spans": spans}
                ]
            }
        ]
    }


# ---------------------------------------------------------------------------
# 1. OTLP parser
# ---------------------------------------------------------------------------

class TestOtlpParser:

    def test_decode_string_value(self):
        assert _decode_value({"stringValue": "hello"}) == "hello"

    def test_decode_int_value_encoded_as_string(self):
        result = _decode_value({"intValue": "42"})
        assert result == 42
        assert isinstance(result, int)

    def test_decode_double_value(self):
        result = _decode_value({"doubleValue": 3.14})
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-9

    def test_decode_bool_value(self):
        assert _decode_value({"boolValue": True}) is True
        assert _decode_value({"boolValue": False}) is False

    def test_decode_unknown_falls_back_to_dict(self):
        raw = {"kvlistValue": {"values": []}}
        result = _decode_value(raw)
        assert isinstance(result, dict)

    def test_parse_multiple_spans(self):
        data = _make_otlp([
            _make_span("agent.session", {"agent.id": "x", "tool.call_count": 3}),
            _make_span("tool.call", {"tool.name": "search"}, parent_id="session1"),
        ])
        records = parse_otlp_json_from_dict(data)
        assert len(records) == 2
        names = {r.name for r in records}
        assert names == {"agent.session", "tool.call"}

    def test_duration_calculated_from_timestamps(self):
        data = _make_otlp([
            _make_span("agent.session", {}, start_ns=1_000_000, end_ns=5_000_000)
        ])
        records = parse_otlp_json_from_dict(data)
        assert records[0].duration_ns == 4_000_000

    def test_group_by_span_name(self):
        records = [
            SpanRecord("tool.call", "t1", "s1", None, {}),
            SpanRecord("tool.call", "t1", "s2", None, {}),
            SpanRecord("llm.inference", "t1", "s3", None, {}),
        ]
        groups = group_by_span_name(records)
        assert len(groups["tool.call"]) == 2
        assert len(groups["llm.inference"]) == 1

    def test_parent_span_id_captured(self):
        data = _make_otlp([
            _make_span("tool.call", {}, span_id="child", parent_id="parent123")
        ])
        records = parse_otlp_json_from_dict(data)
        assert records[0].parent_span_id == "parent123"

    def test_no_parent_span_id_is_none(self):
        data = _make_otlp([_make_span("agent.session", {})])
        records = parse_otlp_json_from_dict(data)
        assert records[0].parent_span_id is None

    def test_attributes_decoded_correctly(self):
        data = _make_otlp([
            _make_span("agent.session", {
                "tool.call_count": 5,
                "agent.goal": "research something",
                "failure.rate": 0.05,
                "session.error": False,
            })
        ])
        records = parse_otlp_json_from_dict(data)
        attrs = records[0].attributes
        assert attrs["tool.call_count"] == 5
        assert attrs["agent.goal"] == "research something"
        assert abs(attrs["failure.rate"] - 0.05) < 1e-9
        assert attrs["session.error"] is False


# ---------------------------------------------------------------------------
# 2. Schema generator
# ---------------------------------------------------------------------------

class TestSchemaGenerator:

    def _make_export_file(self, tmp_path: Path, spans: list[dict]) -> Path:
        path = tmp_path / "traces.json"
        path.write_text(json.dumps(_make_otlp(spans)), encoding="utf-8")
        return path

    def test_generates_profile_dict_with_correct_name(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("agent.session", {"tool.call_count": 3, "gen_ai.model": "gpt-4o"}),
        ])
        result = generate_profile(export, "my_agent")
        assert "my_agent" in result

    def test_infers_tool_names_from_tool_spans(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("tool.call", {"tool.name": "search", "tool.call_index": 0}),
            _make_span("tool.call", {"tool.name": "summariser", "tool.call_index": 1}),
        ])
        result = generate_profile(export, "p")
        tools = result["p"]["tools"]
        assert "search" in tools
        assert "summariser" in tools

    def test_infers_tool_call_count_from_session(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("agent.session", {"tool.call_count": 2}),
            _make_span("agent.session", {"tool.call_count": 5}),
        ])
        result = generate_profile(export, "p")
        tcc = result["p"]["tool_call_count"]
        assert tcc["min"] == 2
        assert tcc["max"] == 5

    def test_excludes_internal_keys_from_schema(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("agent.session", {
                "gen_ai.system": "simulated",     # internal
                "retrieval.score": 0.85,          # custom
            }),
        ])
        result = generate_profile(export, "p")
        session_attrs = result["p"].get("observability_attributes", {}).get("session", {})
        assert "gen_ai.system" not in session_attrs
        assert "retrieval.score" in session_attrs

    def test_boolean_attr_has_probability(self, tmp_path):
        # All True → probability 1.0
        export = self._make_export_file(tmp_path, [
            _make_span("tool.call", {"tool.cache_hit": True}),
            _make_span("tool.call", {"tool.cache_hit": True}),
            _make_span("tool.call", {"tool.cache_hit": False}),
        ])
        result = generate_profile(export, "p")
        cache_hit = result["p"]["observability_attributes"]["tool"]["tool.cache_hit"]
        assert cache_hit["type"] == "boolean"
        assert abs(cache_hit["probability"] - (2 / 3)) < 0.01

    def test_enum_attr_has_values_list(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("tool.call", {"http.status_code": "200"}),
            _make_span("tool.call", {"http.status_code": "404"}),
            _make_span("tool.call", {"http.status_code": "200"}),
        ])
        result = generate_profile(export, "p")
        status = result["p"]["observability_attributes"]["tool"]["http.status_code"]
        assert status["type"] == "enum"
        assert set(status["values"]) == {"200", "404"}

    def test_numeric_attr_has_min_max(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("tool.call", {"retrieval.latency.ms": 120.5}),
            _make_span("tool.call", {"retrieval.latency.ms": 850.0}),
        ])
        result = generate_profile(export, "p")
        lat = result["p"]["observability_attributes"]["tool"]["retrieval.latency.ms"]
        assert lat["min"] <= 120.5
        assert lat["max"] >= 850.0

    def test_llm_model_from_inference_spans(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("llm.inference", {"gen_ai.model": "gpt-4o", "gen_ai.usage.input_tokens": 500}),
            _make_span("llm.inference", {"gen_ai.model": "gpt-4o", "gen_ai.usage.input_tokens": 700}),
        ])
        result = generate_profile(export, "p")
        assert result["p"]["llm_model"] == "gpt-4o"

    def test_failure_rate_calculated(self, tmp_path):
        export = self._make_export_file(tmp_path, [
            _make_span("agent.session", {"agent.status": "success"}),
            _make_span("agent.session", {"agent.status": "success"}),
            _make_span("agent.session", {"agent.status": "error"}),
        ])
        result = generate_profile(export, "p")
        assert abs(result["p"]["failure_rate"] - (1 / 3)) < 0.01


# ---------------------------------------------------------------------------
# 3. Validate — gap detection
# ---------------------------------------------------------------------------

class TestValidate:

    def _write_export(self, tmp_path: Path, spans: list[dict]) -> Path:
        path = tmp_path / "traces.json"
        path.write_text(json.dumps(_make_otlp(spans)), encoding="utf-8")
        return path

    def _write_config(self, tmp_path: Path, profile_name: str, profile_body: dict) -> Path:
        import yaml
        config = {
            "simulator": {"concurrency": 1, "run_duration_seconds": 10},
            "scenarios": {"enabled": {}},
            "agent_profiles": {
                profile_name: {
                    "tools": ["tool_a"],
                    "llm_model": "gpt-4o",
                    "llm_input_tokens": {"mean": 500, "std": 50},
                    "llm_output_tokens": {"mean": 100, "std": 10},
                    "planning_latency_ms": {"mean": 100, "std": 10},
                    "tool_call_count": {"min": 1, "max": 3},
                    "failure_rate": 0.05,
                    **profile_body,
                }
            },
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(config), encoding="utf-8")
        return path

    def test_no_issues_when_attrs_match(self, tmp_path):
        export = self._write_export(tmp_path, [
            _make_span("tool.call", {"retrieval.latency.ms": 300.0}),
        ])
        cfg = self._write_config(tmp_path, "p", {
            "observability_attributes": {
                "tool": {"retrieval.latency.ms": {"type": "float", "min": 0.0, "max": 5000.0}},
            }
        })
        report = validate(export, cfg, "p")
        # No type mismatches and no range violations expected
        errors = [i for i in report.issues if i.severity == "error"]
        assert len(errors) == 0

    def test_missing_attr_raises_warning(self, tmp_path):
        export = self._write_export(tmp_path, [
            _make_span("tool.call", {"http.status_code": "200"}),
        ])
        cfg = self._write_config(tmp_path, "p", {
            "observability_attributes": {"tool": {}}  # nothing declared
        })
        report = validate(export, cfg, "p")
        warnings = [i for i in report.issues if i.severity == "warning" and i.attribute == "http.status_code"]
        assert len(warnings) >= 1
        assert "not declared" in warnings[0].message.lower() or "not found" in warnings[0].message.lower()

    def test_type_mismatch_raises_error(self, tmp_path):
        # Real trace has float, profile declares int
        export = self._write_export(tmp_path, [
            _make_span("tool.call", {"retrieval.latency.ms": 300.5}),
        ])
        cfg = self._write_config(tmp_path, "p", {
            "observability_attributes": {
                "tool": {"retrieval.latency.ms": {"type": "int", "min": 0, "max": 5000}},
            }
        })
        report = validate(export, cfg, "p")
        errors = [i for i in report.issues if i.severity == "error" and "retrieval.latency.ms" in i.attribute]
        assert len(errors) >= 1

    def test_range_violation_raises_warning(self, tmp_path):
        # Real trace max=500, declared max=100 — should warn
        export = self._write_export(tmp_path, [
            _make_span("tool.call", {"chunk.size.tokens": 500}),
        ])
        cfg = self._write_config(tmp_path, "p", {
            "observability_attributes": {
                "tool": {"chunk.size.tokens": {"type": "int", "min": 0, "max": 100}},
            }
        })
        report = validate(export, cfg, "p")
        warnings = [i for i in report.issues if "chunk.size.tokens" in i.attribute]
        assert len(warnings) >= 1

    def test_structural_warning_for_missing_span(self, tmp_path):
        # Export has no tool.call span
        export = self._write_export(tmp_path, [
            _make_span("agent.session", {"agent.status": "success"}),
        ])
        cfg = self._write_config(tmp_path, "p", {})
        report = validate(export, cfg, "p")
        structural = [i for i in report.issues if i.span_type == "structural"]
        # tool.call and llm.inference both missing
        assert any("tool.call" in i.message for i in structural)

    def test_int_real_float_declared_is_compatible(self, tmp_path):
        # int in real traces, float in profile — should NOT error
        export = self._write_export(tmp_path, [
            _make_span("tool.call", {"chunk.size.tokens": 256}),
        ])
        cfg = self._write_config(tmp_path, "p", {
            "observability_attributes": {
                "tool": {"chunk.size.tokens": {"type": "float", "min": 0.0, "max": 2048.0}},
            }
        })
        report = validate(export, cfg, "p")
        errors = [i for i in report.issues if i.severity == "error" and "chunk.size.tokens" in i.attribute]
        assert len(errors) == 0

    def test_unknown_profile_raises_value_error(self, tmp_path):
        export = self._write_export(tmp_path, [_make_span("agent.session", {})])
        cfg = self._write_config(tmp_path, "p", {})
        with pytest.raises(ValueError, match="not found"):
            validate(export, cfg, "nonexistent_profile")


# ---------------------------------------------------------------------------
# 4. Pre-built schema YAML files load through load_config()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_file", [
    "langchain_rag_agent.yaml",
    "openai_assistants_agent.yaml",
    "langgraph_multi_agent.yaml",
    "crewai_research_crew.yaml",
])
def test_prebuilt_schema_loads_cleanly(schema_file):
    path = _SCHEMAS_DIR / schema_file
    assert path.exists(), f"{schema_file} not found in config/schemas/"
    config = load_config(path)
    assert len(config.agent_profiles) >= 1
    for name, profile in config.agent_profiles.items():
        assert profile.llm_model
        assert profile.tools


@pytest.mark.parametrize("schema_file", [
    "langchain_rag_agent.yaml",
    "openai_assistants_agent.yaml",
    "langgraph_multi_agent.yaml",
    "crewai_research_crew.yaml",
])
def test_prebuilt_schema_has_observability_attributes(schema_file):
    path = _SCHEMAS_DIR / schema_file
    config = load_config(path)
    for name, profile in config.agent_profiles.items():
        obs = profile.observability_attributes
        has_attrs = (
            bool(obs.session) or bool(obs.tool) or bool(obs.inference)
        )
        assert has_attrs, f"Profile '{name}' in {schema_file} has no observability_attributes"


@pytest.mark.parametrize("schema_file", [
    "langchain_rag_agent.yaml",
    "openai_assistants_agent.yaml",
    "langgraph_multi_agent.yaml",
    "crewai_research_crew.yaml",
])
def test_prebuilt_schema_has_behavioral_signals(schema_file):
    path = _SCHEMAS_DIR / schema_file
    config = load_config(path)
    for name, profile in config.agent_profiles.items():
        assert profile.behavioral_signals is not None, (
            f"Profile '{name}' in {schema_file} has no behavioral_signals"
        )


# ---------------------------------------------------------------------------
# 5. ValidationConfig honoured in RootConfig
# ---------------------------------------------------------------------------

def test_validation_config_defaults():
    config = load_config(Path(__file__).parent.parent / "config" / "default.yaml")
    assert isinstance(config.validation, ValidationConfig)
    assert config.validation.enabled is False
    assert config.validation.real_export_path is None
    assert config.validation.profile_to_validate is None
    assert isinstance(config.validation.tolerance, ValidationToleranceConfig)
    assert config.validation.tolerance.value_range_margin == 0.20
    assert config.validation.tolerance.missing_attribute_threshold == 0.05


def test_validation_config_parsed_from_raw():
    from pydantic import ValidationError
    vc = ValidationConfig(
        enabled=True,
        real_export_path="/tmp/traces.json",
        profile_to_validate="rag_researcher",
        tolerance=ValidationToleranceConfig(
            value_range_margin=0.10,
            missing_attribute_threshold=0.02,
        ),
    )
    assert vc.enabled is True
    assert vc.tolerance.value_range_margin == 0.10
