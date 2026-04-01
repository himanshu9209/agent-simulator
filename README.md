# Agent Simulator

Generates realistic OpenTelemetry traces and metrics for AI agent workloads — without making any real LLM calls. Useful for testing observability dashboards, alerting rules, and telemetry pipelines before you have real agents running.

The core idea: an OTel backend can't tell the difference between spans from a real agent and spans from a well-crafted faker. So you can build and validate your entire observability stack against simulator output first.

---

## Setup

Requires Python 3.11+ and Docker.

```bash
pip install -e ".[dev]"
docker compose -f docker/docker-compose.yml up -d
python -m simulator
```

Once running, open:
- **http://localhost:16686** — Jaeger (traces)
- **http://localhost:9090** — Prometheus (metrics)
- **http://localhost:3000** — Grafana (dashboards, no login required)

---

## What it emits

Each simulated agent session produces a trace like this:

```
agent.session  [root]
├── agent.planning
└── tool.call  (repeated N times)
    └── llm.inference
        └── agent.output
```

Spans carry GenAI semantic convention attributes — `gen_ai.input.tokens`, `gen_ai.output.tokens`, `gen_ai.model`, etc. — so they look identical to what LangChain, OpenAI Agents SDK, or CrewAI would emit with OTel tracing enabled.

At the default settings (200 concurrent agents, 5x clock multiplier) you get roughly 2,000–5,000 spans per second.

---

## Configuration

Edit `config/default.yaml` to change behaviour. The main knobs:

```yaml
simulator:
  concurrency: 200          # parallel agent sessions
  run_duration_seconds: 300
  clock_multiplier: 5.0     # run 5x faster than wall clock
  random_seed: 42           # remove for non-deterministic runs

agent_profiles:
  rag_researcher:
    mix_weight: 3.0
    tools: [vector_search, reranker, summariser]
    llm_model: "gpt-4o"
    llm_input_tokens:  {mean: 1200, std: 300}
    llm_output_tokens: {mean: 250,  std: 80}
    planning_latency_ms: {mean: 200, std: 50}
    tool_call_count: {min: 1, max: 5}
    failure_rate: 0.05

scenarios:
  enabled:
    tool_timeout: 0.05
    infinite_retry_loop: 0.03
    goal_drift: 0.04
    context_overflow: 0.02
    silent_failure: 0.04
```

Five agent profiles are defined out of the box: `rag_researcher`, `code_executor`, `web_scraper`, `data_analyst`, `api_orchestrator`. Each has its own tool set, token distributions, and latency profile.

Use a custom config with `python -m simulator --config path/to/config.yaml`.

---

## Failure scenarios

The scenario engine injects anomalies into a configurable percentage of sessions. Each scenario is designed to exercise a specific type of dashboard alert:

| Scenario | What happens | What it tests |
|---|---|---|
| `tool_timeout` | `tool.call` errors with `error.type=timeout`, session ends | Timeout rate alerting |
| `infinite_retry_loop` | 10–20 tool calls instead of the normal 1–5 | Loop detection, cost spike alerts |
| `goal_drift` | `agent.goal` changes mid-session during planning | Semantic drift detection |
| `context_overflow` | `gen_ai.input.tokens` forced above 8000 | Context window utilisation alerts |
| `silent_failure` | Session reports success but `agent.output.score=0` | Quality monitoring |

Affected sessions have `scenario.type` set on the root span — filter by it in Jaeger or Prometheus.

---

## Metrics

Exported to Prometheus via the OTel Collector:

| Metric | Type | Description |
|---|---|---|
| `simulator_tokens_input_tokens_total` | Counter | LLM input tokens, by model + profile |
| `simulator_tokens_output_tokens_total` | Counter | LLM output tokens, by model + profile |
| `simulator_llm_latency_milliseconds` | Histogram | LLM inference latency (simulated) |
| `simulator_session_duration_seconds` | Histogram | Session duration, by profile + scenario |
| `simulator_session_errors_total` | Counter | Failed sessions, by profile |
| `simulator_tool_calls_total` | Counter | Tool invocations, by tool name + profile |

Some useful queries to start with:

```promql
# token consumption rate
rate(simulator_tokens_input_tokens_total[1m])

# p95 LLM latency by model
histogram_quantile(0.95, rate(simulator_llm_latency_milliseconds_bucket[5m]))

# error rate
rate(simulator_session_errors_total[1m])
```

---

## Tests

```bash
pytest
```

36 tests covering span structure, GenAI attribute conformance, parent-child relationships, and all five failure scenarios.

---

## Stack

Python asyncio · opentelemetry-sdk · OTLP/gRPC · OTel Collector · Jaeger · Prometheus · Grafana · Pydantic · pytest-asyncio
