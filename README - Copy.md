# Agent Simulator

Generates realistic OpenTelemetry traces and metrics for AI agent workloads — without making any real LLM calls. Useful for testing observability dashboards, alerting rules, and telemetry pipelines before you have real agents running.

**The core idea:** an OTel backend can't tell the difference between spans from a real agent and spans from a well-crafted simulator. Describe your real agent's telemetry shape in YAML and the simulator generates faithful synthetic data matching it exactly — so you can build and validate your entire observability stack first, then plug in real agents on day one.

---

## Install

**From PyPI:**
```bash
pip install agent-simulator
```

**From source:**
```bash
git clone <repo>
cd agent-simulator
pip install -e ".[dev]"
```

**Docker (no Python required):**
```bash
docker compose -f docker-compose.full.yml up -d
```

This starts the simulator together with the full observability stack (Jaeger, Prometheus, Grafana).

---

## Quickstart

```bash
# 1. Start the observability stack
docker compose -f docker-compose.full.yml up -d jaeger otel-collector prometheus grafana

# 2. Validate your config — no spans emitted
agent-simulator --dry-run

# 3. Run
agent-simulator

# 4. Open dashboards
#    Jaeger:      http://localhost:16686
#    Grafana:     http://localhost:3000
#    Prometheus:  http://localhost:9090
```

Press **Ctrl+C** to stop — spans are flushed before exit.

---

## CLI

```
agent-simulator [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-c / --config PATH` | `config/default.yaml` | Path to YAML config file |
| `--dry-run` | — | Validate config and print the run plan. No spans emitted. |
| `--profile NAME` | — | Run a single named profile only (ignores all mix weights) |
| `--duration SECONDS` | from config | Override `run_duration_seconds` without editing YAML |
| `--concurrency N` | from config | Override `concurrency` without editing YAML |
| `--no-console` | — | Suppress console output; send spans to OTLP collector only |

**Examples:**

```bash
# Validate a custom config
agent-simulator -c config/my_agent.yaml --dry-run

# Quick smoke test — 5 agents, 30 seconds, no config editing
agent-simulator --concurrency 5 --duration 30

# Test a single profile
agent-simulator --profile rag_researcher

# Run with a Honeycomb endpoint using env var auth
HONEYCOMB_API_KEY=hcaik_... agent-simulator -c config/honeycomb.yaml
```

**Dry-run output:**
```
=== Agent Simulator — Dry Run ===

  Config:        config/default.yaml
  Concurrency:   200 agents
  Duration:      600s simulated (120s real time)
  Clock:         5.0x
  Seed:          42
  OTel endpoint: http://localhost:4317

  Profiles (5):
    rag_researcher         60.0%  model=gpt-4o             obs_attrs=6  behavioral_signals=4
    code_executor          20.0%  model=gpt-4o             obs_attrs=5  behavioral_signals=2
    ...

  Pricing models: ['gpt-4o', 'gpt-4o-mini', 'claude-3-sonnet']

✅ Config valid. Remove --dry-run to start.
```

---

## What it emits

Each simulated agent session produces a trace with this span hierarchy:

```
agent.session         [root — carries session-level attributes and total cost]
├── agent.planning    [planning quality score, replan flag]
└── tool.call         [repeated N times — tool attributes, behavioral signals]
    └── llm.inference [token counts, per-call cost, model switch flag]
        └── agent.output
```

**Standard GenAI attributes** on every span (compatible with LangChain, OpenAI Agents SDK, CrewAI OTel output):

| Attribute | Example |
|-----------|---------|
| `gen_ai.system` | `"simulated"` |
| `gen_ai.operation.name` | `"agent_session"`, `"tool_call"`, `"chat"` |
| `gen_ai.request.model` | `"gpt-4o"` |
| `gen_ai.usage.input_tokens` | `1247` |
| `gen_ai.usage.output_tokens` | `312` |
| `agent.id` | UUID per session |
| `agent.profile_type` | `"rag_researcher"` |
| `agent.goal` | `"Summarise Q3 financial results"` |

**Cost attributes** (on `llm.inference` and `agent.session`):

| Attribute | Description |
|-----------|-------------|
| `gen_ai.usage.cost_usd` | Cost of this single inference call |
| `gen_ai.usage.input_cost_usd` | Input token cost |
| `gen_ai.usage.output_cost_usd` | Output token cost |
| `session.total_cost_usd` | Total cost across all inference calls in the session |
| `session.avg_cost_per_tool_call_usd` | Cost efficiency signal |

**Behavioral signal attributes** (when declared in profile):

| Attribute | Span | Description |
|-----------|------|-------------|
| `session.goal_drift_detected` | `agent.session` | Agent deviated from original goal |
| `session.original_goal` | `agent.session` | Goal before drift |
| `session.final_goal` | `agent.session` | Goal after drift |
| `planning.quality_score` | `agent.planning` | 0.0–1.0 plan quality signal |
| `planning.replanning_triggered` | `agent.planning` | Agent discarded and rebuilt its plan |
| `tool.selection_quality` | `tool.call` | 0.0–1.0 right-tool-picked signal |
| `tool.sequence_position` | `tool.call` | Index in expected tool order |
| `tool.sequence_deviation` | `tool.call` | Agent deviated from expected sequence |
| `tool.retry_reason` | `tool.call` | Why this call was retried |
| `inference.model_switched` | `llm.inference` | Agent escalated to more expensive model |
| `inference.original_model` | `llm.inference` | Model originally planned |

At the default settings (200 concurrent agents, 5x clock multiplier) the simulator emits roughly **2,000–5,000 spans per second**.

---

## Built-in agent profiles

Five profiles ship in `config/default.yaml`. Each represents a distinct agent archetype with its own tool set, token distribution, and observability attributes.

### `rag_researcher`
Retrieval-augmented generation pipeline. High input token count (context assembly), moderate output, sequential tool ordering enforced.

- **Tools:** `vector_search` → `reranker` → `summariser`
- **Model:** gpt-4o
- **Custom attributes:** `retrieval.score`, `chunks.returned`, `reranker.model`, `index.name`, `tool.input_size_kb`, `tool.cache_hit`, `inference.temperature`, `inference.top_p`

### `code_executor`
Agent that writes and runs code in a sandbox. High output token count (generated code), highest failure rate, sandbox type emitted per session.

- **Tools:** `code_interpreter`, `file_reader`, `shell_exec`
- **Model:** gpt-4o
- **Custom attributes:** `execution.language`, `sandbox.type`, `execution.exit_code`, `execution.runtime_ms`, `execution.memory_mb`

### `web_scraper`
Fetches and parses web content. Wide tool call count range (2–8 calls), highest failure rate, HTTP status codes on each tool span.

- **Tools:** `web_fetch`, `html_parser`, `link_extractor`
- **Model:** claude-3-sonnet
- **Custom attributes:** `pages.scraped`, `content.size_kb`, `http.status_code`, `http.response_ms`, `robots.txt.respected`

### `data_analyst`
SQL/dataframe analysis. High input tokens (large datasets), lowest failure rate, query metadata on tool spans.

- **Tools:** `sql_query`, `dataframe_op`, `chart_renderer`
- **Model:** gpt-4o
- **Custom attributes:** `rows.processed`, `query.complexity`, `query.execution_ms`, `query.rows_returned`, `db.type`

### `task_planner`
Hierarchical planning agent. Highest input token count (complex goal decomposition), plan depth and task counts on session spans.

- **Tools:** `goal_decomposer`, `task_scheduler`, `dependency_resolver`
- **Model:** claude-3-sonnet
- **Custom attributes:** `tasks.created`, `plan.depth`, `dependencies.count`, `subtasks.count`

---

## Configuration

The simulator is entirely YAML-driven. Edit `config/default.yaml` or pass any path with `-c`.

### `simulator`

```yaml
simulator:
  concurrency: 200           # parallel agent sessions
  run_duration_seconds: 600  # simulated time (not wall-clock)
  clock_multiplier: 5.0      # 5x → 600s completes in 120s real time
  random_seed: 42            # remove for non-deterministic runs
```

### `agent_profiles`

```yaml
agent_profiles:
  my_agent:
    mix_weight: 1.0                     # relative weight in profile selection
    tools: [search, summarise]
    llm_model: "gpt-4o"                 # must match a key in pricing
    llm_input_tokens:  {mean: 1200, std: 300}
    llm_output_tokens: {mean: 250,  std: 80}
    planning_latency_ms: {mean: 200, std: 50}
    tool_call_count:   {min: 1, max: 5}
    failure_rate: 0.05                  # probability a session ends in error
```

### Custom span attributes

Declare any attribute your real agent emits — the simulator generates synthetic values within the declared bounds:

```yaml
observability_attributes:
  session:                               # emitted on agent.session span
    retrieval.score:  {type: float, min: 0.6, max: 1.0}
    reranker.model:   {type: enum,  values: [cohere-v3, bge-reranker]}
    chunks.returned:  {type: int,   min: 1,  max: 20}

  tool:                                  # emitted on each tool.call span
    tool.cache_hit:       {type: boolean, probability: 0.3}
    tool.input_size_kb:   {type: float,   min: 0.5, max: 50.0}

  inference:                             # emitted on each llm.inference span
    inference.temperature: {type: float, min: 0.0, max: 1.0}
```

Supported attribute types:

| Type | Fields | Sampling |
|------|--------|----------|
| `float` | `min`, `max` | uniform; add `mean`+`std` for gaussian |
| `int` | `min`, `max` or `values` | uniform range or pick from list |
| `enum` | `values` | uniform pick from list |
| `boolean` | `probability` | Bernoulli (default 0.5) |

### Behavioral signals

Higher-order signals that reflect *what* the agent is doing, not just how fast:

```yaml
behavioral_signals:
  goal_drift:                # session-level: did the agent deviate from its goal?
    type: boolean
    probability: 0.05
    span: session

  tool_selection_quality:    # per-tool: how good was the tool choice?
    type: float
    mean: 0.85
    std: 0.10
    min: 0.0
    max: 1.0
    span: tool

  planning_quality:          # per-planning-span: how well did the agent plan?
    type: float
    mean: 0.88
    std: 0.09
    span: planning

  model_switch:              # did the agent escalate to a more expensive model?
    type: boolean
    probability: 0.03
    target_model: "gpt-4o"
    span: inference

  tool_sequence:             # enforce realistic tool ordering
    enforced: true
    order: [vector_search, reranker, summariser]
    deviation_probability: 0.04

  retry_reason:              # why was this tool call retried?
    type: enum
    values: [rate_limit, timeout, bad_output, network_error]
    emitted_on_retry: true
    span: tool
```

### Pricing table

Controls cost attributes emitted on `llm.inference` and `agent.session` spans:

```yaml
pricing:
  gpt-4o:
    input_per_million:        2.50
    output_per_million:       10.00
    cached_input_per_million: 1.25    # OpenAI prompt caching
  claude-3-sonnet:
    input_per_million:        3.00
    output_per_million:       15.00
    cache_write_per_million:  3.75    # Anthropic cache write
    cache_read_per_million:   0.30    # Anthropic cache read
```

Unknown models return zero cost and log a warning — no crash.

### Failure scenarios

```yaml
scenarios:
  enabled:
    tool_timeout:        0.05   # 5% of sessions hit a tool timeout
    goal_drift:          0.04
    context_overflow:    0.02
    silent_failure:      0.04
    infinite_retry_loop: 0.03
```

| Scenario | What happens | What it exercises |
|----------|-------------|-------------------|
| `tool_timeout` | `tool.call` errors with `error.type=timeout` | Timeout rate alerting |
| `infinite_retry_loop` | 10–20 tool calls instead of the normal 1–5 | Loop detection, cost spike alerts |
| `goal_drift` | `agent.goal` changes mid-session | Semantic drift detection |
| `context_overflow` | `gen_ai.usage.input_tokens` forced above 8000 | Context window utilisation alerts |
| `silent_failure` | Session reports success but `agent.output.score=0` | Quality monitoring |

Affected sessions have `scenario.type` set on the root span — filter by it in Jaeger or Prometheus.

### Telemetry and auth

```yaml
telemetry:
  exporter_endpoint: "http://localhost:4317"   # OTLP/gRPC
  batch_size: 512
  export_interval_ms: 5000
  headers: {}        # optional auth headers (see below)
  tls:
    insecure: true   # set false for TLS endpoints
```

**Sending to a cloud backend (e.g. Honeycomb):**

```yaml
telemetry:
  exporter_endpoint: "https://api.honeycomb.io:443"
  headers:
    x-honeycomb-team:    "${HONEYCOMB_API_KEY}"   # resolved from env var at startup
    x-honeycomb-dataset: "agent-simulator"
  tls:
    insecure: false
```

```bash
export HONEYCOMB_API_KEY=hcaik_...
agent-simulator -c config/honeycomb.yaml
```

---

## Cost emission

Every session emits accurate cost figures based on token counts × model pricing. Look for these in Jaeger on `llm.inference` spans:

```
gen_ai.usage.cost_usd        = 0.00003125
gen_ai.usage.input_cost_usd  = 0.00000312
gen_ai.usage.output_cost_usd = 0.00003125
```

And on the root `agent.session` span:

```
session.total_cost_usd              = 0.00014821
session.avg_cost_per_tool_call_usd  = 0.00002964
```

The Grafana **Cost Dashboard** shows:
- Running total cost per hour
- Cost breakdown by model (useful for comparing gpt-4o vs claude-3-sonnet)
- Cost per session distribution
- Projected daily/monthly cost

---

## Behavioral signals

Behavioral signals are declared in each profile's `behavioral_signals` block and emitted as span attributes. They make simulator output useful for testing higher-order alerting rules — not just latency and error rate, but *what the agent was doing*.

**Reading behavioral signals in Jaeger:**

1. Open any `agent.session` trace
2. Look for `session.goal_drift_detected`, `session.original_goal`, `session.final_goal`
3. Open a child `tool.call` span — look for `tool.selection_quality`, `tool.sequence_deviation`
4. Open `agent.planning` — look for `planning.quality_score`

**Building alerts from behavioral signals:**

```promql
# Goal drift rate over last 5 minutes
rate(agent_behavior_goal_drifts_total[5m])

# Tool selection quality distribution
histogram_quantile(0.05, rate(agent_behavior_tool_quality_bucket[5m]))

# Model escalation frequency
rate(agent_behavior_model_switches_total[5m])
```

---

## Digital twin tooling

The simulator ships two CLI tools for validating that your YAML profile faithfully mirrors your real agent's telemetry.

### Generate a profile from real traces

```bash
# Give it a real OTel JSON export, get a YAML profile back
agent-simulator-schema \
  --input path/to/real_traces.json \
  --profile-name my_agent \
  --output config/profiles/my_agent.yaml
```

The generator extracts all attribute names, infers types, calculates observed min/max/mean/std, and writes a ready-to-run profile.

### Validate the digital twin

```bash
# Compare simulator output against the real export
agent-simulator-validate \
  --real-export path/to/real_traces.json \
  --simulator-config config/profiles/my_agent.yaml \
  --profile my_agent \
  --output validation_report.md
```

The validator checks attribute key coverage, value type fidelity, value range conformance, and span structure — then produces a gap report with suggested YAML additions to close each gap.

### Pre-built schemas

`config/schemas/` contains profiles derived from real framework OTel exports:

| File | Framework |
|------|-----------|
| `langchain_rag_agent.yaml` | LangChain RAG pipeline |
| `openai_assistants_agent.yaml` | OpenAI Assistants API |
| `langgraph_multi_agent.yaml` | LangGraph multi-agent |
| `crewai_research_crew.yaml` | CrewAI research crew |
| `autogen_coding_agent.yaml` | AutoGen coding agent |

Use them as starting points without needing to export real traces first.

---

## Docker stack

### Development stack (observability only)

```bash
# Start Jaeger, OTel Collector, Prometheus, Grafana
docker compose -f docker/docker-compose.yml up -d

# Run simulator from local Python
agent-simulator
```

### Full stack (simulator + observability)

```bash
# Start everything — simulator runs once then exits
docker compose -f docker-compose.full.yml up -d
```

The `docker-compose.full.yml` mounts `./config` into the simulator container — edit your YAML without rebuilding:

```bash
# Use a custom config
docker compose -f docker-compose.full.yml run simulator \
  --config config/my_agent.yaml
```

**Service URLs:**

| Service | URL | Purpose |
|---------|-----|---------|
| Jaeger | http://localhost:16686 | Trace explorer |
| Grafana | http://localhost:3000 | Pre-built dashboards (no login) |
| Prometheus | http://localhost:9090 | Metrics query |
| OTLP/gRPC | localhost:4317 | Collector ingestion point |

---

## Grafana dashboards

Five dashboards are provisioned automatically at startup.
Open **http://localhost:3000** → **Dashboards** → **Agent Simulator**.

### Agent Overview
Active agents by profile type, sessions/min, success vs error rate, session duration distribution by profile.

### Cost Dashboard
Total cost per hour (running counter), cost breakdown by model, cost per session histogram, projected daily/monthly cost. Useful for comparing model choices before committing to production.

### Behavioral Signals
Goal drift rate, tool selection quality distribution, model escalation frequency, planning quality trends, replanning trigger rate. Build your alerting thresholds against these panels.

### Token Usage
Input/output token ratio by profile, token count distribution, context window utilisation, output tokens per dollar (efficiency signal).

### Digital Twin Fidelity
Attribute coverage vs reference schema, value range conformance, span structure correctness. Populated after running `agent-simulator-validate`.

---

## Metrics

Exported to Prometheus via the OTel Collector on port `8889`:

**Session and token metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `simulator_tokens_input_tokens_total` | Counter | LLM input tokens, by model + profile |
| `simulator_tokens_output_tokens_total` | Counter | LLM output tokens, by model + profile |
| `simulator_llm_latency_milliseconds` | Histogram | LLM inference latency |
| `simulator_session_duration_seconds` | Histogram | Session duration, by profile + scenario |
| `simulator_session_errors_total` | Counter | Failed sessions, by profile |
| `simulator_tool_calls_total` | Counter | Tool invocations, by tool + profile |

**Cost metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `agent_cost_total_usd_total` | Counter | Cumulative LLM cost |
| `agent_cost_per_session_usd` | Histogram | Cost distribution per session |

**Behavioral metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `agent_sessions_completed_total` | Counter | Completed sessions, by profile |
| `agent_behavior_goal_drifts_total` | Counter | Goal drift events |
| `agent_behavior_model_switches_total` | Counter | Model escalation events |
| `agent_behavior_tool_quality` | Histogram | Tool selection quality score |

**Useful PromQL queries:**

```promql
# Token consumption rate
rate(simulator_tokens_input_tokens_total[1m])

# p95 LLM latency by model
histogram_quantile(0.95, rate(simulator_llm_latency_milliseconds_bucket[5m]))

# Error rate
rate(simulator_session_errors_total[1m])

# Cost per hour (extrapolated)
rate(agent_cost_total_usd_total[5m]) * 3600

# Goal drift rate
rate(agent_behavior_goal_drifts_total[5m])
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/quickstart.md](docs/quickstart.md) | Install and see first trace in 5 minutes |
| [docs/configuration.md](docs/configuration.md) | Full YAML reference with all fields and defaults |
| [docs/profiles.md](docs/profiles.md) | How to describe your real agent in YAML |
| [docs/dashboards.md](docs/dashboards.md) | What each Grafana panel shows and how to interpret it |
| [docs/digital-twin.md](docs/digital-twin.md) | schema_generator and validate workflow |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Docker, Jaeger, Windows WSL2, common config errors |

**Example configs:**

| File | When to use it |
|------|---------------|
| [docs/examples/minimal.yaml](docs/examples/minimal.yaml) | Smoke-test a new OTel Collector setup |
| [docs/examples/multi-model.yaml](docs/examples/multi-model.yaml) | Compare cost across gpt-4o, gpt-4o-mini, claude-3-sonnet |
| [docs/examples/high-load.yaml](docs/examples/high-load.yaml) | 200-agent stress test, 5x clock (completes in ~2 min) |

---

## Development phases

| Phase | What was built |
|-------|---------------|
| 1 — V1 Skeleton | 5 hardcoded agent profiles, OTel span emission via OTLP/gRPC, asyncio worker pool, `ClockController`, Docker Compose + Jaeger |
| 2 — Dynamic Attribute Schema | YAML-declared span attributes (`observability_attributes`), `AttributeSampler` (float/int/enum/boolean), OTel naming validation at startup |
| 3 — Cost Emission | Per-model pricing table in YAML, `gen_ai.usage.cost_usd` on `llm.inference`, `session.total_cost_usd` on `agent.session`, OTel Metrics cost counters |
| 4 — Behavioral Signals | `behavioral_signals` block in profiles — goal drift, tool selection quality, model switch, planning quality, tool sequence enforcement; scenario engine made fully dynamic |
| 5 — Digital Twin Validation | `agent-simulator-schema` generates YAML profiles from real OTel exports; `agent-simulator-validate` compares shapes and produces gap reports; pre-built schemas for 5 frameworks |
| 6 — Production Hardening | 200-agent concurrency target, Prometheus + Grafana added to Docker stack, 5 pre-built Grafana dashboards provisioned automatically |
| 7 — Productionisation | `agent-simulator` CLI with `--dry-run`, `--profile`, `--duration`, `--concurrency`; human-readable config errors; auth headers with `${ENV_VAR}` syntax; TLS support; `Dockerfile`; `docker-compose.full.yml`; `docs/` |

---

## Tests

```bash
pytest
```

180 tests covering span structure, GenAI attribute conformance, parent-child relationships, all five failure scenarios, attribute sampling bounds, cost calculations, behavioral signal probabilities, digital twin validation logic, CLI argument parsing, error formatting, and OTLP auth header resolution.

---

## Stack

Python asyncio · opentelemetry-sdk · OTLP/gRPC · OTel Collector · Jaeger · Prometheus · Grafana · Pydantic v2 · NumPy · pytest-asyncio · Docker Compose
