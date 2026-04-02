"""
tools/validate.py
Compares a real OTLP JSON export against a simulator profile config.

Usage:
  python -m tools.validate \\
      --real-export path/to/real_traces.json \\
      --simulator-config config/default.yaml \\
      --profile rag_researcher \\
      --output validation_report.md

What it checks:
  1. Attribute key coverage — which real attributes are missing from the simulator profile.
  2. Value type mismatches — real emits float but simulator declares int (or vice versa).
  3. Value range violations — simulator-declared min/max outside real observed range.
  4. Structural check — expected span names present in real export.
  5. Generates a gap report with suggested YAML additions.

Exit code: 0 if no critical gaps found, 1 if critical gaps exist.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._otel_parser import group_by_span_name, parse_otlp_json

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

_SPAN_BUCKETS = {
    "session": {"agent.session"},
    "tool": {"tool.call"},
    "inference": {"llm.inference"},
    "planning": {"agent.planning"},
}

_INTERNAL_KEYS = {
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

_TYPE_LABELS = {bool: "boolean", int: "int", float: "float", str: "enum"}


@dataclass
class AttributeStat:
    key: str
    python_type: str
    min_val: float | None = None
    max_val: float | None = None
    sample_values: list[Any] = field(default_factory=list)


@dataclass
class ValidationIssue:
    severity: str   # "error" | "warning" | "info"
    span_type: str
    attribute: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationReport:
    profile_name: str
    issues: list[ValidationIssue] = field(default_factory=list)

    # Summary counts
    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "info"]


# ---------------------------------------------------------------------------
# Real-trace analysis
# ---------------------------------------------------------------------------

def _infer_python_type(values: list[Any]) -> str:
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "int"
    if all(isinstance(v, float) for v in values):
        return "float"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "float"
    return "enum"


def _collect_real_stats(spans: list, skip: set) -> dict[str, AttributeStat]:
    from collections import defaultdict
    bucket: dict[str, list] = defaultdict(list)
    for span in spans:
        for key, value in span.attributes.items():
            if key not in skip:
                bucket[key].append(value)

    result: dict[str, AttributeStat] = {}
    for key, values in bucket.items():
        if not values:
            continue
        ptype = _infer_python_type(values)
        stat = AttributeStat(key=key, python_type=ptype, sample_values=values[:5])
        if ptype in ("int", "float"):
            numeric = [float(v) for v in values]
            stat.min_val = min(numeric)
            stat.max_val = max(numeric)
        result[key] = stat
    return result


# ---------------------------------------------------------------------------
# Config loader (raw YAML — no simulator import required)
# ---------------------------------------------------------------------------

def _load_profile_raw(config_path: str | Path, profile_name: str) -> dict:
    with open(config_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    profiles = data.get("agent_profiles", {})
    if profile_name not in profiles:
        available = list(profiles.keys())
        raise ValueError(
            f"Profile '{profile_name}' not found in {config_path}. "
            f"Available: {available}"
        )
    return profiles[profile_name]


def _get_declared_attrs(profile: dict, span_type: str) -> dict:
    """Return the dict of declared observability_attributes for a span type."""
    obs = profile.get("observability_attributes", {}) or {}
    return obs.get(span_type, {}) or {}


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def _type_compat(real_type: str, declared_type: str) -> bool:
    """int and float are cross-compatible; boolean and enum are strict."""
    if real_type == declared_type:
        return True
    # float config can cover int values from real traces
    if real_type == "int" and declared_type == "float":
        return True
    return False


def _check_span_type(
    real_stats: dict[str, AttributeStat],
    declared_attrs: dict,
    span_type: str,
    tolerance: float,
    report: ValidationReport,
) -> None:
    real_keys = set(real_stats.keys())
    declared_keys = set(declared_attrs.keys())

    # Missing from simulator
    missing = real_keys - declared_keys
    for key in sorted(missing):
        stat = real_stats[key]
        # Build a suggestion snippet
        if stat.python_type == "boolean":
            true_ratio = sum(1 for v in stat.sample_values if v) / max(1, len(stat.sample_values))
            suggestion = (
                f"  {key}:\n"
                f"    type: boolean\n"
                f"    probability: {round(true_ratio, 2)}"
            )
        elif stat.python_type == "enum":
            uniq = sorted({str(v) for v in stat.sample_values})
            suggestion = (
                f"  {key}:\n"
                f"    type: enum\n"
                f"    values: {uniq}"
            )
        elif stat.python_type in ("int", "float"):
            mn = round(stat.min_val or 0, 4)
            mx = round(stat.max_val or 0, 4)
            suggestion = (
                f"  {key}:\n"
                f"    type: {stat.python_type}\n"
                f"    min: {mn}\n"
                f"    max: {mx}"
            )
        else:
            suggestion = f"  {key}:\n    type: {stat.python_type}"

        report.issues.append(ValidationIssue(
            severity="warning",
            span_type=span_type,
            attribute=key,
            message=f"Attribute '{key}' found in real traces but not declared in profile.",
            suggestion=(
                f"Add to observability_attributes.{span_type}:\n{suggestion}"
            ),
        ))

    # Type mismatches
    for key in real_keys & declared_keys:
        real_type = real_stats[key].python_type
        declared = declared_attrs[key]
        decl_type = declared.get("type", "")
        if not _type_compat(real_type, decl_type):
            report.issues.append(ValidationIssue(
                severity="error",
                span_type=span_type,
                attribute=key,
                message=(
                    f"Type mismatch for '{key}': real traces show '{real_type}' "
                    f"but profile declares '{decl_type}'."
                ),
                suggestion=f"Change type to '{real_type}' in observability_attributes.{span_type}.{key}",
            ))

    # Range violations
    for key in real_keys & declared_keys:
        real_stat = real_stats[key]
        declared = declared_attrs[key]
        if real_stat.python_type not in ("int", "float"):
            continue
        if real_stat.min_val is None or real_stat.max_val is None:
            continue
        margin = tolerance
        decl_min = declared.get("min")
        decl_max = declared.get("max")
        real_range = real_stat.max_val - real_stat.min_val

        if decl_min is not None:
            lower_bound = real_stat.min_val - real_range * margin
            if float(decl_min) < lower_bound:
                report.issues.append(ValidationIssue(
                    severity="warning",
                    span_type=span_type,
                    attribute=key,
                    message=(
                        f"Declared min={decl_min} for '{key}' is below real observed "
                        f"minimum {real_stat.min_val:.4f} (with {margin*100:.0f}% margin)."
                    ),
                    suggestion=(
                        f"Consider setting min: {round(real_stat.min_val, 4)} "
                        f"in observability_attributes.{span_type}.{key}"
                    ),
                ))
        if decl_max is not None:
            upper_bound = real_stat.max_val + real_range * margin
            if float(decl_max) > upper_bound:
                report.issues.append(ValidationIssue(
                    severity="warning",
                    span_type=span_type,
                    attribute=key,
                    message=(
                        f"Declared max={decl_max} for '{key}' exceeds real observed "
                        f"maximum {real_stat.max_val:.4f} (with {margin*100:.0f}% margin)."
                    ),
                    suggestion=(
                        f"Consider setting max: {round(real_stat.max_val, 4)} "
                        f"in observability_attributes.{span_type}.{key}"
                    ),
                ))


def _check_structural(by_name: dict, report: ValidationReport) -> None:
    """Warn if expected top-level span names are absent from the export."""
    expected = {"agent.session", "tool.call", "llm.inference"}
    for span_name in expected:
        if span_name not in by_name:
            report.issues.append(ValidationIssue(
                severity="warning",
                span_type="structural",
                attribute="",
                message=f"Expected span '{span_name}' not found in real export.",
                suggestion=(
                    f"Ensure your agent emits a '{span_name}' span, or adjust "
                    "_SPAN_BUCKETS in validate.py if your span names differ."
                ),
            ))


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _format_report(report: ValidationReport) -> str:
    lines: list[str] = [
        f"# Digital Twin Validation Report",
        f"",
        f"**Profile:** `{report.profile_name}`",
        f"",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| Errors   | {len(report.errors)} |",
        f"| Warnings | {len(report.warnings)} |",
        f"| Info     | {len(report.infos)} |",
        f"",
    ]

    if not report.issues:
        lines.append("All checks passed. The simulator profile is a faithful twin.")
        return "\n".join(lines)

    for severity in ("error", "warning", "info"):
        issues = [i for i in report.issues if i.severity == severity]
        if not issues:
            continue
        label = severity.upper() + "S"
        lines.append(f"## {label}")
        lines.append("")
        for issue in issues:
            tag = f"[{issue.span_type}]" if issue.span_type else ""
            lines.append(f"### {tag} {issue.attribute}")
            lines.append(f"{issue.message}")
            if issue.suggestion:
                lines.append(f"")
                lines.append(f"**Suggested fix:**")
                lines.append(f"```yaml")
                lines.append(issue.suggestion)
                lines.append(f"```")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(
    real_export: str | Path,
    simulator_config: str | Path,
    profile_name: str,
    tolerance: float = 0.20,
) -> ValidationReport:
    spans = parse_otlp_json(real_export)
    by_name = group_by_span_name(spans)
    profile = _load_profile_raw(simulator_config, profile_name)

    report = ValidationReport(profile_name=profile_name)
    _check_structural(by_name, report)

    for span_type, span_names in _SPAN_BUCKETS.items():
        real_spans = [s for name in span_names for s in by_name.get(name, [])]
        if not real_spans:
            continue
        real_stats = _collect_real_stats(real_spans, _INTERNAL_KEYS)
        declared_attrs = _get_declared_attrs(profile, span_type)
        _check_span_type(real_stats, declared_attrs, span_type, tolerance, report)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate simulator profile against real OTLP JSON export."
    )
    parser.add_argument("--real-export", required=True, help="Path to OTLP JSON export")
    parser.add_argument("--simulator-config", required=True, help="Path to simulator config YAML")
    parser.add_argument("--profile", required=True, help="Profile name to validate")
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path (default: stdout)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.20,
        help="Fractional tolerance for range checks (default: 0.20 = 20%%)",
    )
    args = parser.parse_args()

    report = validate(
        real_export=args.real_export,
        simulator_config=args.simulator_config,
        profile_name=args.profile,
        tolerance=args.tolerance,
    )
    text = _format_report(report)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(text)

    if report.errors:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
