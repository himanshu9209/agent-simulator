import { useState } from "react";
import type { AgentProfile, AttributeConfig, AttributeType, SpanAttributeSchema } from "@/types";

interface Props {
  profile: AgentProfile;
  onChange: (patch: Partial<AgentProfile>) => void;
}

type SpanType = "session" | "tool" | "inference";

const SPAN_TYPES: SpanType[] = ["session", "tool", "inference"];
const ATTR_TYPES: AttributeType[] = ["float", "int", "enum", "boolean"];

function blankAttr(): AttributeConfig {
  return { type: "float", min: 0, max: 1 };
}

function AttrRow({
  name,
  config,
  onChangeName,
  onChangeConfig,
  onDelete,
}: {
  name: string;
  config: AttributeConfig;
  onChangeName: (n: string) => void;
  onChangeConfig: (c: AttributeConfig) => void;
  onDelete: () => void;
}) {
  return (
    <tr className="border-b border-gray-800 text-sm">
      <td className="py-2 pr-2">
        <input
          type="text"
          value={name}
          onChange={(e) => onChangeName(e.target.value)}
          className="input text-xs"
          placeholder="agent.session.env"
        />
      </td>
      <td className="py-2 pr-2">
        <select
          value={config.type}
          onChange={(e) =>
            onChangeConfig({ ...blankAttr(), type: e.target.value as AttributeType })
          }
          className="input text-xs"
        >
          {ATTR_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </td>
      <td className="py-2 pr-2 space-x-1">
        {(config.type === "float" || config.type === "int") && (
          <>
            <input
              type="number"
              value={config.min ?? ""}
              onChange={(e) =>
                onChangeConfig({ ...config, min: parseFloat(e.target.value) || 0 })
              }
              placeholder="min"
              className="input text-xs w-20 inline-block"
            />
            <input
              type="number"
              value={config.max ?? ""}
              onChange={(e) =>
                onChangeConfig({ ...config, max: parseFloat(e.target.value) || 0 })
              }
              placeholder="max"
              className="input text-xs w-20 inline-block"
            />
          </>
        )}
        {config.type === "enum" && (
          <input
            type="text"
            value={config.values?.join(", ") ?? ""}
            onChange={(e) =>
              onChangeConfig({
                ...config,
                values: e.target.value.split(",").map((v) => v.trim()),
              })
            }
            placeholder="val1, val2"
            className="input text-xs"
          />
        )}
        {config.type === "boolean" && (
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={config.probability ?? 0.5}
            onChange={(e) =>
              onChangeConfig({ ...config, probability: parseFloat(e.target.value) })
            }
            placeholder="probability"
            className="input text-xs w-28 inline-block"
          />
        )}
      </td>
      <td className="py-2">
        <button
          onClick={onDelete}
          className="text-red-400 hover:text-red-300 text-xs px-2"
        >
          ✕
        </button>
      </td>
    </tr>
  );
}

export default function ObservabilityTab({ profile, onChange }: Props) {
  const [active, setActive] = useState<SpanType>("session");

  const attrs = profile.observability_attributes;

  const updateSpan = (
    span: SpanType,
    updated: Record<string, AttributeConfig>,
  ) => {
    onChange({
      observability_attributes: { ...attrs, [span]: updated },
    });
  };

  const addRow = () => {
    const key = `new_attr_${Date.now()}`;
    updateSpan(active, { ...attrs[active], [key]: blankAttr() });
  };

  const renameKey = (oldKey: string, newKey: string) => {
    const entries = Object.entries(attrs[active]);
    const idx = entries.findIndex(([k]) => k === oldKey);
    if (idx === -1) return;
    entries[idx] = [newKey, entries[idx][1]];
    updateSpan(active, Object.fromEntries(entries));
  };

  const updateRow = (key: string, cfg: AttributeConfig) => {
    updateSpan(active, { ...attrs[active], [key]: cfg });
  };

  const deleteRow = (key: string) => {
    const next = { ...attrs[active] };
    delete next[key];
    updateSpan(active, next);
  };

  const rows = Object.entries(attrs[active]);

  return (
    <div className="space-y-4">
      {/* Span type tabs */}
      <div className="flex gap-1 border-b border-gray-800 pb-0">
        {SPAN_TYPES.map((s) => (
          <button
            key={s}
            onClick={() => setActive(s)}
            className={`px-4 py-1.5 text-sm rounded-t-md transition-colors ${
              active === s
                ? "bg-gray-800 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {s}{" "}
            <span className="text-xs text-gray-500">
              ({Object.keys(attrs[s]).length})
            </span>
          </button>
        ))}
      </div>

      {/* Table */}
      <table className="w-full">
        <thead>
          <tr className="text-xs text-gray-500 border-b border-gray-800">
            <th className="text-left pb-2 pr-2 w-1/3">Attribute Name</th>
            <th className="text-left pb-2 pr-2 w-24">Type</th>
            <th className="text-left pb-2 pr-2">Config</th>
            <th className="pb-2 w-8" />
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, cfg]) => (
            <AttrRow
              key={key}
              name={key}
              config={cfg}
              onChangeName={(n) => renameKey(key, n)}
              onChangeConfig={(c) => updateRow(key, c)}
              onDelete={() => deleteRow(key)}
            />
          ))}
        </tbody>
      </table>

      {rows.length === 0 && (
        <p className="text-sm text-gray-600 italic">No attributes yet.</p>
      )}

      <button onClick={addRow} className="btn-secondary text-sm">
        + Add Attribute
      </button>
    </div>
  );
}
