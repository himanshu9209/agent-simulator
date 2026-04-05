// ─── Distribution shapes ────────────────────────────────────────────────────

export interface GaussianDistribution {
  mean: number;
  std: number;
}

export interface UniformIntDistribution {
  min: number;
  max: number;
}

// ─── Observability attributes ───────────────────────────────────────────────

export type AttributeType = "float" | "int" | "enum" | "boolean";

export interface AttributeConfig {
  type: AttributeType;
  min?: number;
  max?: number;
  mean?: number;
  std?: number;
  values?: (string | number)[];
  probability?: number;
}

export interface SpanAttributeSchema {
  session: Record<string, AttributeConfig>;
  tool: Record<string, AttributeConfig>;
  inference: Record<string, AttributeConfig>;
}

// ─── Behavioral signals ─────────────────────────────────────────────────────

export interface BehavioralSignalConfig {
  type: AttributeType;
  span: string;
  min?: number;
  max?: number;
  mean?: number;
  std?: number;
  values?: (string | number)[];
  probability?: number;
  target_model?: string;
  emitted_on_retry?: boolean;
  description?: string;
}

export interface ToolSequenceConfig {
  enforced: boolean;
  order: string[];
  deviation_probability: number;
}

export interface BehavioralSignalsSchema {
  tool_selection_quality?: BehavioralSignalConfig;
  tool_sequence?: ToolSequenceConfig;
  goal_drift?: BehavioralSignalConfig;
  model_switch?: BehavioralSignalConfig;
  planning_quality?: BehavioralSignalConfig;
  retry_reason?: BehavioralSignalConfig;
  replanning_triggered?: BehavioralSignalConfig;
  sandbox_escalation?: BehavioralSignalConfig;
  extra: Record<string, BehavioralSignalConfig>;
}

// ─── Agent profile ───────────────────────────────────────────────────────────

export interface AgentProfile {
  tools: string[];
  llm_model: string;
  llm_input_tokens: GaussianDistribution;
  llm_output_tokens: GaussianDistribution;
  planning_latency_ms: GaussianDistribution;
  tool_call_count: UniformIntDistribution;
  failure_rate: number;
  mix_weight: number;
  observability_attributes: SpanAttributeSchema;
  behavioral_signals?: BehavioralSignalsSchema;
}

// ─── Profile API shapes ──────────────────────────────────────────────────────

export interface ProfileSummary {
  name: string;
  llm_model: string;
  tool_count: number;
  attribute_count: number;
  behavioral_signal_count: number;
  mix_weight: number;
  failure_rate: number;
}

export interface ProfileListResponse {
  profiles: ProfileSummary[];
  total: number;
}

export interface ProfileDetailResponse {
  name: string;
  profile: AgentProfile;
}

// ─── Config API shapes ───────────────────────────────────────────────────────

export interface ConfigResponse {
  yaml_str: string;
  path: string;
}

export interface ConfigValidateResponse {
  valid: boolean;
  errors: string[];
}

// ─── Run API shapes ──────────────────────────────────────────────────────────

export type RunStatus = "idle" | "running" | "stopping" | "error";

export interface RunStatusResponse {
  status: RunStatus;
  started_at?: string;
  elapsed_seconds: number;
  active_agents: number;
  sessions_completed: number;
  sessions_error: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  tool_calls: number;
  error?: string;
}

export interface RunStartRequest {
  duration?: number;
  concurrency?: number;
  profile?: string;
}

// ─── Pricing API shapes ──────────────────────────────────────────────────────

export interface ModelPricing {
  input_per_million: number;
  output_per_million: number;
  cached_input_per_million?: number;
  cache_write_per_million?: number;
  cache_read_per_million?: number;
}

export interface PricingTableResponse {
  pricing: Record<string, ModelPricing>;
}
