# Architecture — Agent Simulation Framework V2

## Design Principles

1. **Schema-driven** — no hardcoded attribute names anywhere in the codebase
2. **Additive** — every phase builds on the previous, nothing gets thrown away
3. **Faithful** — simulator output must be indistinguishable from real agent telemetry
4. **User-configurable** — any real agent's telemetry shape can be described in YAML
5. **Runnable at every phase** — each phase ends with something testable and demonstrable

---

## Architecture Layers

```
┌──────────────────────────────────────────────────────────┐
│                    CLI / Entry Point                      │
│  agent-simulator --config config/default.yaml --dry-run  │
│  src/simulator/cli.py                                     │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                  Configuration Layer                      │
│  config/default.yaml → src/simulator/config.py (Pydantic)│
│  Validates: profiles, pricing, behavioral signals, mix    │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                   Concurrency Layer                       │
│  src/simulator/core.py — asyncio worker pool             │
│  src/simulator/clock.py — wall-clock time multiplier      │
│  N concurrent agent workers, each running sessions        │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                   Behavior Layer                          │
│  src/simulator/behavior/engine.py — session orchestrator  │
│  src/simulator/behavior/sampler.py — value generator      │
│  src/simulator/behavior/cost.py — cost calculator         │
│  src/simulator/behavior/distributions.py — stats utils    │
│  src/simulator/scenarios/engine.py — scenario evaluator   │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                  Telemetry Layer                          │
│  src/simulator/telemetry/emitter.py — OTel SDK wrapper    │
│  src/simulator/telemetry/attributes.py — schema validator │
│  src/simulator/telemetry/metrics.py — counters/histograms │
└────────────────────────┬─────────────────────────────────┘
                         │ OTLP/gRPC
┌────────────────────────▼─────────────────────────────────┐
│                  OTel Collector                           │
│  docker/docker-compose.yml                               │
│  Exports traces → Jaeger                                  │
│  Exports metrics → Prometheus                             │
└────────────┬──────────────────────────┬──────────────────┘
             │                          │
    ┌────────▼────────┐       ┌─────────▼────────┐
    │     Jaeger      │       │   Prometheus      │
    │  :16686         │       │   :9090           │
    └─────────────────┘       └─────────┬─────────┘
                                        │
                               ┌────────▼─────────┐
                               │     Grafana       │
                               │   :3000           │
                               │  5 dashboards     │
                               └──────────────────┘
```

---

## Data Flow

1. **Config load**: YAML parsed by Pydantic → typed `Config` object with profile schemas, pricing table, behavioral signal configs
2. **Worker spawn**: `core.py` creates N asyncio tasks (one per agent), each bound to a profile selected by `profile_mix` weights
3. **Session loop**: Each worker calls `engine.run_session()` repeatedly until clock expires
4. **Session execution**:
   - `planning phase` → `agent.planning` span with optional planning quality score
   - `tool phase` → N × `tool.call` spans, tool sequence optionally enforced
   - `inference phase` → `llm.inference` span with token counts + cost attributes
   - Session close → `agent.session` span with totals, goal drift, session cost
5. **Attribute sampling**: `sampler.py` reads `observability_attributes` and `behavioral_signals` from profile, samples each value to declared bounds
6. **Cost calculation**: `cost.py` looks up model in pricing table, calculates input/output/cached token costs
7. **Span export**: `emitter.py` sends spans via OTLP/gRPC to OTel Collector
8. **Metrics emission**: `metrics.py` records counters/histograms (sessions, cost, tokens, errors) via OTel Metrics API
9. **Collector routing**: OTel Collector forwards traces to Jaeger, metrics to Prometheus
10. **Visualization**: Grafana queries Prometheus; Jaeger holds trace detail

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Runtime | Python 3.11, asyncio | Concurrent agent simulation |
| Config | Pydantic v2, PyYAML | Schema validation and type safety |
| Telemetry | OpenTelemetry SDK (traces + metrics) | Span and metric emission |
| Transport | OTLP/gRPC | Span delivery to collector |
| Collector | OTel Collector (otelcol-contrib) | Fan-out to Jaeger + Prometheus |
| Trace UI | Jaeger | Span visualization |
| Metrics | Prometheus | Time-series metrics store |
| Dashboards | Grafana 10 | Pre-built observability dashboards |
| Statistics | NumPy | Gaussian/uniform sampling |
| Packaging | pyproject.toml, pip | `pip install agent-simulator` |
| Containers | Docker Compose | Single-command stack startup |

---

## Span Hierarchy

Each agent session produces this span tree:

```
agent.session                          ← root span
├── agent.planning                     ← planning phase
├── tool.call  (tool_name=X)           ┐
├── tool.call  (tool_name=Y)           ├ repeated tool_call_count times
├── tool.call  (tool_name=Z)           ┘
└── llm.inference                      ← inference phase
```

---

## Span Attribute Reference

### `agent.session` span

| Attribute | Type | Description |
|-----------|------|-------------|
| `agent.profile_type` | string | Profile name (e.g. `rag_researcher`) |
| `agent.goal` | string | Session goal string |
| `agent.worker_id` | int | Worker index |
| `session.total_cost_usd` | float | Total LLM cost for session |
| `session.goal_drift_detected` | bool | Did goal drift occur? |
| `session.original_goal` | string | Goal before drift |
| `session.final_goal` | string | Goal after drift |
| `session.tool_call_count` | int | Number of tool calls |
| `session.error` | bool | Did session error? |
| `session.error_type` | string | Error category if errored |
| + profile `observability_attributes.session.*` | varies | Custom per-profile attrs |

### `agent.planning` span

| Attribute | Type | Description |
|-----------|------|-------------|
| `agent.profile_type` | string | Profile name |
| `planning.quality_score` | float | 0.0–1.0 quality signal |
| `planning.replanning_triggered` | bool | Did agent replan? |

### `tool.call` span

| Attribute | Type | Description |
|-----------|------|-------------|
| `tool.name` | string | Tool name |
| `agent.profile_type` | string | Profile name |
| `tool.sequence_position` | int | Position in tool call sequence |
| `tool.selection_quality` | float | 0.0–1.0 quality score |
| `tool.sequence_deviation` | bool | Deviated from expected order? |
| `tool.retry_reason` | string | Enum: why tool was retried |
| + profile `observability_attributes.tool.*` | varies | Custom per-profile attrs |

### `llm.inference` span

| Attribute | Type | Description |
|-----------|------|-------------|
| `gen_ai.system` | string | Provider (openai / anthropic / google) |
| `gen_ai.request.model` | string | Model name |
| `gen_ai.usage.input_tokens` | int | Input token count |
| `gen_ai.usage.output_tokens` | int | Output token count |
| `gen_ai.usage.cost_usd` | float | Total inference cost |
| `gen_ai.usage.input_cost_usd` | float | Input token cost |
| `gen_ai.usage.output_cost_usd` | float | Output token cost |
| `inference.model_switched` | bool | Did agent escalate model? |
| `inference.original_model` | string | Originally planned model |
| + profile `observability_attributes.inference.*` | varies | Custom per-profile attrs |

---

## Attribute Sampler Types

All custom attributes declared in `observability_attributes` are processed by `behavior/sampler.py`:

| Type | Config fields | Sampling method |
|------|--------------|----------------|
| `float` | `mean` + `std` | Gaussian, clipped to `min`/`max` |
| `float` | `min` + `max` (no mean) | Uniform |
| `int` | `min` + `max` | Uniform integer |
| `int` | `values: [0,1,2]` | Random choice from list |
| `enum` | `values: [a, b, c]` | Random choice from list |
| `boolean` | `probability: 0.3` | Bernoulli with given probability |
