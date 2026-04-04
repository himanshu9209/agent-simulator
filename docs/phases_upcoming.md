# Upcoming Phases — Design Detail

---

## Phase 8 — Web UI

### Goal
Provide a browser-based interface for configuring the simulator, viewing and
editing YAML profiles, monitoring live runs, and linking directly to Grafana
dashboards. Removes the last barrier for non-developer users.

Phase 8 is split into three parts that can be built and merged independently.

### Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Backend API | FastAPI (Python) | Same language as simulator, async-native |
| Frontend | React + TypeScript | Component model suits the form-heavy UI |
| Styling | Tailwind CSS | Utility-first, no design system needed |
| State management | React Query | Server state sync for live run data |
| YAML editor | CodeMirror 6 | Syntax highlighting, validation inline |
| Charts | Recharts | Lightweight, React-native |
| Packaging | Single Docker service | Added to docker-compose.yml |

---

## Phase 8a — Backend API

### Goal
Stand up a fully tested FastAPI backend that the frontend (Phase 8b) can
integrate against. The backend must be runnable standalone (`uvicorn`) before
any frontend work begins.

### New directory: `src/simulator/api/`

```
src/simulator/api/
├── __init__.py
├── main.py              # FastAPI app, CORS, router registration
├── routers/
│   ├── profiles.py      # CRUD for agent profiles
│   ├── config.py        # Read/write full config YAML
│   ├── run.py           # Start/stop simulator, WebSocket live stream
│   └── pricing.py       # Pricing table CRUD
├── models.py            # Pydantic response models
└── config_manager.py    # Thread-safe config file read/write
```

### Key API endpoints

```
GET    /api/profiles              → list all profiles
GET    /api/profiles/:name        → get one profile
POST   /api/profiles              → create profile
PUT    /api/profiles/:name        → update profile
DELETE /api/profiles/:name        → delete profile

GET    /api/config                → get full YAML as string
PUT    /api/config                → validate + save full YAML

POST   /api/run/start             → start simulator
POST   /api/run/stop              → graceful stop
GET    /api/run/status            → current run stats
WS     /api/run/stream            → WebSocket live stats stream

GET    /api/pricing               → get pricing table
PUT    /api/pricing               → update pricing table

POST   /api/validate              → dry-run validation, returns report
POST   /api/schema/generate       → schema_generator on uploaded OTel export
```

### Config Manager (thread-safe YAML read/write)

```python
class ConfigManager:
    """Thread-safe reader/writer for default.yaml.
    Validates before writing — never writes an invalid config.
    Keeps last 5 versions as backups in config/.backups/
    """
    def read(self) -> Config: ...
    def write(self, cfg: Config) -> None: ...
    def validate_raw(self, yaml_str: str) -> List[str]: ...  # returns error list
    def backup(self) -> Path: ...
```

### Files to Add/Modify

| File | Change |
|------|--------|
| `src/simulator/api/main.py` | New — FastAPI app |
| `src/simulator/api/routers/` | New — 4 route files |
| `src/simulator/api/config_manager.py` | New — thread-safe config R/W |
| `pyproject.toml` | Add fastapi, uvicorn, websockets dependencies |

### Tests to Add

- `tests/test_api_profiles.py` — CRUD operations on profiles via API
- `tests/test_api_config.py` — config validation and write via API
- `tests/test_api_run.py` — start/stop/status endpoints
- `tests/test_config_manager.py` — thread safety, backup, validation

### End State

`uvicorn simulator.api.main:app` starts cleanly, all endpoints return correct
responses, all tests pass. No frontend required to validate this phase.

---

## Phase 8b — Frontend

### Goal
Build the full React + TypeScript UI. All pages are complete and wired to the
Phase 8a API via React Query. WebSocket live stats are visible on the Dashboard.
YAML editing works via CodeMirror. The app runs with `npm run dev` pointing at
a locally running backend.

### UI Structure

```
agent-simulator UI  (http://localhost:8080)
├── /                     → Dashboard (live run status)
├── /profiles             → Profile list and editor
├── /profiles/new         → New profile wizard
├── /profiles/:name       → Edit existing profile
├── /scenarios            → Scenario configuration
├── /pricing              → Model pricing table editor
├── /config               → Raw YAML editor with validation
├── /run                  → Start / stop / monitor runs
└── /dashboards           → Links to Grafana dashboards
```

### Page Designs

#### 1. Dashboard (/)
Live run status page:
- **Run status** — running / stopped, time elapsed, time remaining
- **Live counters** — active agents, sessions completed, spans/sec, total cost
- **Mini charts** — sessions/min, error rate, cost/min (last 60s rolling)
- **Start / Stop button**
- **Quick links** — Jaeger, Grafana, Prometheus

```
┌─────────────────────────────────────────────────────┐
│  Agent Simulator                          ● Running  │
├──────────┬──────────┬──────────┬────────────────────┤
│ Agents   │ Sessions │ Spans/s  │ Total Cost         │
│ 200      │ 12,847   │ 2,341    │ $0.2847            │
├──────────┴──────────┴──────────┴────────────────────┤
│  Sessions/min ────────────────────────────────────  │
│  Error rate   ────────────────────────────────────  │
├─────────────────────────────────────────────────────┤
│  [Stop Simulation]   Jaeger  Grafana  Prometheus    │
└─────────────────────────────────────────────────────┘
```

#### 2. Profile List (/profiles)
Table of all configured profiles:
- Profile name, Model, Tool count, Custom attribute count, Behavioral signal count, Profile mix weight (%)
- Edit / Duplicate / Delete actions
- **+ New Profile** button

#### 3. Profile Editor (/profiles/:name)
Tabbed editor for a single agent profile:

**Tab 1 — Basic Settings**
- Profile name (text), LLM model (dropdown from pricing table), Profile mix weight (slider 0–100%), Failure rate (slider 0–50%), Tool list (tag input)

**Tab 2 — Distributions**
Form inputs with live preview charts:
- LLM input tokens (mean + std → bell curve preview)
- LLM output tokens (mean + std → bell curve preview)
- Planning latency ms, Tool latency ms, Tool call count (min + max → range preview)

**Tab 3 — Observability Attributes**
Table per span type (session / tool / inference):
- Attribute name (text, OTel naming validated), Type (dropdown), Type-specific fields
- Add / Remove row actions

**Tab 4 — Behavioral Signals**
- Goal drift (toggle + probability slider)
- Tool selection quality (toggle + mean/std sliders)
- Model switch (toggle + probability + target model dropdown)
- Planning quality (toggle + mean/std)
- Tool sequence (toggle + ordered list editor)
- Custom signals (add/remove table)

**Tab 5 — YAML Preview**
Read-only CodeMirror view of generated YAML. Copy to clipboard + Download buttons.

#### 4. Raw Config Editor (/config)
Full CodeMirror editor for `default.yaml`:
- YAML syntax highlighting, inline validation (red underline), error panel
- **Save**, **Reset to default**, **Download** buttons

#### 5. Run Controller (/run)
- Config summary (concurrency, duration, clock multiplier)
- Override fields — duration, concurrency, single profile mode
- **Dry Run** button — calls `agent-simulator --dry-run`, shows output
- **Start** / **Stop** buttons
- Live log tail — last 50 lines via WebSocket

#### 6. Pricing Table (/pricing)
Editable table: model name, input/output cost per 1M tokens, provider-specific fields (cached input, cache write/read). Add / Remove rows. **Save** button.

### Frontend Structure

```
ui/
├── package.json
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── components/
    │   ├── Layout/             # Sidebar, header, nav
    │   ├── ProfileEditor/      # Tabbed profile form
    │   ├── Dashboard/          # Live stats widgets
    │   ├── RunController/      # Start/stop/log tail
    │   ├── PricingTable/       # Editable pricing grid
    │   └── YamlEditor/         # CodeMirror wrapper
    ├── pages/
    │   ├── DashboardPage.tsx
    │   ├── ProfilesPage.tsx
    │   ├── ProfileEditorPage.tsx
    │   ├── ConfigPage.tsx
    │   ├── RunPage.tsx
    │   └── PricingPage.tsx
    ├── api/                    # React Query hooks for each endpoint
    └── types/                  # TypeScript types mirroring Pydantic models
```

### Files to Add

| File | Change |
|------|--------|
| `ui/` | New — full React frontend |

### End State

`npm run dev` starts the UI, all pages load, API calls succeed against a local
backend, WebSocket live stats update in real time on the Dashboard, YAML editor
saves and validates correctly. No Docker required to validate this phase.

---

## Phase 8c — Docker Integration + End to End

### Goal
Package the frontend and backend into Docker services, add them to
`docker-compose.yml`, and verify the full flow end to end in a containerised
environment: open browser → edit a profile → start the simulator → watch live
stats update.

### Docker Integration

```yaml
# Additions to docker-compose.yml
services:
  simulator-ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    ports:
      - "8080:8080"    # UI → http://localhost:8080
    environment:
      - API_URL=http://localhost:8000
    depends_on:
      - simulator-api

  simulator-api:
    build: .
    command: ["uvicorn", "simulator.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
```

### Files to Add/Modify

| File | Change |
|------|--------|
| `Dockerfile.ui` | New — UI container (multi-stage: build → nginx) |
| `docker/docker-compose.yml` | Add simulator-ui and simulator-api services |

### End-to-End Test Checklist

1. `docker compose up -d` — all services start cleanly, no port conflicts
2. Open `http://localhost:8080` — Dashboard loads
3. Navigate to `/profiles` — existing profiles listed correctly
4. Edit a profile, change a distribution value, click Save — config file updated on disk
5. Navigate to `/run`, click Start — simulator starts, span counter increments on Dashboard
6. WebSocket stream updates live stats within 2 seconds
7. Click Stop — simulator stops, status returns to idle
8. Open Jaeger at `http://localhost:16686` — spans from the run are visible

### End State

`cd docker && docker compose up -d` brings up the full stack. Anyone can open
`http://localhost:8080`, build an agent profile using forms, set behavioral
signal probabilities with sliders, hit Start, and watch live cost and span
metrics update in real time — without touching a YAML file or a terminal.
