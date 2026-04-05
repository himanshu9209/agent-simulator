/**
 * Run controller — override duration/concurrency/profile, dry-run button,
 * start/stop, live log tail via WebSocket.
 */
import { useEffect, useRef, useState } from "react";
import { useRunStatus, useStartRun, useStopRun, openRunStream } from "@/api/run";
import { useProfiles } from "@/api/profiles";
import type { RunStartRequest } from "@/types";

export default function RunPage() {
  const { data: statusData } = useRunStatus();
  const { data: profilesData } = useProfiles();
  const startRun = useStartRun();
  const stopRun = useStopRun();

  const [overrides, setOverrides] = useState<RunStartRequest>({});
  const [logs, setLogs] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  const running = statusData?.status === "running";

  // WebSocket log mirror — stream status as log lines
  useEffect(() => {
    const ws = openRunStream((s) => {
      if (s.status === "running") {
        const line = `[${new Date().toLocaleTimeString()}] agents=${s.active_agents} sessions=${s.sessions_completed} errors=${s.sessions_error} cost=$${s.total_cost_usd.toFixed(4)}`;
        setLogs((prev) => [...prev.slice(-49), line]);
      }
    });
    return () => ws.close();
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const profiles = profilesData?.profiles ?? [];

  const handleStart = () => {
    const req: RunStartRequest = {};
    if (overrides.duration) req.duration = overrides.duration;
    if (overrides.concurrency) req.concurrency = overrides.concurrency;
    if (overrides.profile) req.profile = overrides.profile;
    startRun.mutate(req, {
      onSuccess: () => setLogs((p) => [...p, `[${new Date().toLocaleTimeString()}] Simulation started`]),
    });
  };

  const handleStop = () => {
    stopRun.mutate(undefined, {
      onSuccess: () => setLogs((p) => [...p, `[${new Date().toLocaleTimeString()}] Stop signal sent`]),
    });
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-bold text-white">Run Controller</h1>

      {/* Current status */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-xs text-gray-500 mb-1">Status</p>
          <span
            className={`font-semibold ${
              running ? "text-green-400" : "text-gray-400"
            }`}
          >
            {statusData?.status ?? "—"}
          </span>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Active agents</p>
          <span className="text-white font-semibold">{statusData?.active_agents ?? 0}</span>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Sessions done</p>
          <span className="text-white font-semibold">
            {(statusData?.sessions_completed ?? 0).toLocaleString()}
          </span>
        </div>
      </div>

      {/* Overrides */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-300">Run Overrides (optional)</h2>
        <div className="grid grid-cols-3 gap-4">
          <label className="block">
            <span className="label-text">Duration (s)</span>
            <input
              type="number"
              min={1}
              value={overrides.duration ?? ""}
              onChange={(e) =>
                setOverrides((o) => ({
                  ...o,
                  duration: e.target.value ? parseInt(e.target.value, 10) : undefined,
                }))
              }
              className="input mt-1"
              placeholder="default"
            />
          </label>
          <label className="block">
            <span className="label-text">Concurrency</span>
            <input
              type="number"
              min={1}
              value={overrides.concurrency ?? ""}
              onChange={(e) =>
                setOverrides((o) => ({
                  ...o,
                  concurrency: e.target.value ? parseInt(e.target.value, 10) : undefined,
                }))
              }
              className="input mt-1"
              placeholder="default"
            />
          </label>
          <label className="block">
            <span className="label-text">Single Profile</span>
            <select
              value={overrides.profile ?? ""}
              onChange={(e) =>
                setOverrides((o) => ({
                  ...o,
                  profile: e.target.value || undefined,
                }))
              }
              className="input mt-1"
            >
              <option value="">All profiles</option>
              {profiles.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {/* Controls */}
      <div className="flex gap-3">
        {running ? (
          <button
            onClick={handleStop}
            disabled={stopRun.isPending}
            className="btn-danger disabled:opacity-50"
          >
            {stopRun.isPending ? "Stopping…" : "Stop Simulation"}
          </button>
        ) : (
          <button
            onClick={handleStart}
            disabled={startRun.isPending || statusData?.status === "stopping"}
            className="btn-primary disabled:opacity-50"
          >
            {startRun.isPending ? "Starting…" : "Start Simulation"}
          </button>
        )}
      </div>

      {startRun.isError && (
        <p className="text-red-400 text-sm">{String(startRun.error)}</p>
      )}

      {/* Log tail */}
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-4 h-60 overflow-y-auto font-mono text-xs text-gray-400">
        {logs.length === 0 && (
          <span className="text-gray-600">Log output will appear here once a run starts…</span>
        )}
        {logs.map((line, i) => (
          <div key={i}>{line}</div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
