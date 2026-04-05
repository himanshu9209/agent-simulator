import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProfiles, useDeleteProfile } from "@/api/profiles";

export default function ProfilesPage() {
  const { data, isLoading, error } = useProfiles();
  const deleteProfile = useDeleteProfile();
  const navigate = useNavigate();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  if (isLoading) return <div className="text-gray-400">Loading…</div>;
  if (error)
    return (
      <div className="text-red-400">Failed to load profiles: {String(error)}</div>
    );

  const profiles = data?.profiles ?? [];

  const handleDelete = (name: string) => {
    deleteProfile.mutate(name, {
      onSuccess: () => setConfirmDelete(null),
    });
  };

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Agent Profiles</h1>
          <p className="text-sm text-gray-500">{profiles.length} profiles configured</p>
        </div>
        <button
          onClick={() => navigate("/profiles/new")}
          className="btn-primary"
        >
          + New Profile
        </button>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500">
              <th className="text-left px-5 py-3">Name</th>
              <th className="text-left px-4 py-3">Model</th>
              <th className="text-right px-4 py-3">Tools</th>
              <th className="text-right px-4 py-3">Attrs</th>
              <th className="text-right px-4 py-3">Signals</th>
              <th className="text-right px-4 py-3">Weight</th>
              <th className="text-right px-4 py-3">Fail %</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr
                key={p.name}
                className="border-b border-gray-800 last:border-0 hover:bg-gray-800/50 transition-colors"
              >
                <td className="px-5 py-3 font-medium text-white">{p.name}</td>
                <td className="px-4 py-3 text-gray-400 font-mono text-xs">{p.llm_model}</td>
                <td className="px-4 py-3 text-right text-gray-400">{p.tool_count}</td>
                <td className="px-4 py-3 text-right text-gray-400">{p.attribute_count}</td>
                <td className="px-4 py-3 text-right text-gray-400">{p.behavioral_signal_count}</td>
                <td className="px-4 py-3 text-right text-gray-400">{p.mix_weight.toFixed(1)}</td>
                <td className="px-4 py-3 text-right text-gray-400">
                  {(p.failure_rate * 100).toFixed(0)}%
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => navigate(`/profiles/${p.name}`)}
                      className="text-blue-400 hover:text-blue-300 text-xs"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setConfirmDelete(p.name)}
                      className="text-red-400 hover:text-red-300 text-xs"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {profiles.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-10">
            No profiles yet.{" "}
            <button
              onClick={() => navigate("/profiles/new")}
              className="text-blue-400 hover:underline"
            >
              Create one
            </button>
          </p>
        )}
      </div>

      {/* Delete confirm modal */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-80 space-y-4">
            <h2 className="font-semibold text-white">Delete "{confirmDelete}"?</h2>
            <p className="text-sm text-gray-400">This cannot be undone.</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmDelete(null)}
                className="btn-secondary text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDelete)}
                disabled={deleteProfile.isPending}
                className="btn-danger text-sm disabled:opacity-50"
              >
                {deleteProfile.isPending ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
