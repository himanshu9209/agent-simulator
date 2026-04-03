# Reading the Grafana Dashboards

Open Grafana at **http://localhost:3000** (no login required).
Navigate to **Dashboards → Agent Simulator** to find all five dashboards.

---

## Dashboard 1 — Agent Overview

**What it shows:** High-level health of the simulation run.

| Panel | Metric | What to look for |
|-------|--------|-----------------|
| Active agents | `agent.sessions.completed` rate | Should be stable near your concurrency target |
| Sessions / min | Rate of `agent.sessions.completed` | Flat line = healthy; drops = export lag |
| Success vs error rate | `agent.sessions.errors` / total | Matches your configured `failure_rate` |
| Session duration by profile | `simulator.session.duration` histogram | Each profile should have its own band |

**Normal values:** With `concurrency=200` and `clock_multiplier=5`, expect
roughly 200–500 sessions/minute depending on profile mix.

---

## Dashboard 2 — Cost Dashboard

**What it shows:** LLM cost breakdown across models and profiles.

| Panel | What to look for |
|-------|-----------------|
| Total cost / hour | Running counter; slope = spend rate |
| Cost by model | GPT-4o should cost more per session than GPT-4o-mini |
| Cost per session (histogram) | Distribution shape should match your token configs |
| Projected daily cost | Extrapolated from last 5 minutes of data |

**Debugging:** If cost shows zero, check that `pricing` is configured in YAML
and that the model name in `agent_profiles[x].llm_model` exactly matches a key
in `pricing`.

---

## Dashboard 3 — Behavioral Signals

**What it shows:** Higher-order agent behaviour patterns over time.

| Panel | Signal | Expected value |
|-------|--------|---------------|
| Goal drift rate | `agent.behavior.goal_drifts` | Matches `goal_drift.probability` in config |
| Tool selection quality | `agent.behavior.tool_quality` histogram | Mean matches `tool_selection_quality.mean` |
| Model escalation frequency | `agent.behavior.model_switches` | Matches `model_switch.probability` |
| Planning quality trend | `planning.quality_score` span attribute | Stable near configured mean |

**Tip:** If behavioral signals never appear, confirm `behavioral_signals` is
declared in your profile config. See [profiles.md](profiles.md).

---

## Dashboard 4 — Token Usage

**What it shows:** Token consumption patterns used to estimate cost and
context window headroom.

| Panel | Description |
|-------|-------------|
| Input vs output ratio | Higher output ratio = more expensive per session |
| Token count distribution | Should match your `llm_input_tokens` / `llm_output_tokens` config |
| Context window utilisation | input_tokens / model_max_context (informational) |
| Output tokens per dollar | Efficiency signal — higher = better model value |

**Note:** Context window utilisation requires `model_context_window` to be
declared in your pricing config (Phase 8 addition; shown as 0 until then).

---

## Dashboard 5 — Digital Twin Fidelity

**What it shows:** How closely the simulator output matches a reference
OTel export from your real agent.

| Panel | Description |
|-------|-------------|
| Attribute coverage % | % of real attributes present in simulator output |
| Value range conformance | % of simulator values within observed real ranges |
| Span structure correctness | Correct parent/child span relationships |
| Distribution comparison | Side-by-side histograms: real vs simulated |

This dashboard is only populated after running a validation:

```bash
agent-simulator-validate \
  --real-export path/to/real_traces.json \
  --simulator-config config/default.yaml \
  --profile rag_researcher
```

See [digital-twin.md](digital-twin.md) for the full workflow.
