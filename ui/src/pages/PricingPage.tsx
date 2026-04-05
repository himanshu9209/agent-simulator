import { useState, useEffect } from "react";
import { usePricing, useUpdatePricing } from "@/api/pricing";
import type { ModelPricing } from "@/types";

export default function PricingPage() {
  const { data, isLoading, error } = usePricing();
  const updatePricing = useUpdatePricing();

  // Local draft as array for editable table
  const [rows, setRows] = useState<{ model: string; pricing: ModelPricing }[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setRows(
        Object.entries(data.pricing).map(([model, pricing]) => ({ model, pricing })),
      );
    }
  }, [data]);

  const updateRow = (i: number, patch: Partial<ModelPricing>) => {
    setRows((prev) =>
      prev.map((r, idx) =>
        idx === i ? { ...r, pricing: { ...r.pricing, ...patch } } : r,
      ),
    );
  };

  const updateModel = (i: number, model: string) => {
    setRows((prev) =>
      prev.map((r, idx) => (idx === i ? { ...r, model } : r)),
    );
  };

  const addRow = () => {
    setRows((prev) => [
      ...prev,
      {
        model: `new-model-${prev.length + 1}`,
        pricing: { input_per_million: 0, output_per_million: 0 },
      },
    ]);
  };

  const removeRow = (i: number) => {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  };

  const handleSave = () => {
    const pricing = Object.fromEntries(rows.map((r) => [r.model, r.pricing]));
    updatePricing.mutate(pricing, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2500);
      },
    });
  };

  if (isLoading) return <div className="text-gray-400">Loading pricing…</div>;
  if (error)
    return (
      <div className="text-red-400">Failed to load pricing: {String(error)}</div>
    );

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Model Pricing</h1>
          <p className="text-sm text-gray-500">
            Cost per 1M tokens — used for cost telemetry calculations
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={addRow} className="btn-secondary text-sm">
            + Add Model
          </button>
          <button
            onClick={handleSave}
            disabled={updatePricing.isPending}
            className="btn-primary text-sm disabled:opacity-50"
          >
            {updatePricing.isPending ? "Saving…" : saved ? "Saved ✓" : "Save"}
          </button>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500">
              <th className="text-left px-5 py-3">Model</th>
              <th className="text-right px-4 py-3">Input / 1M</th>
              <th className="text-right px-4 py-3">Output / 1M</th>
              <th className="text-right px-4 py-3">Cached Input</th>
              <th className="text-right px-4 py-3">Cache Write</th>
              <th className="text-right px-4 py-3">Cache Read</th>
              <th className="px-4 py-3 w-8" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-gray-800 last:border-0"
              >
                <td className="px-5 py-2">
                  <input
                    type="text"
                    value={row.model}
                    onChange={(e) => updateModel(i, e.target.value)}
                    className="input font-mono text-xs w-40"
                  />
                </td>
                {(
                  [
                    "input_per_million",
                    "output_per_million",
                    "cached_input_per_million",
                    "cache_write_per_million",
                    "cache_read_per_million",
                  ] as (keyof ModelPricing)[]
                ).map((field) => (
                  <td key={field} className="px-4 py-2 text-right">
                    <input
                      type="number"
                      min={0}
                      step={0.01}
                      value={row.pricing[field] ?? ""}
                      onChange={(e) =>
                        updateRow(i, {
                          [field]: e.target.value
                            ? parseFloat(e.target.value)
                            : undefined,
                        })
                      }
                      className="input text-right w-24"
                      placeholder="—"
                    />
                  </td>
                ))}
                <td className="px-4 py-2">
                  <button
                    onClick={() => removeRow(i)}
                    className="text-red-400 hover:text-red-300 text-xs"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {rows.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-10">No models yet.</p>
        )}
      </div>

      {updatePricing.isError && (
        <p className="text-red-400 text-sm">{String(updatePricing.error)}</p>
      )}
    </div>
  );
}
