/**
 * Dashboard — live run stats via WebSocket with Recharts mini-charts.
 * Falls back to polling /api/run/status if WS is unavailable.
 */
import { useEffect, useRef, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { openRunStream, useStartRun, useStopRun } from "@/api/run";
import type { RunStatusResponse } from "@/types";

interface HistoryPoint {
  t: number;
  sessions: number;
  errors: number;
  cost: number;
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

function MiniChart({
  data,
  dataKey,
  color,
  label,
}: {
  data: HistoryPoint[];
  dataKey: keyof HistoryPoint;
  color: string;
  label: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 mb-2">{label}</p>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="t" hide />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                background: "#1f2937",
                border: "none",
                fontSize: 11,
              }}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              dot={false}
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [status, setStatus] = useState<RunStatusResponse | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const startRun = useStartRun();
  const stopRun = useStopRun();

  useEffect(() => {
    const ws = openRunStream(
      (s) => {
        setStatus(s);
        setHistory((prev) => {
          const next = [
            ...prev,
            {
              t: prev.length,
              sessions: s.sessions_completed,
              errors: s.sessions_error,
              cost: parseFloat(s.total_cost_usd.toFixed(4)),
            },
          ].slice(-60); // keep last 60 seconds
          return next;
        });
      },
    );
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  const running = status?.status === "running";
  const elapsed = status?.elapsed_seconds ?? 0;
  const hh = Math.floor(elapsed / 3600).toString().padStart(2, "0");
  const mm = Math.floor((elapsed % 3600) / 60).toString().padStart(2, "0");
  const ss = Math.floor(elapsed % 60).toString().padStart(2, "0");

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-500">Live simulation telemetry</p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-full ${
              running
                ? "bg-green-900 text-green-300"
                : status?.status === "stopping"
                ? "bg-yellow-900 text-yellow-300"
                : "bg-gray-800 text-gray-400"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                running ? "bg-green-400 animate-pulse" : "bg-gray-500"
              }`}
            />
            {status?.status ?? "connecting…"}
          </span>
          {running ? (
            <button
              onClick={() => stopRun.mutate()}
              disabled={stopRun.isPending}
              className="btn-danger disabled:opacity-50"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={() => startRun.mutate({})}
              disabled={startRun.isPending || status?.status === "stopping"}
              className="btn-primary disabled:opacity-50"
            >
              Start
            </button>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active Agents"
          value={String(status?.active_agents ?? 0)}
        />
        <StatCard
          label="Sessions"
          value={(status?.sessions_completed ?? 0).toLocaleString()}
          sub={`${status?.sessions_error ?? 0} errors`}
        />
        <StatCard
          label="Elapsed"
          value={`${hh}:${mm}:${ss}`}
        />
        <StatCard
          label="Total Cost"
          value={`$${(status?.total_cost_usd ?? 0).toFixed(4)}`}
          sub={`${(status?.total_input_tokens ?? 0).toLocaleString()} in / ${(status?.total_output_tokens ?? 0).toLocaleString()} out tokens`}
        />
      </div>

      {/* Mini charts */}
      {history.length > 1 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MiniChart data={history} dataKey="sessions" color="#3b82f6" label="Sessions completed" />
          <MiniChart data={history} dataKey="errors"   color="#ef4444" label="Session errors" />
          <MiniChart data={history} dataKey="cost"     color="#22c55e" label="Total cost ($)" />
        </div>
      )}

      {status?.error && (
        <div className="bg-red-950 border border-red-800 rounded-lg p-4 text-sm text-red-300">
          {status.error}
        </div>
      )}

      {/* External links */}
      <div className="flex gap-4 pt-2">
        {[
          { href: "http://localhost:16686", label: "Jaeger" },
          { href: "http://localhost:3000",  label: "Grafana" },
          { href: "http://localhost:9090",  label: "Prometheus" },
        ].map(({ href, label }) => (
          <a
            key={href}
            href={href}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-blue-400 hover:underline"
          >
            ↗ {label}
          </a>
        ))}
      </div>
    </div>
  );
}
