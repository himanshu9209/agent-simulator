# Changelog

All notable changes to agent-simulator are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.1.0] — Phase 7 — Productionisation

### Added
- `agent-simulator` CLI entry point (`src/simulator/cli.py`)
  - `--dry-run` flag: validates config and prints what would run, no spans emitted
  - `--profile NAME`: run a single profile only (overrides mix weights)
  - `--duration SECONDS`: override `run_duration_seconds` without editing YAML
  - `--concurrency N`: override `concurrency` without editing YAML
  - `--no-console`: suppress console output (reserved for Phase 8 console exporter)
  - Real-time progress line printed every 5 seconds during a run
  - Graceful shutdown on Ctrl+C / SIGTERM — flushes all spans before exit
- `src/simulator/errors.py`: `ConfigError` exception and `format_validation_error()`
  — converts raw Pydantic `ValidationError` stack traces into human-readable messages
- `TlsConfig` model and `headers` / `tls` fields on `TelemetryConfig` (`config.py`)
  — auth headers support `${ENV_VAR}` syntax resolved at startup
  — TLS can be enabled for production OTLP endpoints (e.g. Honeycomb, Grafana Cloud)
- `_resolve_headers()` in `emitter.py` — env var substitution with warning on unset vars
- Metrics exporter (`metrics.py`) now inherits auth headers and TLS settings
- `Dockerfile` — official `python:3.11-slim` image, runs as non-root `simulator` user
- `docker-compose.full.yml` — single-command full stack (simulator + Jaeger + Collector
  + Prometheus + Grafana), config directory mounted so YAML edits don't need a rebuild
- `CHANGELOG.md` (this file)
- `docs/` directory:
  - `quickstart.md` — install and see first trace in 5 minutes
  - `configuration.md` — full YAML reference
  - `profiles.md` — how to describe a real agent in YAML
  - `dashboards.md` — reading each Grafana dashboard
  - `digital-twin.md` — schema_generator and validate tooling
  - `troubleshooting.md` — common issues and fixes (Docker, Jaeger, Windows WSL2)
  - `examples/minimal.yaml` — simplest valid config
  - `examples/multi-model.yaml` — cost comparison across multiple models
  - `examples/high-load.yaml` — 200-agent stress test

### Changed
- `pyproject.toml`: version `0.1.0` → `2.0.0`, added PyPI metadata (license, keywords,
  classifiers), `numpy` added to `dependencies` (was used but not declared), entry points
- `emitter.py`: `insecure=True` replaced with `config.telemetry.tls.insecure` (default
  still `True` — no behaviour change for existing configs)
- `metrics.py`: same `tls.insecure` + `headers` threading as `emitter.py`

---

## [2.0.0] — Phase 6 — Production Hardening

### Added
- 200-agent concurrency target with stable span export under load
- Prometheus scrape endpoint via OTel Collector (`8889`)
- Grafana dashboards: Agent Overview, Cost, Behavioral Signals, Token Usage, Digital Twin
  Fidelity — provisioned automatically via `docker/grafana/provisioning/`
- `SimulatorMetrics` extended with behavioral signal counters:
  `agent.behavior.goal_drifts`, `agent.behavior.model_switches`,
  `agent.behavior.tool_quality`

---

## [1.3.0] — Phase 5 — Digital Twin Validation

### Added
- `tools/validate.py` — compare a real OTel JSON export against simulator output,
  produces a gap report with suggested YAML additions
- `tools/schema_generator.py` — generate a starter YAML profile from a real OTel export
- `config/schemas/` — pre-built profiles for LangChain, OpenAI Assistants, LangGraph,
  CrewAI, AutoGen
- `ValidationConfig` in `RootConfig` with `tolerance` settings

---

## [1.2.0] — Phase 4 — Behavioral Signals

### Added
- `BehavioralSignalsSchema` and `BehavioralSignalConfig` models
- `ToolSequenceConfig` — enforced tool ordering with `deviation_probability`
- Engine emits on `agent.planning`, `tool.call`, `llm.inference`, `agent.session`:
  `planning.quality_score`, `tool.selection_quality`, `tool.sequence_position`,
  `tool.sequence_deviation`, `tool.retry_reason`, `inference.model_switched`,
  `session.goal_drift_detected`, etc.
- `ScenarioEngine` now driven by profile behavioral signal config (not hardcoded list)

---

## [1.1.0] — Phase 3 — Cost Emission

### Added
- `ModelPricing` model and `pricing` table in `RootConfig`
- `CostCalculator` in `behavior/cost.py` — input × price + output × price per model
- Span attributes: `gen_ai.usage.cost_usd`, `gen_ai.usage.input_cost_usd`,
  `gen_ai.usage.output_cost_usd`, `session.total_cost_usd`,
  `session.avg_cost_per_tool_call_usd`
- OTel Metrics cost counters/histograms: `agent.cost.total_usd`,
  `agent.cost.per_session_usd`

---

## [1.0.0] — Phase 2 — Dynamic Attribute Schema

### Added
- `AttributeConfig`, `SpanAttributeSchema` models — YAML-declared span attributes
- `AttributeSampler` in `behavior/sampler.py` — float, int, enum, boolean sampling
- `AttributeSchemaValidator` — OTel naming convention check at startup
- Dynamic attribute emission on `agent.session`, `tool.call`, `llm.inference` spans

---

## [0.1.0] — Phase 1 — V1 Skeleton (Initial Release)

### Added
- 5 hardcoded agent profiles: rag_researcher, code_executor, web_scraper,
  data_analyst, task_planner
- OTel span emission via OTLP/gRPC using `opentelemetry-sdk`
- Span hierarchy: `agent.session` → `agent.planning` → `tool.call` → `llm.inference`
  → `agent.output`
- `ClockController` — configurable time multiplier for fast simulation
- `asyncio` worker pool with configurable concurrency
- `ScenarioEngine` — injecting failure scenarios: TOOL_TIMEOUT, GOAL_DRIFT,
  CONTEXT_OVERFLOW, SILENT_FAILURE, INFINITE_RETRY_LOOP
- Docker Compose stack: OTel Collector + Jaeger
