/**
 * CodeMirror 6 YAML editor wrapper.
 * Props:
 *   value       – controlled YAML string
 *   onChange    – called on every keystroke
 *   readOnly    – disable editing (for YAML preview)
 *   minHeight   – CSS min-height (default "300px")
 */
import { useEffect, useRef } from "react";
import { EditorView, basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { yaml } from "@codemirror/lang-yaml";
import { oneDark } from "@codemirror/theme-one-dark";

interface Props {
  value: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  minHeight?: string;
}

export default function YamlEditor({
  value,
  onChange,
  readOnly = false,
  minHeight = "300px",
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  // Track external value changes without re-creating the view
  const valueRef = useRef(value);

  useEffect(() => {
    if (!containerRef.current) return;

    const extensions = [
      basicSetup,
      yaml(),
      oneDark,
      EditorView.theme({
        "&": { minHeight, fontSize: "13px" },
        ".cm-scroller": { fontFamily: "'Fira Code', 'Cascadia Code', monospace" },
      }),
    ];

    if (readOnly) {
      extensions.push(EditorState.readOnly.of(true));
    } else if (onChange) {
      extensions.push(
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const next = update.state.doc.toString();
            valueRef.current = next;
            onChange(next);
          }
        }),
      );
    }

    const view = new EditorView({
      state: EditorState.create({ doc: value, extensions }),
      parent: containerRef.current,
    });
    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // Only run on mount/unmount — external value sync below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readOnly, minHeight]);

  // Sync external value changes (e.g. reset button)
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    if (value === valueRef.current) return; // avoid loop from own edits
    valueRef.current = value;
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: value },
    });
  }, [value]);

  return <div ref={containerRef} className="rounded-md overflow-hidden border border-gray-700" />;
}
