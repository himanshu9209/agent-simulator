"""
simulator/api/models.py
Pydantic request/response models for the Phase 8a REST API.

All shapes are defined here; routers import from here to stay thin.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from simulator.config import AgentProfile, ModelPricing


# ---------------------------------------------------------------------------
# Profile models
# ---------------------------------------------------------------------------

class ProfileSummary(BaseModel):
    name: str
    llm_model: str
    tool_count: int
    attribute_count: int
    behavioral_signal_count: int
    mix_weight: float
    failure_rate: float


class ProfileListResponse(BaseModel):
    profiles: List[ProfileSummary]
    total: int


class ProfileDetailResponse(BaseModel):
    name: str
    profile: AgentProfile


class ProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    profile: AgentProfile


class ProfileUpdateRequest(BaseModel):
    profile: AgentProfile


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------

class ConfigResponse(BaseModel):
    yaml_str: str
    path: str


class ConfigWriteRequest(BaseModel):
    yaml_str: str


class ConfigValidateRequest(BaseModel):
    yaml_str: str


class ConfigValidateResponse(BaseModel):
    valid: bool
    errors: List[str]


# ---------------------------------------------------------------------------
# Run models
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class RunStartRequest(BaseModel):
    duration: Optional[int] = Field(None, ge=1, description="Override run_duration_seconds")
    concurrency: Optional[int] = Field(None, ge=1, description="Override concurrency")
    profile: Optional[str] = Field(None, description="Run a single named profile only")


class RunStatusResponse(BaseModel):
    status: RunStatus
    started_at: Optional[str] = None
    elapsed_seconds: float = 0.0
    active_agents: int = 0
    sessions_completed: int = 0
    sessions_error: int = 0
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_calls: int = 0
    error: Optional[str] = None


class RunStartResponse(BaseModel):
    message: str
    status: RunStatus


class RunStopResponse(BaseModel):
    message: str
    status: RunStatus


# ---------------------------------------------------------------------------
# Pricing models
# ---------------------------------------------------------------------------

class PricingTableResponse(BaseModel):
    pricing: Dict[str, ModelPricing]


class PricingUpdateRequest(BaseModel):
    pricing: Dict[str, ModelPricing]
