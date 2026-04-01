# Agent Simulation Framework — Architecture Design Document
*v1.0 — Portfolio Project*

---

## 1. Overview

The Agent Simulation Framework is a pure Python asyncio load generator that produces semantically realistic OpenTelemetry (OTel) telemetry — spans, logs, and metrics — without making any real LLM API calls. Its purpose is to provide a production-like data stream for validating AI agent observability dashboards and backends.

**Key insight:** an observability backend cannot distinguish between spans emitted by a real agent and spans emitted by a carefully crafted faker. This means dashboard validation, alerting rules, and semantic queries can all be developed and tested against simulator output before any real agents are deployed.

---

## 2. Design Goals

- Emit OTel spans that are structurally and semantically identical to those produced by real LLM agent frameworks (LangGraph, OpenAI Agents SDK, CrewAI).
- Support 100+ concurrent simulated agents with configurable concurrency via a single asyncio worker pool.
- Require zero external API calls — all timing and token counts are synthesised using statistical distributions.
- Allow all agent behaviours, failure rates, and scenario injections to be declared in YAML config with no code changes.
- Produce deterministic runs when seeded, for reproducible dashboard and alerting tests.

---

## 3. Architecture Layers

The framework is organised into five vertical layers. Each layer has a single responsibility and communicates downward only.

### 3.1 Config Layer

The topmost layer. All runtime behaviour is declared here in YAML. No Python code needs to be modified to change agent count, profile mix, failure rates, or scenario types.

**Key config sections:**

- `agent_profiles` — defines the named agent types (`rag_researcher`, `code_executor`, `web_scraper`, etc.) with their tool sets, token distributions, latency distributions, and base failure rates.
- `scenarios` — defines injectable anomaly scenarios (`tool_timeout`, `infinite_retry_loop`, `goal_drift`, `context_overflow`) and the probability that a given agent session enters each scenario.
- `simulator` — top-level settings: concurrency (number of parallel agents), `run_duration`, `clock_multiplier`, `random_seed`.
- `telemetry` — OTel exporter endpoint, batch size, and export interval.

**Example config structure:**
```yaml
simulator:
  concurrency: 200
  run_duration_seconds: 300
  clock_multiplier: 5.0  # run 5x faster than wall clock
  random_seed: 42

agent_profiles:
  rag_researcher:
    tools: [vector_search, reranker, summariser]
    llm_input_tokens:    {mean: 1200, std: 300}
    llm_output_tokens:   {mean: 250,  std: 80}
    planning_latency_ms: {mean: 200,  std: 50}
    tool_call_count:     {min: 1, max: 5}
    failure_rate: 0.05
```

### 3.2 Simulator Core

The central orchestrator. Implemented as an asyncio event loop that spawns and manages a pool of agent coroutines. Each coroutine runs one simulated agent session from start to finish, then optionally loops to simulate a continuously active agent population.

**Responsibilities:**

- Read the config layer at startup and instantiate profile objects.
- Maintain the worker pool at the configured concurrency level — when one agent session completes, a new one starts immediately.
- Distribute agent sessions across profiles according to configured mix ratios.
- Pass each session a pre-seeded random state so runs are reproducible.
- Apply the `clock_multiplier` by scaling all `sleep()` calls, allowing minutes of simulated activity to complete in seconds.

**Key implementation note:** the simulator uses `asyncio.gather()` with a semaphore to cap concurrency, not threads. This means hundreds of agents can run on a single CPU core with no OS thread overhead.

### 3.3 Behavior Engine

Responsible for executing the internal logic of a single agent session according to its profile. Each session follows a fixed span lifecycle:

- `agent.session` (root span) — created at session start, closed at session end. Carries `agent_id`, `profile_type`, and `goal` attributes.
- `agent.planning` — simulates the LLM reasoning step before tool selection. Duration drawn from the profile's `planning_latency` distribution.
- `tool.call` (0..N iterations) — each tool call is a child span under the session. Duration, tool name, and result attributes are drawn from profile distributions. The number of iterations is drawn from the profile's `tool_call_count` range.
- `llm.inference` — simulates the LLM generation step. Emits `gen_ai.input.tokens`, `gen_ai.output.tokens`, `gen_ai.model`, and latency attributes per the OTel GenAI semantic conventions.
- `agent.output` — the final span, carrying `status=success` or `status=error`.

### 3.4 Scenario Engine

Intercepts the behavior engine at the **scenario gate** — the decision point after `llm.inference` — and optionally replaces the normal completion path with an injected failure scenario. This is the primary mechanism for producing interesting, non-trivial telemetry that tests dashboard alerting and anomaly detection.

**Built-in scenarios:**

| Scenario | Span pattern | What it validates |
|---|---|---|
| `tool_timeout` | `tool.call` with `error=timeout` | Dashboard timeout rate alerting |
| `infinite_retry_loop` | `tool.call` repeated 10–20x | Loop detection, cost spike alerts |
| `goal_drift` | `agent.goal` changes mid-session | Semantic drift detection |
| `context_overflow` | `gen_ai.input.tokens` > 8000 | Context window utilisation alerts |
| `silent_failure` | `agent.output` status=success, score=0 | Quality monitoring, LLM-as-judge |

### 3.5 Clock Controller

Wraps `asyncio.sleep()` across all coroutines with a single multiplier. When `clock_multiplier=10`, a simulated agent session that would take 60 seconds in real-time completes in 6 seconds. This allows stress-testing dashboard ingest pipelines and verifying metric aggregation windows without running long overnight tests.

The controller also provides a simulated timestamp offset so that span start/end times in emitted telemetry reflect simulated wall-clock time, not real wall-clock time — useful when replaying historical scenarios.

### 3.6 Telemetry Emitter

Wraps the OpenTelemetry Python SDK. Translates the behavior engine's span lifecycle events into OTel spans with correct parent/child relationships (trace context propagation), and attaches attributes conforming to the OTel GenAI semantic conventions draft spec.

**Key span attributes emitted (GenAI conventions):**

- `gen_ai.system` — always set to `simulated`
- `gen_ai.operation.name` — one of: `chat`, `tool_call`, `agent_session`
- `gen_ai.input.tokens` — integer drawn from profile distribution
- `gen_ai.output.tokens` — integer drawn from profile distribution
- `gen_ai.model` — set per profile (e.g. `gpt-4o`, `claude-3-sonnet`)
- `agent.id` — UUID generated per session
- `agent.profile_type` — profile name (e.g. `rag_researcher`)
- `agent.goal` — short goal string, changes on `goal_drift` scenario
- `tool.name` — tool identifier (e.g. `vector_search`, `web_fetch`)
- `scenario.type` — set when a failure scenario is active

The emitter uses the OTel `BatchSpanProcessor` for efficient export. All spans are flushed to the OTel Collector via OTLP/gRPC.

---

## 4. Data Flow

A single agent session produces the following span tree:

```
agent.session  [root]
└── agent.planning
    └── tool.call  (repeated 0..N times)
        └── llm.inference
            └── agent.output  OR  agent.error
```

All spans within a session share the same `trace_id`. Parent/child relationships are enforced via OTel context propagation, producing a correctly structured trace tree in any OTel-compatible backend (Jaeger, Tempo, Honeycomb, etc.).

At scale (200 concurrent agents, `clock_multiplier=5`), the emitter produces approximately 2,000–5,000 spans per second, which is representative of a medium-sized production agent deployment.

---

## 5. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Concurrency runtime | Python asyncio | 100s of coroutines on one thread, no OS overhead |
| Telemetry SDK | opentelemetry-sdk (Python) | Industry standard, GenAI conventions support |
| Span export | OTLP/gRPC exporter | Low overhead, compatible with all collectors |
| Collector | OTel Collector (contrib) | Fan-out to multiple backends, batching, filtering |
| Config format | YAML + Pydantic validation | Declarative, type-safe, IDE-friendly |
| Statistical distributions | numpy / random (stdlib) | Gaussian latency + token count synthesis |
| Testing | pytest + pytest-asyncio | Async-native test execution |

---

## 6. Project Structure

```
agent-simulator/
├── config/
│   ├── default.yaml              # default agent profiles + scenarios
│   └── scenarios/                # individual scenario YAML overrides
├── src/
│   └── simulator/
│       ├── core.py               # asyncio worker pool, session orchestration
│       ├── clock.py              # clock controller, sleep wrapper
│       ├── config.py             # Pydantic config models + YAML loader
│       ├── behavior/
│       │   ├── engine.py         # span lifecycle execution
│       │   ├── profiles.py       # agent profile dataclasses
│       │   └── distributions.py  # Gaussian/uniform samplers
│       ├── scenarios/
│       │   ├── engine.py         # scenario gate + injection logic
│       │   └── types.py          # scenario type definitions
│       └── telemetry/
│           ├── emitter.py        # OTel SDK wrapper, span builder
│           └── attributes.py     # GenAI semantic convention constants
├── tests/
│   ├── test_behavior.py          # span tree structure assertions
│   ├── test_scenarios.py         # failure injection validation
│   └── test_emitter.py           # OTel attribute conformance
├── docker/
│   ├── otel-collector.yaml       # collector pipeline config
│   └── docker-compose.yml        # collector + optional Jaeger
├── README.md
└── pyproject.toml
```

---

## 7. Span Attribute Reference

All spans conform to the OTel GenAI semantic conventions (draft, as of early 2026).

| Attribute | Span type | Example value | Notes |
|---|---|---|---|
| `gen_ai.system` | all | `simulated` | Identifies simulator traffic |
| `gen_ai.operation.name` | all | `agent_session` | `chat` \| `tool_call` \| `agent_session` |
| `gen_ai.model` | `llm.inference` | `gpt-4o` | Set per profile config |
| `gen_ai.input.tokens` | `llm.inference` | `1450` | Gaussian sample from profile |
| `gen_ai.output.tokens` | `llm.inference` | `287` | Gaussian sample from profile |
| `agent.id` | `agent.session` | uuid4 | New UUID per session |
| `agent.profile_type` | `agent.session` | `rag_researcher` | From config profile name |
| `agent.goal` | `agent.session` | `Summarise Q3 results` | Changes on `goal_drift` scenario |
| `tool.name` | `tool.call` | `vector_search` | Drawn from profile tool list |
| `tool.call.count` | `agent.session` | `3` | Total tool calls in session |
| `scenario.type` | `agent.error` | `infinite_retry_loop` | Only set on injected failures |
| `error.type` | `agent.error` | `timeout` | OTel standard error attribute |

---

## 8. Development Milestones

### Milestone 1 — Skeleton (Week 1)
- Config loader with Pydantic validation
- Single agent coroutine emitting a correct span tree to stdout
- OTel collector running via Docker Compose

### Milestone 2 — Scale (Week 2)
- asyncio worker pool at 50 concurrent agents
- All five built-in agent profiles implemented
- Clock controller with configurable multiplier
- Spans visible in Jaeger UI

### Milestone 3 — Scenarios (Week 3)
- All five failure scenarios implemented and configurable
- pytest suite validating span tree structure and attribute conformance
- README with architecture diagram and quickstart

### Milestone 4 — Production scale (Week 4)
- 200 concurrent agents sustained for 10 minutes
- Metrics emitted (token usage, latency percentiles, error rates) via OTel metrics API
- Docker Compose stack including simulator + collector + Prometheus + Grafana

---

## 9. Output Validation Strategy

Since the simulator produces synthetic telemetry, validation ensures its output is structurally and semantically credible enough to drive real dashboard development.

**Structural validation**
- Every session must produce exactly one root span with `span_kind=SERVER`.
- All child spans must carry the parent's `trace_id`.
- `agent.output` or `agent.error` must always be the last span in a session.

**Attribute conformance**
- All required GenAI semantic convention attributes must be present on the correct span types.
- Token counts must be positive integers within the profile's configured distribution range.
- Scenario attributes must only appear on sessions where a scenario was injected.

**Reference comparison**
- Run 20–50 real agent sessions using the OpenAI Agents SDK or LangChain with MLflow tracing enabled.
- Export the raw OTel JSON from both real and simulated runs.
- Assert that span attribute keys match (values will differ — that is expected).
- Confirm span depth and tool call patterns are in the same range.
