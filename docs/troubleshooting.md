# Troubleshooting

---

## Docker Desktop not running

**Symptom:** `docker compose` fails with "Cannot connect to the Docker daemon"

**Fix:** Start Docker Desktop. On Windows, look for the whale icon in the
system tray. If it's not there, launch Docker Desktop from the Start menu.

On Windows, the first startup after a reboot can take 30–60 seconds.
Run `docker info` to confirm Docker is ready before running compose.

---

## No spans appearing in Jaeger

**Symptom:** Simulator appears to run (progress line prints) but Jaeger shows
no traces under service "agent-simulator".

**Checks:**

1. Is the OTel Collector running?
   ```bash
   docker compose -f docker-compose.full.yml ps
   ```
   All services should be `running`.

2. Is the collector accepting connections?
   ```bash
   # Should return something (empty response is OK, connection refused is not)
   curl -s http://localhost:4317
   ```

3. Check collector logs for errors:
   ```bash
   docker logs agent-sim-otel-collector
   ```
   Look for lines like `"msg":"Exporting failed"`.

4. Is the simulator sending to the right endpoint?
   ```bash
   agent-simulator --dry-run
   ```
   Confirm `OTel endpoint` matches `http://localhost:4317`.

---

## Cost dashboard showing no data

**Symptom:** Grafana cost panels are empty or show zero.

**Cause:** Either `pricing` is missing from the config, or the model name
in `agent_profiles[x].llm_model` doesn't match any key in `pricing`.

**Fix:**
```yaml
# In your YAML, both of these must match exactly:
agent_profiles:
  my_agent:
    llm_model: "gpt-4o"          # ← must match a pricing key

pricing:
  gpt-4o:                        # ← must match llm_model
    input_per_million: 2.50
    output_per_million: 10.00
```

Run with `--dry-run` to confirm pricing models are detected.

---

## Behavioral signals never triggering

**Symptom:** The Behavioral Signals dashboard shows zeros even after a long run.

**Checks:**

1. Are behavioral signals declared in the profile config?
   ```bash
   agent-simulator --dry-run
   ```
   Look for `behavioral_signals=N` next to the profile name.
   If it shows `behavioral_signals=0`, add a `behavioral_signals:` block
   to the profile. See [profiles.md](profiles.md).

2. Are the probabilities large enough to be visible?
   With `concurrency=200` and `run_duration_seconds=600` at `clock_multiplier=5`,
   you'll get ~5,000–15,000 sessions. A probability of `0.01` (1%) should fire
   50–150 times. A probability of `0.001` may not fire at all in a short run.

3. Check the span attributes directly in Jaeger:
   Open a `agent.session` trace and look for `session.goal_drift_detected`.

---

## OTel Collector connection refused

**Symptom:** Simulator crashes immediately with a gRPC connection error.

```
StatusCode.UNAVAILABLE ... Connection refused
```

**Fix:** Start the observability stack first:
```bash
docker compose -f docker-compose.full.yml up -d
# Wait ~10 seconds
agent-simulator
```

The simulator will still emit spans even if the collector is temporarily
unavailable (the batch processor retries), but a hard refusal at startup
means the collector is not running at all.

---

## Windows WSL2 setup issues

**Symptom:** Docker commands work but `localhost:4317` is unreachable from
the simulator running on Windows (not inside WSL2).

**Cause:** WSL2 has a different network namespace from Windows. Ports exposed
by Docker Desktop are accessible from Windows as `localhost`.
Running the simulator inside WSL2 requires the correct WSL2-to-host address.

**Fix (run simulator from Windows PowerShell / cmd, not inside WSL2):**
```powershell
pip install agent-simulator
agent-simulator
```

**If you must run inside WSL2:**
```bash
# Find the Windows host IP from WSL2
WINDOWS_HOST=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')

# Override the endpoint
# Edit config/default.yaml:
# telemetry:
#   exporter_endpoint: "http://<WINDOWS_HOST>:4317"
```

---

## `ValidationError` on startup

**Symptom:** Simulator exits with a Pydantic validation error.

The error message will now look like:

```
❌ Config error in config/default.yaml:

   agent_profiles → rag_researcher → failure_rate: Input should be less than or equal to 1
   Value given: 1.5

💡 Check config/default.yaml for reference.
```

Fix the indicated field in your YAML and re-run `--dry-run` to verify.

---

## Grafana shows "No data" on all panels

**Symptom:** Grafana loads but all panels say "No data".

**Checks:**

1. Is Prometheus scraping the collector?
   Open http://localhost:9090/targets and confirm `agent-sim-otel-collector`
   is `UP`.

2. Has the simulator run for at least 10 seconds?
   Metrics are exported on a 5-second interval by default.

3. Check the Grafana data source:
   Go to **Configuration → Data Sources → Prometheus**.
   The URL should be `http://prometheus:9090`.
   Click **Save & Test** — it should say "Data source is working".
