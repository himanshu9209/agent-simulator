# Describing Your Real Agent in YAML

The goal of a profile is to make simulator output indistinguishable from your
real agent's telemetry. This page explains how to translate what your agent
actually emits into YAML.

---

## Workflow

```
1. Export OTel traces from your real agent (JSON format)
2. Run schema_generator to get a starter profile
3. Refine the profile by hand
4. Run the simulator with --dry-run to validate
5. Run validate to confirm shapes match
```

### Auto-generate a starter profile

```bash
agent-simulator-schema \
  --input path/to/real_traces.json \
  --profile-name my_agent \
  --output config/profiles/my_agent.yaml
```

The generated file will have all attribute names, inferred types, and
observed min/max/mean/std values filled in. Edit to taste.

---

## Matching token distributions

Look at your real agent's `gen_ai.usage.input_tokens` values across many
sessions. Calculate mean and standard deviation:

```yaml
llm_input_tokens:
  mean: 1200   # observed mean
  std: 300     # observed std dev
```

If your agent uses a small fixed range, use uniform:

```yaml
# uniform: 800–1600 tokens
llm_input_tokens:
  mean: 1200
  std: 200   # ~68% of values between 1000–1400
```

---

## Matching custom span attributes

For every custom attribute your agent emits, add an entry under
`observability_attributes` on the correct span type.

### Example: RAG agent with Cohere reranker

```yaml
observability_attributes:
  session:
    retrieval.score:
      type: float
      min: 0.55
      max: 0.98
    chunks.returned:
      type: int
      min: 1
      max: 20
    reranker.model:
      type: enum
      values: [cohere-v3, cohere-v2, bge-reranker-large]
  tool:
    tool.cache_hit:
      type: boolean
      probability: 0.28   # 28% cache hit rate from production data
    tool.input_size_kb:
      type: float
      min: 0.5
      max: 45.0
  inference:
    inference.temperature:
      type: float
      min: 0.0
      max: 0.8
```

---

## Behavioral signals

Behavioral signals are higher-order patterns that reflect *what* the agent
is doing, not just its performance characteristics.

### Goal drift

Your agent changes its objective mid-session:

```yaml
behavioral_signals:
  goal_drift:
    type: boolean
    probability: 0.04   # 4% of sessions exhibit drift
    span: session
```

Emits on `agent.session`:
- `session.goal_drift_detected: true`
- `session.original_goal: "original goal text"`
- `session.final_goal: "drifted goal text"`

### Tool selection quality

How well the agent picks the right tool for the task:

```yaml
behavioral_signals:
  tool_selection_quality:
    type: float
    mean: 0.82
    std: 0.12
    min: 0.0
    max: 1.0
    span: tool
```

Emits `tool.selection_quality` on each `tool.call` span.

### Model escalation

Agent switches to a more capable (expensive) model mid-session:

```yaml
behavioral_signals:
  model_switch:
    type: boolean
    probability: 0.03
    target_model: "gpt-4o"
    span: inference
```

Emits `inference.model_switched: true` and `inference.original_model` on
`llm.inference` spans for that session.

### Planning quality

How well the agent plans before acting:

```yaml
behavioral_signals:
  planning_quality:
    type: float
    mean: 0.88
    std: 0.09
    min: 0.0
    max: 1.0
    span: planning
```

Emits `planning.quality_score` on `agent.planning` spans.

### Enforced tool sequence

Agent must call tools in a specific order (like a RAG pipeline):

```yaml
behavioral_signals:
  tool_sequence:
    enforced: true
    order: [vector_search, reranker, summariser]
    deviation_probability: 0.04   # 4% chance wrong-order pick
```

Emits `tool.sequence_position` and `tool.sequence_deviation` on each
`tool.call` span.

### Retry reason

Why did the agent retry a tool call:

```yaml
behavioral_signals:
  retry_reason:
    type: enum
    values: [rate_limit, timeout, bad_output, network_error]
    emitted_on_retry: true
    span: tool
```

Emits `tool.retry_reason` only on calls where `failure_rate` fires.

---

## Pre-built schemas

`config/schemas/` contains ready-to-use profiles derived from real
framework OTel exports:

| File | Framework |
|------|-----------|
| `langchain_rag_agent.yaml` | LangChain RAG pipeline |
| `openai_assistants_agent.yaml` | OpenAI Assistants API |
| `langgraph_multi_agent.yaml` | LangGraph multi-agent |
| `crewai_research_crew.yaml` | CrewAI research crew |
| `autogen_coding_agent.yaml` | AutoGen coding agent |

Copy one as your starting point:

```bash
cp config/schemas/langchain_rag_agent.yaml config/my_agent.yaml
agent-simulator -c config/my_agent.yaml --dry-run
```
