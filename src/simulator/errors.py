"""
simulator/errors.py
Human-readable error formatting for config validation failures.
Converts raw Pydantic ValidationError stack traces into actionable messages.
"""
from __future__ import annotations

from pydantic import ValidationError


class ConfigError(Exception):
    """Raised when a config file fails validation or is otherwise unusable."""
    pass


def format_validation_error(exc: ValidationError, config_path: str) -> str:
    """
    Convert a Pydantic ValidationError into a user-friendly, multi-line message.

    Example output::

        ❌ Config error in config/default.yaml:

           agent_profiles → rag_researcher → failure_rate: Input should be less than or equal to 1
           Value given: 1.5

        💡 Check config/default.yaml for reference.
    """
    lines: list[str] = [f"\n❌ Config error in {config_path}:\n"]
    for error in exc.errors():
        location = " → ".join(str(loc) for loc in error["loc"])
        lines.append(f"   {location}: {error['msg']}")
        input_val = error.get("input", "unknown")
        lines.append(f"   Value given: {input_val}\n")
    lines.append(f"💡 Check config/default.yaml for reference.\n")
    return "\n".join(lines)
