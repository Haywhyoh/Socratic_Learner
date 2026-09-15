"use client";

import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";

interface CodeEditorProps {
  path: string;
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
}

function languageForPath(path: string): string {
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".js")) return "javascript";
  return "plaintext";
}

export function CodeEditor({ path, value, onChange, onSave }: CodeEditorProps) {
  const handleMount = (ed: editor.IStandaloneCodeEditor) => {
    ed.addCommand(
      // Ctrl/Cmd + S
      2048 | 49,
      () => onSave?.(),
    );
  };

  return (
    <Editor
      height="100%"
      path={path}
      language={languageForPath(path)}
      value={value}
      theme="vs-dark"
      onChange={(v) => onChange(v ?? "")}
      onMount={handleMount}
      options={{
        fontSize: 14,
        fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        padding: { top: 12 },
        wordWrap: "on",
      }}
    />
  );
}
