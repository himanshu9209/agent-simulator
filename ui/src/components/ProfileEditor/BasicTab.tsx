import { usePricing } from "@/api/pricing";
import type { AgentProfile } from "@/types";

interface Props {
  profile: AgentProfile;
  onChange: (patch: Partial<AgentProfile>) => void;
}

export default function BasicTab({ profile, onChange }: Props) {
  const { data: pricingData } = usePricing();
  const models = Object.keys(pricingData?.pricing ?? {});

  const handleToolsChange = (raw: string) => {
    const tools = raw
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    onChange({ tools });
  };

  return (
    <div className="space-y-5 max-w-lg">
      {/* LLM model */}
      <label className="block">
        <span className="label-text">LLM Model</span>
        <select
          value={profile.llm_model}
          onChange={(e) => onChange({ llm_model: e.target.value })}
          className="input mt-1"
        >
          {models.length === 0 && (
            <option value={profile.llm_model}>{profile.llm_model}</option>
          )}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>

      {/* Mix weight */}
      <label className="block">
        <span className="label-text">
          Mix Weight — {(profile.mix_weight * 100).toFixed(0)}%
        </span>
        <input
          type="range"
          min={0}
          max={10}
          step={0.1}
          value={profile.mix_weight}
          onChange={(e) => onChange({ mix_weight: parseFloat(e.target.value) })}
          className="w-full mt-1 accent-blue-500"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0</span>
          <span>5</span>
          <span>10</span>
        </div>
      </label>

      {/* Failure rate */}
      <label className="block">
        <span className="label-text">
          Failure Rate — {(profile.failure_rate * 100).toFixed(0)}%
        </span>
        <input
          type="range"
          min={0}
          max={0.5}
          step={0.01}
          value={profile.failure_rate}
          onChange={(e) => onChange({ failure_rate: parseFloat(e.target.value) })}
          className="w-full mt-1 accent-blue-500"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0%</span>
          <span>25%</span>
          <span>50%</span>
        </div>
      </label>

      {/* Tools */}
      <label className="block">
        <span className="label-text">Tools (comma-separated)</span>
        <input
          type="text"
          value={profile.tools.join(", ")}
          onChange={(e) => handleToolsChange(e.target.value)}
          placeholder="search, calculator, code_runner"
          className="input mt-1"
        />
      </label>
    </div>
  );
}
