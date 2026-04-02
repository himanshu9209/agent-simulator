"""
tools/_otel_parser.py
Parses OTLP JSON export files into lightweight SpanRecord objects.
Shared by schema_generator.py and validate.py.

OTLP JSON structure:
  resourceSpans -> scopeSpans -> spans -> attributes
  Attribute values are tagged dicts: {"stringValue": ...}, {"intValue": "123"},
  {"doubleValue": 1.5}, {"boolValue": true}.
  Note: intValue is JSON-encoded as a STRING (int64 precision) — must cast with int().
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SpanRecord:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    attributes: dict[str, Any]
    duration_ns: int = 0


def _decode_value(value_dict: dict) -> Any:
    """Convert a single OTLP attribute value dict to a Python scalar."""
    if "stringValue" in value_dict:
        return value_dict["stringValue"]
    if "intValue" in value_dict:
        # int64 values are encoded as JSON strings in OTLP JSON
        return int(value_dict["intValue"])
    if "doubleValue" in value_dict:
        return float(value_dict["doubleValue"])
    if "boolValue" in value_dict:
        return bool(value_dict["boolValue"])
    if "arrayValue" in value_dict:
        return [
            _decode_value(v)
            for v in value_dict["arrayValue"].get("values", [])
        ]
    # Fallback — return raw dict rather than crashing
    return value_dict


def _decode_attributes(raw_attrs: list[dict]) -> dict[str, Any]:
    """Convert a list of OTLP {key, value} dicts into a plain Python dict."""
    result: dict[str, Any] = {}
    for entry in raw_attrs:
        key = entry.get("key", "")
        value_dict = entry.get("value", {})
        result[key] = _decode_value(value_dict)
    return result


def parse_otlp_json_from_dict(data: dict) -> list[SpanRecord]:
    """Parse a pre-loaded OTLP JSON dict into SpanRecord objects."""
    records: list[SpanRecord] = []

    for resource_span in data.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                parent_id = span.get("parentSpanId") or None
                # duration = endTimeUnixNano - startTimeUnixNano (both encoded as strings)
                try:
                    start_ns = int(span.get("startTimeUnixNano", "0"))
                    end_ns = int(span.get("endTimeUnixNano", "0"))
                    duration_ns = max(0, end_ns - start_ns)
                except (ValueError, TypeError):
                    duration_ns = 0

                records.append(SpanRecord(
                    name=span.get("name", ""),
                    trace_id=span.get("traceId", ""),
                    span_id=span.get("spanId", ""),
                    parent_span_id=parent_id,
                    attributes=_decode_attributes(span.get("attributes", [])),
                    duration_ns=duration_ns,
                ))

    return records


def parse_otlp_json(path: str | Path) -> list[SpanRecord]:
    """Load an OTLP JSON export file and return SpanRecord objects."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return parse_otlp_json_from_dict(data)


def group_by_span_name(records: list[SpanRecord]) -> dict[str, list[SpanRecord]]:
    """Group SpanRecords by their span name."""
    groups: dict[str, list[SpanRecord]] = {}
    for rec in records:
        groups.setdefault(rec.name, []).append(rec)
    return groups
