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
    behavioral_signals: Optional[BehavioralSignalsSchema] = None


class SimulatorConfig(BaseModel):
    concurrency: int = Field(ge=1, default=1)
    run_duration_seconds: int = Field(ge=1, default=60)
    clock_multiplier: float = Field(gt=0.0, default=1.0)
    random_seed: int | None = None


class TlsConfig(BaseModel):
    """TLS / mTLS settings for the OTLP exporter."""
    insecure: bool = True            # set False for TLS-enabled endpoints
    cert_file: Optional[str] = None  # path to client cert for mTLS


class TelemetryConfig(BaseModel):
    exporter_endpoint: str = "http://localhost:4317"
    batch_size: int = Field(ge=1, default=512)
    export_interval_ms: int = Field(ge=100, default=5000)
    # Auth headers — values may use ${ENV_VAR} syntax resolved at startup
    headers: Dict[str, str] = Field(default_factory=dict)
    tls: TlsConfig = Field(default_factory=TlsConfig)


class ScenarioConfig(BaseModel):
    # Maps scenario_name -> injection probability (0.0–1.0)
    enabled: dict[str, float] = Field(default_factory=dict)


class BehavioralSignalConfig(BaseModel):
    """
    Declares one behavioral signal emitted on a specific span type.
    Reuses AttributeType so AttributeSampler works on it directly.
    The extra fields (span, target_model, emitted_on_retry, description)
    are behavioral metadata; the sampler only reads type/min/max/mean/std/values/probability.
    """
    type: AttributeType
    span: str                               # "session" | "tool" | "inference" | "planning"
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    values: Optional[List[Union[str, int]]] = None
    probability: Optional[float] = None
    target_model: Optional[str] = None     # for model_switch: which model to escalate to
    emitted_on_retry: bool = False          # for retry_reason: only emit on retried calls
    description: Optional[str] = None


class ToolSequenceConfig(BaseModel):
    enforced: bool = False
    order: List[str] = Field(default_factory=list)
    deviation_probability: float = 0.0


class BehavioralSignalsSchema(BaseModel):
    tool_selection_quality: Optional[BehavioralSignalConfig] = None
    tool_sequence:          Optional[ToolSequenceConfig] = None
    goal_drift:             Optional[BehavioralSignalConfig] = None
    model_switch:           Optional[BehavioralSignalConfig] = None
    planning_quality:       Optional[BehavioralSignalConfig] = None
    retry_reason:           Optional[BehavioralSignalConfig] = None
    replanning_triggered:   Optional[BehavioralSignalConfig] = None  # mid-session replan
    sandbox_escalation:     Optional[BehavioralSignalConfig] = None  # sandbox switch
    extra:                  Dict[str, BehavioralSignalConfig] = Field(default_factory=dict)


class ModelPricing(BaseModel):
    input_per_million:          float
    output_per_million:         float
    cached_input_per_million:   Optional[float] = None  # OpenAI prompt caching
    cache_write_per_million:    Optional[float] = None  # Anthropic cache write
    cache_read_per_million:     Optional[float] = None  # Anthropic cache read


class ValidationToleranceConfig(BaseModel):
    value_range_margin: float = 0.20
    missing_attribute_threshold: float = 0.05


class ValidationConfig(BaseModel):
    enabled: bool = False
    real_export_path: Optional[str] = None
    profile_to_validate: Optional[str] = None
    tolerance: ValidationToleranceConfig = Field(default_factory=ValidationToleranceConfig)


class RootConfig(BaseModel):
    simulator: SimulatorConfig = Field(default_factory=SimulatorConfig)
    agent_profiles: dict[str, AgentProfile]
    scenarios: ScenarioConfig = Field(default_factory=ScenarioConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    pricing: Dict[str, ModelPricing] = Field(default_factory=dict)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)


def load_config(path: str | Path) -> RootConfig:
    """Load and validate a YAML config file, returning a RootConfig instance."""
    from simulator.telemetry.attributes import AttributeSchemaValidator

    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = RootConfig.model_validate(raw)
    AttributeSchemaValidator().validate_profile_schemas(config.agent_profiles)
    return config
