from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, model_validator


class GaussianDistribution(BaseModel):
    mean: float
    std: float = Field(gt=0)


class UniformIntDistribution(BaseModel):
    min: int = Field(ge=0)
    max: int

    @model_validator(mode="after")
    def check_range(self) -> "UniformIntDistribution":
        if self.max < self.min:
            raise ValueError(f"max ({self.max}) must be >= min ({self.min})")
        return self


class AttributeType(str, Enum):
    FLOAT   = "float"
    INT     = "int"
    ENUM    = "enum"
    BOOLEAN = "boolean"


class AttributeConfig(BaseModel):
    type: AttributeType
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    values: Optional[List[Union[str, int]]] = None
    probability: Optional[float] = None  # for boolean type


class SpanAttributeSchema(BaseModel):
    session:   Dict[str, AttributeConfig] = Field(default_factory=dict)
    tool:      Dict[str, AttributeConfig] = Field(default_factory=dict)
    inference: Dict[str, AttributeConfig] = Field(default_factory=dict)


class AgentProfile(BaseModel):
    tools: list[str]
    llm_model: str = "gpt-4o"
    llm_input_tokens: GaussianDistribution
    llm_output_tokens: GaussianDistribution
    planning_latency_ms: GaussianDistribution
    tool_call_count: UniformIntDistribution
    failure_rate: float = Field(ge=0.0, le=1.0, default=0.05)
    mix_weight: float = Field(gt=0.0, default=1.0)
    observability_attributes: SpanAttributeSchema = Field(default_factory=SpanAttributeSchema)


class SimulatorConfig(BaseModel):
    concurrency: int = Field(ge=1, default=1)
    run_duration_seconds: int = Field(ge=1, default=60)
    clock_multiplier: float = Field(gt=0.0, default=1.0)
    random_seed: int | None = None


class TelemetryConfig(BaseModel):
    exporter_endpoint: str = "http://localhost:4317"
    batch_size: int = Field(ge=1, default=512)
    export_interval_ms: int = Field(ge=100, default=5000)


class ScenarioConfig(BaseModel):
    # Maps scenario_name -> injection probability (0.0–1.0)
    enabled: dict[str, float] = Field(default_factory=dict)


class RootConfig(BaseModel):
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    agent_profiles: dict[str, AgentProfile]
    scenarios: ScenarioConfig = Field(default_factory=ScenarioConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)


def load_config(path: str | Path) -> RootConfig:
    """Load and validate a YAML config file, returning a RootConfig instance."""
    from simulator.telemetry.attributes import AttributeSchemaValidator

    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = RootConfig.model_validate(raw)
    AttributeSchemaValidator().validate_profile_schemas(config.agent_profiles)
    return config
