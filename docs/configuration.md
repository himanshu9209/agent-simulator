# Configuration Reference

The simulator is driven entirely by a single YAML file.
The default is `config/default.yaml`; pass any path with `--config`.

---

## Top-level structure

```yaml
simulator:       # concurrency, duration, clock speed
agent_profiles:  # one or more agent profiles (the core of the config)
pricing:         # model pricing table for cost emission
scenarios:       # failure scenario injection
telemetry:       # OTel Collector endpoint, auth, TLS
validation:      # digital twin validation settings
```

---

## `simulator`

```yaml
simulator:
  concurrency: 200           # number of agents running in parallel
  run_duration_seconds: 600  # simulated wall-clock duration
  clock_multiplier: 5.0      # speed-up factor (5.0 → 600s completes in 120s real)
  random_seed: 42            # null for non-deterministic runs
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `concurrency` | int ≥ 1 | 1 | Parallel agent sessions |
| `run_duration_seconds` | int ≥ 1 | 60 | Simulated time to run |
| `clock_multiplier` | float > 0 | 1.0 | >1 speeds up simulation, <1 slows it down |
| `random_seed` | int \| null | null | Seed for reproducibility |

---

## `agent_profiles`

Each key is a profile name; values configure the agent's behaviour.

```yaml
agent_profiles:
  my_agent:
    mix_weight: 1.0            # relative probability of picking this profile
    tools: [search, summarise] # tool names (strings, used as span attributes)
    llm_model: "gpt-4o"        # model name — must match a key in `pricing`
    llm_input_tokens:          # Gaussian distribution
      mean: 1200
      std: 300
    llm_output_tokens:
      mean: 250
      std: 80
    planning_latency_ms:
      mean: 200
      std: 50
    tool_call_count:           # Uniform integer distribution
      min: 1
      max: 5
    failure_rate: 0.05         # probability a session ends in error (0.0–1.0)
    observability_attributes:  # custom span attributes (Phase 2)
      session: {}
      tool: {}
      inference: {}
    behavioral_signals: null   # behavioral signal config (Phase 4)
```

### `observability_attributes`

Declare custom attributes emitted on each span type:

```yaml
observability_attributes:
  session:
    retrieval.score:  {type: float,   min: 0.6, max: 1.0}
    reranker.model:   {type: enum,    values: [cohere-v3, bge-reranker]}
  tool:
    tool.cache_hit:   {type: boolean, probability: 0.3}
    tool.input_size_kb: {type: float, min: 0.5, max: 50.0}
  inference:
    inference.temperature: {type: float, min: 0.0, max: 1.0}
```

Supported attribute types:

| Type | Required fields | Optional fields |
|------|----------------|-----------------|
| `float` | — | `min`, `max`, `mean`, `std` (gaussian if mean+std present, else uniform) |
| `int` | — | `min`, `max` (uniform) or `values` (pick from list) |
| `enum` | `values` | — |
| `boolean` | — | `probability` (default 0.5) |

### `behavioral_signals`

See [profiles.md](profiles.md) for the full behavioral signals reference.

---

## `pricing`

```yaml
pricing:
  gpt-4o:
    input_per_million:        2.50
    output_per_million:       10.00
    cached_input_per_million: 1.25
  claude-3-sonnet:
    input_per_million:        3.00
    output_per_million:       15.00
    cache_write_per_million:  3.75
    cache_read_per_million:   0.30
```

All prices are USD per 1 million tokens.
Unknown models return zero cost (no crash).

---

## `scenarios`

Inject failure scenarios with a per-scenario probability:

```yaml
scenarios:
  enabled:
    tool_timeout:        0.05   # 5% of sessions hit a tool timeout
    goal_drift:          0.03
    context_overflow:    0.02
    silent_failure:      0.01
    infinite_retry_loop: 0.01
```

---

## `telemetry`

```yaml
telemetry:
  exporter_endpoint: "http://localhost:4317"  # OTLP/gRPC
  batch_size: 512
  export_interval_ms: 5000
  headers: {}            # optional auth headers
  tls:
    insecure: true       # set false for TLS endpoints
    cert_file: null      # path to client cert for mTLS
```

### Auth headers with environment variables

Header values can reference env vars using `${VAR_NAME}` syntax:

```yaml
telemetry:
  endpoint: "https://api.honeycomb.io:443"
  headers:
    x-honeycomb-team: "${HONEYCOMB_API_KEY}"
    x-honeycomb-dataset: "agent-simulator"
  tls:
    insecure: false
```

Set the variable before running:

```bash
export HONEYCOMB_API_KEY=hcaik_...
agent-simulator
```

---

## `validation`

```yaml
validation:
  enabled: false
  real_export_path: null          # path to a real OTel JSON export
  profile_to_validate: null       # which profile to compare
  tolerance:
    value_range_margin: 0.20      # 20% outside observed range is OK
    missing_attribute_threshold: 0.05  # flag if >5% of real attrs missing
```

See [digital-twin.md](digital-twin.md) for usage.

---

## CLI overrides

Any of these can be overridden at run time without editing YAML:

```bash
agent-simulator --concurrency 10 --duration 30  # quick smoke test
agent-simulator --profile rag_researcher         # single profile
agent-simulator --dry-run                        # validate only
```
