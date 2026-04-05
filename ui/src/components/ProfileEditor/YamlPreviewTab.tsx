/**
 * Shows a read-only CodeMirror YAML view of the current profile state.
 * Generates YAML client-side from the profile object (no API round-trip).
 */
import YamlEditor from "@/components/YamlEditor/YamlEditor";
import type { AgentProfile } from "@/types";

interface Props {
  name: string;
  profile: AgentProfile;
}

/** Minimal YAML serialiser — just enough for the preview. */
function toYaml(name: string, profile: AgentProfile): string {
  const j = JSON.parse(JSON.stringify(profile)) as Record<string, unknown>;
  // Use JSON→YAML via manual multi-line dump (keeps it dependency-free)
  return dumpValue({ [name]: j }, 0);
}

function dumpValue(value: unknown, indent: number): string {
  const pad = "  ".repeat(indent);
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return String(value);
  if (typeof value === "number") return String(value);
  if (typeof value === "string") {
    if (/[:#\[\]{},|>&*!'"@`]/.test(value) || value.includes("\n")) {
      return `"${value.replace(/"/g, '\\"')}"`;
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    return value
      .map((v) => `\n${pad}- ${dumpValue(v, indent + 1)}`)
      .join("");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).filter(
      ([, v]) => v !== undefined,
    );
    if (entries.length === 0) return "{}";
    return entries
      .map(([k, v]) => {
        const vStr = dumpValue(v, indent + 1);
        const inline =
          typeof v !== "object" || v === null || Array.isArray(v) && (v as unknown[]).length === 0;
        if (inline) return `\n${pad}${k}: ${vStr}`;
        return `\n${pad}${k}:${vStr}`;
      })
      .join("");
  }
  return String(value);
}

export default function YamlPreviewTab({ name, profile }: Props) {
  const yaml = toYaml(name, profile);

  const download = () => {
    const blob = new Blob([yaml], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copy = () => navigator.clipboard.writeText(yaml);

  return (
    <div className="space-y-3">
      <div className="flex gap-2 justify-end">
        <button onClick={copy} className="btn-secondary text-xs">
          Copy
        </button>
        <button onClick={download} className="btn-secondary text-xs">
          Download
        </button>
      </div>
      <YamlEditor value={yaml} readOnly minHeight="420px" />
    </div>
  );
}
