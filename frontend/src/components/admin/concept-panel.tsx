"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { AdminConceptSpec, AdminPracticeTask } from "@/lib/types";

function asLines(values: string[]) {
  return values.join("\n");
}

function fromLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function misconceptionText(item: string | Record<string, unknown>) {
  if (typeof item === "string") return item;
  return String(item.description ?? item.id ?? "");
}

export function ConceptPanel({
  concept,
  language,
  projectTitle,
  slug,
  onChange,
  onDelete,
}: {
  concept: AdminConceptSpec;
  language: string;
  projectTitle: string;
  slug: string;
  onChange: (next: AdminConceptSpec) => void;
  onDelete: () => void;
}) {
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function regenerate() {
    setBusy(true);
    setError(null);
    try {
      const { api } = await import("@/lib/api");
      const next = await api.generateAdminConcept({
        concept,
        language,
        project_title: projectTitle,
        slug,
      });
      onChange({ ...concept, ...next, id: concept.id, title: next.title || concept.title });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not regenerate");
    } finally {
      setBusy(false);
    }
  }

  function updateTask(index: number, patch: Partial<AdminPracticeTask>) {
    const tasks = [...(concept.practice_tasks || [])];
    tasks[index] = { ...tasks[index], ...patch };
    onChange({ ...concept, practice_tasks: tasks });
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-stone-500">Concept</p>
          <h2 className="font-serif text-xl text-stone-50">{concept.title}</h2>
        </div>
        <Button variant="ghost" onClick={onDelete}>
          Remove
        </Button>
      </div>

      <label className="mt-4 block text-xs text-stone-400">
        Id
        <input
          className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 font-mono text-sm text-stone-100"
          value={concept.id}
          onChange={(event) => onChange({ ...concept, id: event.target.value })}
        />
      </label>
      <label className="mt-3 block text-xs text-stone-400">
        Title
        <input
          className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-100"
          value={concept.title}
          onChange={(event) => onChange({ ...concept, title: event.target.value })}
        />
      </label>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="block text-xs text-stone-400">
          Category
          <input
            className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-100"
            value={concept.category}
            onChange={(event) => onChange({ ...concept, category: event.target.value })}
          />
        </label>
        <div className="flex items-end">
          <Button className="w-full" variant="secondary" disabled={busy} onClick={regenerate}>
            {busy ? "Regenerating…" : "Regenerate"}
          </Button>
        </div>
      </div>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      <label className="mt-3 block text-xs text-stone-400">
        Description
        <textarea
          className="mt-1 min-h-24 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-100"
          value={concept.description}
          onChange={(event) => onChange({ ...concept, description: event.target.value })}
        />
      </label>
      <label className="mt-3 block text-xs text-stone-400">
        Learning objectives (one per line)
        <textarea
          className="mt-1 min-h-20 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-100"
          value={asLines(concept.learning_objectives || [])}
          onChange={(event) =>
            onChange({ ...concept, learning_objectives: fromLines(event.target.value) })
          }
        />
      </label>
      <label className="mt-3 block text-xs text-stone-400">
        Hints (5 levels)
        <textarea
          className="mt-1 min-h-28 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-100"
          value={asLines(concept.hints || [])}
          onChange={(event) => onChange({ ...concept, hints: fromLines(event.target.value) })}
        />
      </label>

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-stone-300">
        {(["explanation", "implementation", "testing", "research"] as const).map((key) => (
          <label key={key} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={Boolean(concept.mastery_requirements?.[key])}
              onChange={(event) =>
                onChange({
                  ...concept,
                  mastery_requirements: {
                    ...concept.mastery_requirements,
                    [key]: event.target.checked,
                  },
                })
              }
            />
            {key}
          </label>
        ))}
      </div>

      <button
        type="button"
        className="mt-4 text-left text-xs text-amber-500 hover:text-amber-400"
        onClick={() => setAdvanced((value) => !value)}
      >
        {advanced ? "Hide" : "Show"} questions, misconceptions, practice
      </button>

      {advanced && (
        <div className="mt-3 space-y-3">
          <label className="block text-xs text-stone-400">
            Diagnostic questions
            <textarea
              className="mt-1 min-h-16 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
              value={asLines(concept.diagnostic_questions || [])}
              onChange={(event) =>
                onChange({ ...concept, diagnostic_questions: fromLines(event.target.value) })
              }
            />
          </label>
          <label className="block text-xs text-stone-400">
            Research questions
            <textarea
              className="mt-1 min-h-16 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
              value={asLines(concept.research_questions || [])}
              onChange={(event) =>
                onChange({ ...concept, research_questions: fromLines(event.target.value) })
              }
            />
          </label>
          <label className="block text-xs text-stone-400">
            Misconceptions (one description per line)
            <textarea
              className="mt-1 min-h-16 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-sm"
              value={asLines((concept.misconceptions || []).map(misconceptionText))}
              onChange={(event) =>
                onChange({
                  ...concept,
                  misconceptions: fromLines(event.target.value).map((description, index) => ({
                    id: `${concept.id}-m${index + 1}`,
                    description,
                    signals: [],
                    diagnostic_questions: [],
                    remediation: { type: "targeted_question", script: description },
                  })),
                })
              }
            />
          </label>
          <div>
            <p className="text-xs text-stone-400">Practice tasks</p>
            {(concept.practice_tasks || []).map((task, index) => (
              <div key={index} className="mt-2 rounded-lg border border-stone-800 p-2">
                <input
                  className="mb-2 w-full rounded border border-stone-700 bg-stone-900 px-2 py-1 text-xs"
                  placeholder="filename"
                  value={task.filename || ""}
                  onChange={(event) => updateTask(index, { filename: event.target.value })}
                />
                <textarea
                  className="w-full rounded border border-stone-700 bg-stone-900 px-2 py-1 text-xs"
                  placeholder="prompt"
                  value={task.prompt || ""}
                  onChange={(event) => updateTask(index, { prompt: event.target.value })}
                />
              </div>
            ))}
            <Button
              variant="ghost"
              className="mt-2"
              onClick={() =>
                onChange({
                  ...concept,
                  practice_tasks: [
                    ...(concept.practice_tasks || []),
                    { id: `task-${(concept.practice_tasks || []).length + 1}`, filename: "", prompt: "" },
                  ],
                })
              }
            >
              Add task
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
