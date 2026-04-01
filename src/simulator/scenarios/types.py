from __future__ import annotations

from enum import Enum


class ScenarioType(str, Enum):
    TOOL_TIMEOUT = "tool_timeout"
    INFINITE_RETRY_LOOP = "infinite_retry_loop"
    GOAL_DRIFT = "goal_drift"
    CONTEXT_OVERFLOW = "context_overflow"
    SILENT_FAILURE = "silent_failure"
