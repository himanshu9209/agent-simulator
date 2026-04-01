# GenAI semantic convention attribute name constants.
# Centralised here so engine.py and future modules never use raw string literals.

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
