import {
  AreaChart,
  Area,
  XAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { AgentProfile, GaussianDistribution, UniformIntDistribution } from "@/types";

interface Props {
  profile: AgentProfile;
  onChange: (patch: Partial<AgentProfile>) => void;
}

/** Build a simple bell-curve sample for preview */
function gaussianPreview(mean: number, std: number) {
  const points = [];
  for (let i = -3; i <= 3; i += 0.25) {
    const x = mean + i * std;
    const y =
      (1 / (std * Math.sqrt(2 * Math.PI))) *
      Math.exp(-0.5 * Math.pow(i, 2));
    points.push({ x: Math.round(x), y });
  }
  return points;
}

function GaussField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: GaussianDistribution;
  onChange: (v: GaussianDistribution) => void;
}) {
  const preview = gaussianPreview(value.mean, Math.max(value.std, 1));
  return (
    <div className="space-y-2">
      <p className="label-text">{label}</p>
      <div className="flex gap-4">
        <label className="flex-1">
          <span className="text-xs text-gray-500">Mean</span>
          <input
            type="number"
            value={value.mean}
            onChange={(e) =>
              onChange({ ...value, mean: parseFloat(e.target.value) || 0 })
            }
            className="input mt-0.5"
          />
        </label>
        <label className="flex-1">
          <span className="text-xs text-gray-500">Std Dev</span>
          <input
            type="number"
            min={1}
            value={value.std}
            onChange={(e) =>
              onChange({ ...value, std: parseFloat(e.target.value) || 1 })
            }
            className="input mt-0.5"
          />
        </label>
      </div>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={preview} margin={{ top: 4, bottom: 0, left: 0, right: 0 }}>
            <XAxis dataKey="x" tick={{ fontSize: 10, fill: "#6b7280" }} />
            <Tooltip
              formatter={(v: number) => v.toFixed(4)}
              contentStyle={{ background: "#1f2937", border: "none", fontSize: 11 }}
            />
            <Area
              type="monotone"
              dataKey="y"
              stroke="#3b82f6"
              fill="#1e3a5f"
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function UniformField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: UniformIntDistribution;
  onChange: (v: UniformIntDistribution) => void;
}) {
  const preview = Array.from(
    { length: value.max - value.min + 1 },
    (_, i) => ({ x: value.min + i, y: 1 }),
  );
  return (
    <div className="space-y-2">
      <p className="label-text">{label}</p>
      <div className="flex gap-4">
        <label className="flex-1">
          <span className="text-xs text-gray-500">Min</span>
          <input
            type="number"
            min={0}
            value={value.min}
            onChange={(e) =>
              onChange({ ...value, min: parseInt(e.target.value, 10) || 0 })
            }
            className="input mt-0.5"
          />
        </label>
        <label className="flex-1">
          <span className="text-xs text-gray-500">Max</span>
          <input
            type="number"
            min={value.min}
            value={value.max}
            onChange={(e) =>
              onChange({ ...value, max: parseInt(e.target.value, 10) || value.min })
            }
            className="input mt-0.5"
          />
        </label>
      </div>
      {preview.length <= 30 && (
        <div className="h-16">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={preview} margin={{ top: 4, bottom: 0, left: 0, right: 0 }}>
              <XAxis dataKey="x" tick={{ fontSize: 10, fill: "#6b7280" }} />
              <Area
                type="stepAfter"
                dataKey="y"
                stroke="#22c55e"
                fill="#14532d"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default function DistributionsTab({ profile, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <GaussField
        label="LLM Input Tokens"
        value={profile.llm_input_tokens}
        onChange={(v) => onChange({ llm_input_tokens: v })}
      />
      <GaussField
        label="LLM Output Tokens"
        value={profile.llm_output_tokens}
        onChange={(v) => onChange({ llm_output_tokens: v })}
      />
      <GaussField
        label="Planning Latency (ms)"
        value={profile.planning_latency_ms}
        onChange={(v) => onChange({ planning_latency_ms: v })}
      />
      <UniformField
        label="Tool Call Count"
        value={profile.tool_call_count}
        onChange={(v) => onChange({ tool_call_count: v })}
      />
    </div>
  );
}
