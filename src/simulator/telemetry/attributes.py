"""
telemetry/attributes.py
GenAI semantic convention attribute name constants and OTel naming validator.
Centralised here so engine.py and future modules never use raw string literals.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.config import AgentProfile

# Present on all spans
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"

# Operation name values
OP_AGENT_SESSION = "agent_session"
OP_TOOL_CALL = "tool_call"
OP_CHAT = "chat"

# llm.inference spans only
GEN_AI_MODEL = "gen_ai.model"
GEN_AI_INPUT_TOKENS = "gen_ai.input.tokens"
GEN_AI_OUTPUT_TOKENS = "gen_ai.output.tokens"

# agent.session spans
AGENT_ID = "agent.id"
AGENT_PROFILE_TYPE = "agent.profile_type"
AGENT_GOAL = "agent.goal"
AGENT_STATUS = "agent.status"
TOOL_CALL_COUNT = "tool.call.count"

# tool.call spans
TOOL_NAME = "tool.name"
TOOL_CALL_INDEX = "tool.call.index"

SCENARIO_TYPE = "scenario.type"
ERROR_TYPE = "error.type"

# Fixed values
SYSTEM_SIMULATED = "simulated"


class AttributeSchemaValidator:
    """
    Validates that every observability attribute name in the profile schemas
    follows OTel naming conventions: lowercase namespaced tokens separated by dots.
    Raises ValueError at startup rather than silently emitting invalid spans.
    """

    _OTEL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*)*$")

    def validate_profile_schemas(self, profiles: dict[str, "AgentProfile"]) -> None:
        for profile_name, profile in profiles.items():
            obs = profile.observability_attributes
            # Iterate over (span_type_name, attrs_dict) pairs via Pydantic model iteration.
            for span_type, attrs in obs:
                if not attrs:
                    continue
                for attr_name in attrs:
                    if not self._OTEL_NAME_PATTERN.match(attr_name):
                        raise ValueError(
                            f"Profile '{profile_name}': invalid OTel attribute name "
                            f"'{attr_name}' on span type '{span_type}'. "
                            f"Must follow namespace.attribute convention (e.g. 'tool.cache_hit')."
                        )
