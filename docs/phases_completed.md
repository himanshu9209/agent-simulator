# Completed Phases — Design Detail

Full design documentation for Phases 1–7. For the V1 skeleton (Phase 1) source of truth, see [CLAUDE_hist.md](../CLAUDE_hist.md).

---

## Phase 1 — V1 Skeleton

### What was built
- 5 hardcoded agent profiles (rag_researcher, code_executor, web_scraper, data_analyst, task_planner)
- OTel span emission via OTLP/gRPC using the OpenTelemetry Python SDK
- asyncio worker pool for concurrent agents (`core.py`)
- Wall-clock time multiplier for accelerated simulation (`clock.py`)
- Docker Compose stack: OTel Collector + Jaeger

### Files (carried forward untouched into V2)
- `src/simulator/core.py` — asyncio worker pool
- `src/simulator/clock.py` — time multiplier
- `src/simulator/telemetry/emitter.py` — OTel SDK wrapper
- `docker/` — OTel Collector + Jaeger

### End state
Working simulator emitting hardcoded spans to Jaeger. Foundation for V2.

---

## Phase 2 — Dynamic Attribute Schema

### Goal
Replace hardcoded span attributes with a YAML-driven schema system. Any attribute a real
agent emits can be declared in the profile config and will appear in simulator spans —
no Python changes required.

### New config structure

```yaml
agent_profiles:
  rag_researcher:
    tools: [vector_search, reranker, summariser]
    llm_model: "gpt-4o"
    llm_input_tokens:    {mean: 1200, std: 300}
    llm_output_tokens:   {mean: 250,  std: 80}
    planning_latency_ms: {mean: 200,  std: 50}
    tool_latency_ms:     {mean: 400,  std: 100}
    tool_call_count:     {min: 1, max: 5}
    failure_rate: 0.05

    observability_attributes:
      session:
        retrieval.score:      {type: float,   min: 0.6,  max: 1.0}
        chunks.returned:      {type: int,     min: 1,    max: 20}
        reranker.model:       {type: enum,    values: [cohere-v3, bge-reranker]}
        index.name:           {type: enum,    values: [prod-index, staging-index]}
      tool:
        tool.input_size_kb:   {type: float,   min: 0.5,  max: 50.0}
        tool.cache_hit:       {type: boolean, probability: 0.3}
      inference:
        inference.temperature: {type: float,  min: 0.0,  max: 1.0}
        inference.top_p:       {type: float,  min: 0.8,  max: 1.0}

  code_executor:
    tools: [code_interpreter, file_reader, shell_exec]
    llm_model: "gpt-4o"
    llm_input_tokens:    {mean: 800,  std: 200}
    llm_output_tokens:   {mean: 600,  std: 150}
    planning_latency_ms: {mean: 150,  std: 40}
    tool_latency_ms:     {mean: 800,  std: 300}
    tool_call_count:     {min: 1, max: 4}
    failure_rate: 0.08
    observability_attributes:
      session:
        execution.language:   {type: enum,    values: [python, javascript, bash]}
        sandbox.type:         {type: enum,    values: [docker, e2b, local]}
      tool:
        execution.exit_code:  {type: int,     values: [0, 1, 2]}
        execution.runtime_ms: {type: float,   min: 10, max: 5000}
        execution.memory_mb:  {type: float,   min: 10, max: 512}

  web_scraper:
    tools: [web_fetch, html_parser, link_extractor]
    llm_model: "claude-3-sonnet"
    llm_input_tokens:    {mean: 600,  std: 150}
    llm_output_tokens:   {mean: 180,  std: 60}
    planning_latency_ms: {mean: 100,  std: 30}
    tool_latency_ms:     {mean: 600,  std: 200}
    tool_call_count:     {min: 2, max: 8}
    failure_rate: 0.12
    observability_attributes:
      session:
        pages.scraped:        {type: int,     min: 1,   max: 20}
        content.size_kb:      {type: float,   min: 1.0, max: 500.0}
      tool:
        http.status_code:     {type: enum,    values: [200, 301, 404, 429, 503]}
        http.response_ms:     {type: float,   min: 50,  max: 3000}
        robots.txt.respected: {type: boolean, probability: 0.95}

  data_analyst:
    tools: [sql_query, dataframe_op, chart_renderer]
    llm_model: "gpt-4o"
    llm_input_tokens:    {mean: 1500, std: 400}
    llm_output_tokens:   {mean: 300,  std: 100}
    planning_latency_ms: {mean: 250,  std: 60}
    tool_latency_ms:     {mean: 500,  std: 150}
    tool_call_count:     {min: 1, max: 6}
    failure_rate: 0.04
    observability_attributes:
      session:
        rows.processed:       {type: int,     min: 100,  max: 1000000}
        query.complexity:     {type: enum,    values: [simple, moderate, complex]}
      tool:
        query.execution_ms:   {type: float,   min: 10,   max: 10000}
        query.rows_returned:  {type: int,     min: 0,    max: 100000}
        db.type:              {type: enum,    values: [postgres, bigquery, snowflake]}

  task_planner:
    tools: [goal_decomposer, task_scheduler, dependency_resolver]
    llm_model: "claude-3-sonnet"
    llm_input_tokens:    {mean: 2000, std: 500}
    llm_output_tokens:   {mean: 400,  std: 120}
    planning_latency_ms: {mean: 300,  std: 80}
    tool_latency_ms:     {mean: 300,  std: 80}
    tool_call_count:     {min: 2, max: 6}
    failure_rate: 0.03
    observability_attributes:
      session:
        tasks.created:        {type: int,     min: 2,    max: 20}
        plan.depth:           {type: int,     min: 1,    max: 5}
        dependencies.count:   {type: int,     min: 0,    max: 15}
      tool:
        subtasks.count:       {type: int,     min: 1,    max: 8}
```

### New and modified files

#### NEW: `src/simulator/behavior/sampler.py`
Central value generator for all attribute types.

```python
class AttributeSampler:
    def sample(self, attr_cfg: AttributeConfig, rng: np.random.Generator) -> Any:
        if attr_cfg.type == "float":
            return self._sample_float(attr_cfg, rng)
        elif attr_cfg.type == "int":
            return self._sample_int(attr_cfg, rng)
        elif attr_cfg.type == "enum":
            return self._sample_enum(attr_cfg, rng)
        elif attr_cfg.type == "boolean":
            return self._sample_boolean(attr_cfg, rng)

    def _sample_float(self, cfg, rng):
        if cfg.mean is not None:
            value = rng.normal(cfg.mean, cfg.std or cfg.mean * 0.1)
        else:
            value = rng.uniform(cfg.min, cfg.max)
        return float(np.clip(value, cfg.min or 0, cfg.max or float('inf')))

    def _sample_int(self, cfg, rng):
        if cfg.values:
            return int(rng.choice(cfg.values))
        return int(rng.integers(cfg.min, cfg.max + 1))

    def _sample_enum(self, cfg, rng):
        return str(rng.choice(cfg.values))

    def _sample_boolean(self, cfg, rng):
        return bool(rng.random() < (cfg.probability or 0.5))
```

#### MODIFIED: `src/simulator/config.py`
Added Pydantic models: `AttributeType`, `AttributeConfig`, `SpanAttributeSchema`.
`AgentProfileConfig` gained `observability_attributes: Optional[SpanAttributeSchema]`.

#### MODIFIED: `src/simulator/behavior/engine.py`
Dynamic attribute emission pass added after existing hardcoded attributes in `_tool_phase`, `_inference_phase`, and `run_session`.

#### MODIFIED: `src/simulator/telemetry/attributes.py`
`AttributeSchemaValidator` added — checks OTel naming convention (`namespace.attribute`) at startup.

### Tests added
- `tests/test_sampler.py` — each attribute type samples within declared bounds
- `tests/test_dynamic_attributes.py` — custom attributes appear on correct span types

### End state
Any attribute a real agent emits can be declared in YAML. Zero Python changes required to add a new attribute.

---

## Phase 3 — Cost Emission

### Goal
Every session emits accurate cost figures based on token counts × model pricing.

### New config structure

```yaml
pricing:
  gpt-4o:
    input_per_million:        2.50
    output_per_million:       10.00
    cached_input_per_million: 1.25
  gpt-4o-mini:
    input_per_million:        0.15
    output_per_million:       0.60
    cached_input_per_million: 0.075
  claude-3-sonnet:
    input_per_million:        3.00
    output_per_million:       15.00
    cache_write_per_million:  3.75
    cache_read_per_million:   0.30
  claude-3-haiku:
    input_per_million:        0.25
    output_per_million:       1.25
    cache_write_per_million:  0.30
    cache_read_per_million:   0.03
  gemini-1.5-pro:
    input_per_million:        1.25
    output_per_million:       5.00
  gemini-1.5-flash:
    input_per_million:        0.075
    output_per_million:       0.30
```

### New span attributes emitted

On `llm.inference`: `gen_ai.usage.cost_usd`, `gen_ai.usage.input_cost_usd`, `gen_ai.usage.output_cost_usd`

On `agent.session`: `session.total_cost_usd`, `session.avg_cost_per_tool_call_usd`

### New and modified files

#### NEW: `src/simulator/behavior/cost.py`

```python
@dataclass
class InferenceCost:
    input_cost_usd:  float
    output_cost_usd: float
    total_cost_usd:  float

class CostCalculator:
    def __init__(self, pricing_cfg: Dict[str, ModelPricing]) -> None:
        self._pricing = pricing_cfg

    def calculate(self, model, input_tokens, output_tokens, cached_tokens=0) -> InferenceCost:
        pricing = self._pricing.get(model)
        if not pricing:
            return InferenceCost(0.0, 0.0, 0.0)  # unknown model — zero cost, no crash
        input_cost  = (input_tokens - cached_tokens) * pricing.input_per_million / 1_000_000
        cached_cost = cached_tokens * (pricing.cached_input_per_million or pricing.input_per_million) / 1_000_000
        output_cost = output_tokens * pricing.output_per_million / 1_000_000
        total       = input_cost + cached_cost + output_cost
        return InferenceCost(
            input_cost_usd=round(input_cost + cached_cost, 8),
            output_cost_usd=round(output_cost, 8),
            total_cost_usd=round(total, 8),
        )
```

#### NEW: `src/simulator/telemetry/metrics.py` (initial)
OTel cost counters: `agent.cost.total_usd` (counter), `agent.cost.per_session_usd` (histogram).

#### MODIFIED: `src/simulator/config.py`
Added `ModelPricing` model. `Config` gained `pricing: Dict[str, ModelPricing]`.

#### MODIFIED: `src/simulator/behavior/engine.py`
`CostCalculator` wired into `_inference_phase`. Session total accumulated and emitted on `agent.session` span.

### Tests added
- `tests/test_cost.py` — cost calculations correct per model, unknown model returns zero

### End state
Every session emits granular cost data. Pricing fully configurable in YAML.

---

## Phase 4 — Behavioral Signals

### Goal
Emit behavioral signals — goal drift, tool selection quality, model switching, planning quality — as first-class telemetry. Scenario engine becomes fully dynamic.

### New config structure

```yaml
agent_profiles:
  rag_researcher:
    behavioral_signals:
      tool_selection_quality:
        type: float
        mean: 0.85
        std: 0.1
        min: 0.0
        max: 1.0
        span: tool
      tool_sequence:
        enforced: true
        order: [vector_search, reranker, summariser]
        deviation_probability: 0.05
      goal_drift:
        type: boolean
        probability: 0.05
        span: session
      model_switch:
        type: boolean
        probability: 0.03
        target_model: "gpt-4o"
        span: inference
      planning_quality:
        type: float
        mean: 0.80
        std: 0.15
        min: 0.0
        max: 1.0
        span: planning
      retry_reason:
        type: enum
        values: [rate_limit, timeout, bad_output, network_error]
        emitted_on_retry: true
        span: tool

  code_executor:
    behavioral_signals:
      tool_selection_quality: {type: float, mean: 0.75, std: 0.2, span: tool}
      goal_drift: {type: boolean, probability: 0.08, span: session}
      sandbox_escalation:
        type: boolean
        probability: 0.05
        description: "Agent switches from local to docker sandbox mid-session"
        span: tool

  task_planner:
    behavioral_signals:
      planning_quality: {type: float, mean: 0.90, std: 0.08, span: planning}
      goal_drift: {type: boolean, probability: 0.03, span: session}
      replanning_triggered:
        type: boolean
        probability: 0.12
        description: "Agent discards original plan and replans mid-session"
        span: session
```

### New span attributes emitted

On `agent.planning`: `planning.quality_score`, `planning.replanning_triggered`

On `tool.call`: `tool.selection_quality`, `tool.sequence_position`, `tool.sequence_deviation`, `tool.retry_reason`

On `llm.inference`: `inference.model_switched`, `inference.original_model`

On `agent.session`: `session.goal_drift_detected`, `session.original_goal`, `session.final_goal`

### New and modified files

#### MODIFIED: `src/simulator/config.py`
Added: `BehavioralSignalConfig`, `ToolSequenceConfig`, `BehavioralSignalsSchema`.
`AgentProfileConfig` gained `behavioral_signals: Optional[BehavioralSignalsSchema]`.

#### MODIFIED: `src/simulator/behavior/engine.py`
Behavioral signals wired into `_planning_phase`, `_tool_phase`, and `run_session`.
Tool sequence enforcement and goal drift logic added.

#### MODIFIED: `src/simulator/scenarios/engine.py`
Replaced hardcoded scenario list with dynamic evaluation from `profile.behavioral_signals`.

```python
class ScenarioEngine:
    def evaluate(self, profile, rng) -> ScenarioResult:
        if not profile.behavioral_signals:
            return ScenarioResult(scenario=ScenarioType.NONE)
        bs = profile.behavioral_signals
        if bs.goal_drift and rng.random() < bs.goal_drift.probability:
            return ScenarioResult(scenario=ScenarioType.GOAL_DRIFT, ...)
        if bs.model_switch and rng.random() < bs.model_switch.probability:
            return ScenarioResult(scenario=ScenarioType.MODEL_SWITCH, ...)
        return ScenarioResult(scenario=ScenarioType.NONE)
```

### Tests added
- `tests/test_behavioral_signals.py`

### End state
Teams can declare behavioral signal probabilities in YAML and build alerting rules against them. Scenario engine is fully dynamic.

---

## Phase 5 — Digital Twin Validation

### Goal
Prove simulator output faithfully mirrors real agent telemetry. Provide tooling to compare real OTel exports against simulator output.

### What digital twin validation means
1. All span attribute *keys* present in real output also appear in simulator output
2. Attribute *value types* match (int vs float vs string)
3. Attribute *value ranges* are realistic
4. Span *structure* matches (parent/child, names)
5. *Behavioral patterns* match (tool call frequency, failure rates, cost distribution)

### New tooling

#### `tools/validate.py`
```bash
python -m tools.validate \
  --real-export path/to/real_traces.json \
  --simulator-config config/default.yaml \
  --profile rag_researcher \
  --output validation_report.md
```
Checks: attribute key coverage, value type mismatches, value range violations, structural differences. Generates gap report with suggested YAML additions.

#### `tools/schema_generator.py`
```bash
python -m tools.schema_generator \
  --input path/to/real_traces.json \
  --profile-name my_real_agent \
  --output config/profiles/my_real_agent.yaml
```
Extracts attribute names, infers types, calculates min/max/mean/std, generates enum lists. Produces ready-to-use YAML.

#### `config/schemas/` — pre-built schemas
```
config/schemas/
├── langchain_rag_agent.yaml
├── openai_assistants_agent.yaml
├── langgraph_multi_agent.yaml
├── crewai_research_crew.yaml
└── autogen_coding_agent.yaml
```

### New config structure
```yaml
validation:
  enabled: false
  real_export_path: null
  profile_to_validate: null
  tolerance:
    value_range_margin: 0.20
    missing_attribute_threshold: 0.05
```

### Tests added
- `tests/test_digital_twin.py`

### End state
User can export real OTel traces → `schema_generator.py` → YAML profile → run simulator → `validate.py` → confirmed match. Build observability platform with confidence.

---

## Phase 6 — Production Hardening

### Goal
200 concurrent agents, full Prometheus + Grafana stack, pre-built dashboards.

### Concurrency target
- 200 concurrent agents, 10-minute simulated runs at 5x clock
- 2,000–5,000 spans/second throughput
- Cost metrics updated every 5 seconds

### Extended Docker Compose stack
Added: Prometheus (`:9090`), Grafana (`:3000`) with anonymous access enabled.
OTel Collector extended to export metrics to Prometheus.

### Pre-built Grafana dashboards (5 total)

| Dashboard | Key panels |
|-----------|-----------|
| Agent Overview | Active agents by profile, sessions/min, success/error rate, avg session duration |
| Cost Dashboard | Total cost/hour, cost by model (pie), cost/session histogram, spike alerts, projections |
| Behavioral Signals | Goal drift rate, tool selection quality, model escalation, planning quality, replanning rate |
| Token Usage | Input vs output ratio, token distributions, context window utilisation, cost efficiency |
| Digital Twin Fidelity | Attribute coverage %, value range conformance, span structure correctness |

### New files
```
docker/
├── prometheus.yml
└── grafana/
    ├── provisioning/datasources/prometheus.yaml
    ├── provisioning/dashboards/dashboards.yaml
    └── dashboards/
        ├── agent_overview.json
        ├── cost_dashboard.json
        ├── behavioral_signals.json
        ├── token_usage.json
        └── digital_twin_fidelity.json
```

#### NEW: `src/simulator/telemetry/metrics.py` (full implementation)

```python
class SimulatorMetrics:
    def __init__(self, meter):
        self.cost_counter    = meter.create_counter("agent.cost.total_usd")
        self.cost_histogram  = meter.create_histogram("agent.cost.per_session_usd")
        self.input_token_histogram  = meter.create_histogram("agent.tokens.input")
        self.output_token_histogram = meter.create_histogram("agent.tokens.output")
        self.session_counter   = meter.create_counter("agent.sessions.total")
        self.session_histogram = meter.create_histogram("agent.session.duration_ms")
        self.error_counter     = meter.create_counter("agent.sessions.errors")
        self.goal_drift_counter    = meter.create_counter("agent.behavior.goal_drift")
        self.model_switch_counter  = meter.create_counter("agent.behavior.model_switch")
        self.tool_quality_histogram = meter.create_histogram("agent.behavior.tool_quality")
```

### End state
Demo-ready simulator: 200 agents, 2000–5000 spans/second, 5 Grafana dashboards, pre-built schemas for major agent frameworks.

---

## Phase 7 — Productionisation

### Goal
Make the simulator usable by people outside your team without Python knowledge, manual YAML editing, or OTel familiarity.

### 7.1 Installation and Distribution

#### PyPI packaging (`pyproject.toml`)
```toml
[project]
name = "agent-simulator"
version = "2.0.0"
description = "Schema-driven OTel telemetry generator for AI agent observability"
license = {text = "MIT"}
keywords = ["opentelemetry", "observability", "ai-agents", "testing"]

[project.scripts]
agent-simulator = "simulator.cli:main"
agent-simulator-validate = "tools.validate:main"
agent-simulator-schema = "tools.schema_generator:main"
```

#### Official Docker image (`Dockerfile`)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
RUN pip install -e .
ENTRYPOINT ["agent-simulator"]
CMD ["--config", "config/default.yaml"]
```

#### `docker-compose.full.yml`
All-in-one: simulator + OTel Collector + Jaeger + Prometheus + Grafana. User mounts `./config` volume for their own profiles.

#### `CHANGELOG.md`
Version history: 2.0.0 (all V2 phases) and 1.0.0 (V1 initial release).

### 7.2 CLI (`src/simulator/cli.py`)

Full argparse CLI replacing bare `core.py` invocation:

```
agent-simulator [OPTIONS]
  --config, -c    Path to YAML config (default: config/default.yaml)
  --dry-run       Validate config, print plan, no spans emitted
  --profile       Run single named profile only
  --duration      Override run_duration_seconds
  --concurrency   Override concurrency
  --no-console    Send spans to collector only, suppress console output
```

**Dry run output:**
```
=== Agent Simulator — Dry Run ===
  Config:        config/default.yaml
  Concurrency:   200 agents
  Duration:      600s simulated (120s real)
  Profiles (5):
    rag_researcher       20%  obs_attrs=6  behavioral_signals=4
    ...
✅ Config valid. Remove --dry-run to start.
```

**Live progress** (every 5 seconds):
```
[00:12] agents=200  sessions=847  spans=12,431  cost=$0.0234  errors=3.2%
```

**Graceful shutdown**: SIGINT/SIGTERM flushes spans before exit.

### 7.3 Error Messages (`src/simulator/errors.py`)

Replaces raw Pydantic stack traces with human-readable errors:
```
❌ Config error in agent_profiles.rag_researcher:
   failure_rate: 1.5 is invalid — must be between 0.0 and 1.0
   Value given: 1.5

💡 Check config/default.yaml for reference.
```

### 7.4 Security — OTLP authentication

```yaml
telemetry:
  endpoint: "https://api.honeycomb.io:443"
  headers:
    x-honeycomb-team: "${HONEYCOMB_API_KEY}"   # env var reference
    x-honeycomb-dataset: "agent-simulator"
  tls:
    insecure: false
    cert_file: null
```

`emitter.py` resolves `${ENV_VAR}` references in header values at startup. Warns if env var is unset.

### 7.5 Documentation (`docs/`)
```
docs/
├── quickstart.md       # First trace in 5 minutes
├── configuration.md    # Full YAML reference
├── profiles.md         # Describe your agent in YAML
├── dashboards.md       # Reading each Grafana dashboard
├── digital-twin.md     # schema_generator and validate tools
├── troubleshooting.md  # Docker, Jaeger, Windows WSL2 issues
└── examples/
    ├── minimal.yaml
    ├── multi-model.yaml
    └── high-load.yaml
```

### Files changed/added in Phase 7

| File | Change |
|------|--------|
| `pyproject.toml` | PyPI metadata, entry points |
| `src/simulator/cli.py` | New — full CLI |
| `src/simulator/errors.py` | New — human-readable errors |
| `src/simulator/telemetry/emitter.py` | Auth headers, TLS config |
| `Dockerfile` | New — official image |
| `docker-compose.full.yml` | New — all-in-one stack |
| `CHANGELOG.md` | New |
| `docs/` | New — documentation directory |

### Tests added
- `tests/test_cli.py` — dry-run output, argument parsing, graceful shutdown
- `tests/test_errors.py` — human-readable errors for bad configs
- `tests/test_auth.py` — env var resolution in OTLP headers

### End state
`pip install agent-simulator`, run `agent-simulator --dry-run`, start generating telemetry in under 5 minutes without reading source code.
