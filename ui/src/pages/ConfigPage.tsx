/**
 * Full YAML editor for default.yaml via CodeMirror.
 * Validates before saving; shows error panel on failure.
 */
import { useEffect, useState } from "react";
import { useConfig, useSaveConfig, useValidateConfig } from "@/api/config";
import YamlEditor from "@/components/YamlEditor/YamlEditor";

export default function ConfigPage() {
  const { data, isLoading, error: loadError } = useConfig();
  const saveConfig = useSaveConfig();
  const validateConfig = useValidateConfig();

  const [yaml, setYaml] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  // Initialise editor when data loads
  useEffect(() => {
    if (data) setYaml(data.yaml_str);
  }, [data]);

  const handleValidate = async () => {
    const result = await validateConfig.mutateAsync(yaml);
    setValidationErrors(result.errors);
    return result.valid;
  };

  const handleSave = async () => {
    const valid = await handleValidate();
    if (!valid) return;
    await saveConfig.mutateAsync(yaml);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleReset = () => {
    if (data) {
      setYaml(data.yaml_str);
      setValidationErrors([]);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([yaml], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "default.yaml";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) return <div className="text-gray-400">Loading config…</div>;
  if (loadError)
    return (
      <div className="text-red-400">
        Failed to load config: {String(loadError)}
      </div>
    );

  const isBusy = validateConfig.isPending || saveConfig.isPending;

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Config Editor</h1>
          <p className="text-sm text-gray-500">{data?.path}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleDownload} className="btn-secondary text-sm">
            Download
          </button>
          <button
            onClick={handleReset}
            disabled={isBusy}
            className="btn-secondary text-sm disabled:opacity-50"
          >
            Reset
          </button>
          <button
            onClick={handleValidate}
            disabled={isBusy}
            className="btn-secondary text-sm disabled:opacity-50"
          >
            {validateConfig.isPending ? "Checking…" : "Validate"}
          </button>
          <button
            onClick={handleSave}
            disabled={isBusy}
            className="btn-primary text-sm disabled:opacity-50"
          >
            {saveConfig.isPending ? "Saving…" : saved ? "Saved ✓" : "Save"}
          </button>
        </div>
      </div>

      <YamlEditor value={yaml} onChange={setYaml} minHeight="500px" />

      {validationErrors.length > 0 && (
        <div className="bg-red-950 border border-red-800 rounded-lg p-4 space-y-1">
          <p className="text-xs font-semibold text-red-300 uppercase tracking-wider mb-2">
            Validation errors
          </p>
          {validationErrors.map((e, i) => (
            <p key={i} className="text-sm text-red-300 font-mono">
              {e}
            </p>
          ))}
        </div>
      )}

      {validateConfig.isSuccess && validationErrors.length === 0 && (
        <div className="bg-green-950 border border-green-800 rounded-lg p-3 text-sm text-green-300">
          Config is valid.
        </div>
      )}

      {saveConfig.isError && (
        <div className="bg-red-950 border border-red-800 rounded-lg p-3 text-sm text-red-300">
          Save failed: {String(saveConfig.error)}
        </div>
      )}
    </div>
  );
}
