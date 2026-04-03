# Digital Twin Validation

A *digital twin* is valid when simulator output is indistinguishable from your
real agent's telemetry. This page shows how to achieve and verify that.

---

## What "valid" means

| Criterion | What is checked |
|-----------|----------------|
| Attribute key coverage | All span attribute *names* from real output appear in simulator output |
| Type fidelity | Attribute value types match (int vs float vs string) |
| Value ranges | Simulator values fall within real observed ranges ± tolerance |
| Span structure | Correct parent/child relationships, correct span names |
| Behavioural patterns | Tool call frequency, failure rates, cost distribution |

---

## Step 1 — Export real traces

Export traces from your real agent as JSON using your OTel backend's export
feature or the OTel Collector's file exporter:

```yaml
# otel-collector.yaml — add a file exporter to capture real traces
exporters:
  file:
    path: /tmp/real_traces.json
```

Collect at least 100 sessions for statistically meaningful results.

---

## Step 2 — Generate a starter profile

```bash
agent-simulator-schema \
  --input /tmp/real_traces.json \
  --profile-name my_agent \
  --output config/profiles/my_agent.yaml
```

The schema generator:
- Extracts all attribute names from the traces
- Infers types (float / int / enum / boolean)
- Calculates min/max/mean/std from observed values
- Builds enum value lists from string attributes
- Writes a ready-to-run YAML profile

Review the output and tweak anything that looks wrong (e.g. enum lists with
too many values may benefit from collapsing rare variants).

---

## Step 3 — Run the simulator with your profile

```bash
agent-simulator -c config/profiles/my_agent.yaml --duration 300
```

---

## Step 4 — Validate

```bash
agent-simulator-validate \
  --real-export /tmp/real_traces.json \
  --simulator-config config/profiles/my_agent.yaml \
  --profile my_agent \
  --output validation_report.md
```

The validator produces a gap report:

```
## Validation Report — my_agent

### Attribute coverage: 94.2%
Missing from simulator:
  - llm.provider (type: enum, seen in 100% of real spans)
  - agent.memory_used_mb (type: float, range: 12.0–512.0)

### Value range violations: 2
  - retrieval.score: simulator emits values down to 0.42, real min is 0.58
    Fix: set min: 0.58 in observability_attributes.session.retrieval.score

### Span structure: OK

### Suggested YAML additions:
  observability_attributes:
    inference:
      llm.provider:
        type: enum
        values: [openai, anthropic]
    session:
      agent.memory_used_mb:
        type: float
        min: 12.0
        max: 512.0
```

---

## Step 5 — Iterate

Apply the suggested YAML changes, re-run the simulator, re-validate.
Repeat until coverage reaches your target (typically >95%).

---

## Tolerance settings

```yaml
validation:
  tolerance:
    value_range_margin: 0.20          # allow 20% outside observed range
    missing_attribute_threshold: 0.05 # flag if >5% of real attrs missing
```

The `value_range_margin` exists because real production values sometimes
exceed the range seen in your export sample. A 20% margin prevents false
positives on rare edge cases.

---

## Pre-built schemas

`config/schemas/` contains profiles already validated against real framework
exports. Use them as starting points to avoid the export step entirely:

```bash
cp config/schemas/langchain_rag_agent.yaml config/my_agent.yaml
# edit to match your specific configuration
agent-simulator -c config/my_agent.yaml --dry-run
```
