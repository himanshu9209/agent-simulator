import type {
  AgentProfile,
  BehavioralSignalConfig,
  BehavioralSignalsSchema,
} from "@/types";

interface Props {
  profile: AgentProfile;
  onChange: (patch: Partial<AgentProfile>) => void;
}

type SignalKey =
  | "tool_selection_quality"
  | "goal_drift"
  | "model_switch"
  | "planning_quality"
  | "retry_reason"
  | "replanning_triggered"
  | "sandbox_escalation";

const SIGNAL_LABELS: Record<SignalKey, string> = {
  tool_selection_quality: "Tool Selection Quality",
  goal_drift: "Goal Drift",
  model_switch: "Model Switch",
  planning_quality: "Planning Quality",
  retry_reason: "Retry Reason",
  replanning_triggered: "Replanning Triggered",
  sandbox_escalation: "Sandbox Escalation",
};

const DEFAULT_SPAN: Record<SignalKey, string> = {
  tool_selection_quality: "tool",
  goal_drift: "session",
  model_switch: "inference",
  planning_quality: "planning",
  retry_reason: "inference",
  replanning_triggered: "session",
  sandbox_escalation: "inference",
};

function blank(key: SignalKey): BehavioralSignalConfig {
  return { type: "float", span: DEFAULT_SPAN[key], min: 0, max: 1, probability: 0.1 };
}

function patchSignals(
  existing: BehavioralSignalsSchema | undefined,
  patch: Partial<BehavioralSignalsSchema>,
): BehavioralSignalsSchema {
  return {
    tool_selection_quality: undefined,
    tool_sequence: undefined,
    goal_drift: undefined,
    model_switch: undefined,
    planning_quality: undefined,
    retry_reason: undefined,
    replanning_triggered: undefined,
    sandbox_escalation: undefined,
    extra: {},
    ...existing,
    ...patch,
  };
}

function SignalRow({
  label,
  value,
  onEnable,
  onDisable,
  onChange,
}: {
  label: string;
  value?: BehavioralSignalConfig;
  onEnable: () => void;
  onDisable: () => void;
  onChange: (v: BehavioralSignalConfig) => void;
}) {
  const enabled = !!value;
  return (
    <div className="border border-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-200">{label}</span>
        <button
          onClick={enabled ? onDisable : onEnable}
          className={`px-3 py-1 text-xs rounded-full transition-colors ${
            enabled
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:text-white"
          }`}
        >
          {enabled ? "Enabled" : "Disabled"}
        </button>
      </div>
      {enabled && value && (
        <div className="grid grid-cols-2 gap-3 pt-1">
          <label className="block">
            <span className="text-xs text-gray-500">Span type</span>
            <input
              type="text"
              value={value.span}
              onChange={(e) => onChange({ ...value, span: e.target.value })}
              className="input mt-0.5"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">Probability</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={value.probability ?? ""}
              onChange={(e) =>
                onChange({ ...value, probability: parseFloat(e.target.value) || 0 })
              }
              className="input mt-0.5"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">Mean</span>
            <input
              type="number"
              value={value.mean ?? ""}
              onChange={(e) =>
                onChange({ ...value, mean: parseFloat(e.target.value) || 0 })
              }
              className="input mt-0.5"
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-500">Std</span>
            <input
              type="number"
              min={0}
              value={value.std ?? ""}
              onChange={(e) =>
                onChange({ ...value, std: parseFloat(e.target.value) || 0 })
              }
              className="input mt-0.5"
            />
          </label>
          {label === "Model Switch" && (
            <label className="col-span-2 block">
              <span className="text-xs text-gray-500">Target Model</span>
              <input
                type="text"
                value={value.target_model ?? ""}
                onChange={(e) =>
                  onChange({ ...value, target_model: e.target.value })
                }
                placeholder="gpt-4o"
                className="input mt-0.5"
              />
            </label>
          )}
        </div>
      )}
    </div>
  );
}

export default function BehavioralTab({ profile, onChange }: Props) {
  const bs = profile.behavioral_signals;

  const update = (key: SignalKey, value?: BehavioralSignalConfig) => {
    onChange({ behavioral_signals: patchSignals(bs, { [key]: value }) });
  };

  return (
    <div className="space-y-3">
      {(Object.entries(SIGNAL_LABELS) as [SignalKey, string][]).map(
        ([key, label]) => (
          <SignalRow
            key={key}
            label={label}
            value={bs?.[key] ?? undefined}
            onEnable={() => update(key, blank(key))}
            onDisable={() => update(key, undefined)}
            onChange={(v) => update(key, v)}
          />
        ),
      )}
    </div>
  );
}
