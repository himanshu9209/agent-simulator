/**
 * Handles both /profiles/new and /profiles/:name.
 * Creates a blank profile for "new", loads the existing one for edit.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useProfile, useCreateProfile, useUpdateProfile } from "@/api/profiles";
import ProfileEditor from "@/components/ProfileEditor/ProfileEditor";
import type { AgentProfile } from "@/types";

const BLANK_PROFILE: AgentProfile = {
  tools: [],
  llm_model: "gpt-4o",
  llm_input_tokens: { mean: 1000, std: 200 },
  llm_output_tokens: { mean: 400,  std: 100 },
  planning_latency_ms: { mean: 500, std: 100 },
  tool_call_count: { min: 1, max: 5 },
  failure_rate: 0.05,
  mix_weight: 1.0,
  observability_attributes: { session: {}, tool: {}, inference: {} },
};

// ─── New profile wizard ──────────────────────────────────────────────────────

function NewProfilePage() {
  const navigate = useNavigate();
  const create = useCreateProfile();
  const [name, setName] = useState("");
  const [step, setStep] = useState<"name" | "edit">("name");

  if (step === "name") {
    return (
      <div className="max-w-sm space-y-4">
        <h1 className="text-xl font-bold text-white">New Profile</h1>
        <label className="block">
          <span className="label-text">Profile name</span>
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) setStep("edit");
            }}
            className="input mt-1"
            placeholder="my_agent"
          />
        </label>
        <div className="flex gap-3">
          <button onClick={() => navigate("/profiles")} className="btn-secondary">
            Cancel
          </button>
          <button
            disabled={!name.trim()}
            onClick={() => setStep("edit")}
            className="btn-primary disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/profiles")}
          className="text-gray-400 hover:text-white text-sm"
        >
          ← Profiles
        </button>
        <h1 className="text-xl font-bold text-white">{name}</h1>
        <span className="text-xs text-gray-500">(new)</span>
      </div>

      <ProfileEditor
        name={name}
        initialProfile={BLANK_PROFILE}
        saving={create.isPending}
        onSave={(p) =>
          create.mutate(
            { name: name.trim(), profile: p },
            { onSuccess: () => navigate("/profiles") },
          )
        }
      />

      {create.isError && (
        <p className="text-red-400 text-sm">{String(create.error)}</p>
      )}
    </div>
  );
}

// ─── Edit existing profile ───────────────────────────────────────────────────

function EditProfilePage({ name }: { name: string }) {
  const navigate = useNavigate();
  const { data, isLoading, error } = useProfile(name);
  const update = useUpdateProfile(name);

  if (isLoading) return <div className="text-gray-400">Loading…</div>;
  if (error || !data)
    return <div className="text-red-400">Profile not found: {name}</div>;

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/profiles")}
          className="text-gray-400 hover:text-white text-sm"
        >
          ← Profiles
        </button>
        <h1 className="text-xl font-bold text-white">{name}</h1>
      </div>

      <ProfileEditor
        name={name}
        initialProfile={data.profile}
        saving={update.isPending}
        onSave={(p) =>
          update.mutate(p, { onSuccess: () => navigate("/profiles") })
        }
      />

      {update.isError && (
        <p className="text-red-400 text-sm">{String(update.error)}</p>
      )}
    </div>
  );
}

// ─── Route entry point ───────────────────────────────────────────────────────

export default function ProfileEditorPage() {
  const { name } = useParams<{ name: string }>();
  if (!name || name === "new") return <NewProfilePage />;
  return <EditProfilePage name={name} />;
}
