# Quickstart — First trace in 5 minutes

## Prerequisites

- Python 3.11+
- Docker Desktop running

---

## Step 1 — Install

```bash
pip install agent-simulator
```

Or from source:

```bash
git clone <repo>
cd agent-simulator
pip install -e ".[dev]"
```

---

## Step 2 — Start the observability stack

```bash
# From the project root
docker compose -f docker-compose.full.yml up -d jaeger otel-collector prometheus grafana
```

Wait ~10 seconds for the services to be ready.

---

## Step 3 — Validate your config

```bash
agent-simulator --dry-run
```

You should see something like:

```
=== Agent Simulator — Dry Run ===

  Config:        config/default.yaml
  Concurrency:   200 agents
  Duration:      600s simulated (120s real time)
  Clock:         5.0x
  Seed:          42
  OTel endpoint: http://localhost:4317

  Profiles (5):
    rag_researcher          60.0%  model=gpt-4o             obs_attrs=6  behavioral_signals=0
    ...

✅ Config valid. Remove --dry-run to start.
```

---

## Step 4 — Run the simulator

```bash
agent-simulator
```

You will see a live progress line:

```
[00:05] running  agents=200  elapsed=5s  remaining=115s
[00:10] running  agents=200  elapsed=10s  remaining=110s
```

Press **Ctrl+C** to stop early — spans are flushed before exit.

---

## Step 5 — Open the dashboards

| Service    | URL                       |
|------------|---------------------------|
| Jaeger     | http://localhost:16686    |
| Grafana    | http://localhost:3000     |
| Prometheus | http://localhost:9090     |

In Jaeger, select service **agent-simulator** and click **Find Traces**.

In Grafana, the pre-built dashboards are under **Dashboards → Agent Simulator**.

---

## Next steps

- [Configuration reference](configuration.md) — all YAML options explained
- [Describing your real agent](profiles.md) — match your actual telemetry shape
- [Reading the dashboards](dashboards.md) — what each panel shows
