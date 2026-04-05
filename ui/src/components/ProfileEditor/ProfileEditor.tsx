/**
 * Five-tab editor for a single AgentProfile.
 * Manages local draft state; calls onSave when user clicks Save.
 */
import { useState } from "react";
import type { AgentProfile } from "@/types";
import BasicTab from "./BasicTab";
import DistributionsTab from "./DistributionsTab";
import ObservabilityTab from "./ObservabilityTab";
import BehavioralTab from "./BehavioralTab";
import YamlPreviewTab from "./YamlPreviewTab";

interface Props {
  name: string;
  initialProfile: AgentProfile;
  onSave: (profile: AgentProfile) => void;
  saving?: boolean;
}

type TabId = "basic" | "distributions" | "observability" | "behavioral" | "yaml";

const TABS: { id: TabId; label: string }[] = [
  { id: "basic",         label: "Basic" },
  { id: "distributions", label: "Distributions" },
  { id: "observability", label: "Observability Attrs" },
  { id: "behavioral",    label: "Behavioral Signals" },
  { id: "yaml",          label: "YAML Preview" },
];

export default function ProfileEditor({
  name,
  initialProfile,
  onSave,
  saving,
}: Props) {
  const [tab, setTab] = useState<TabId>("basic");
  const [draft, setDraft] = useState<AgentProfile>(initialProfile);

  const patch = (p: Partial<AgentProfile>) =>
    setDraft((d) => ({ ...d, ...p }));

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-800">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm transition-colors rounded-t-md ${
              tab === t.id
                ? "bg-gray-800 text-white border-b-2 border-blue-500"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="pt-1">
        {tab === "basic"         && <BasicTab profile={draft} onChange={patch} />}
        {tab === "distributions" && <DistributionsTab profile={draft} onChange={patch} />}
        {tab === "observability" && <ObservabilityTab profile={draft} onChange={patch} />}
        {tab === "behavioral"    && <BehavioralTab profile={draft} onChange={patch} />}
        {tab === "yaml"          && <YamlPreviewTab name={name} profile={draft} />}
      </div>

      {/* Save bar */}
      {tab !== "yaml" && (
        <div className="flex justify-end pt-4 border-t border-gray-800">
          <button
            onClick={() => onSave(draft)}
            disabled={saving}
            className="btn-primary disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Profile"}
          </button>
        </div>
      )}
    </div>
  );
}
