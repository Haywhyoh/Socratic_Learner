"use client";

import { Button } from "@/components/ui/button";
import { emptyMilestone } from "@/lib/admin-graph";
import type { AdminConceptSpec, AdminMilestoneSpec } from "@/lib/types";

export function MilestonePanel({
  milestones,
  concepts,
  selectedConceptId,
  onChange,
}: {
  milestones: AdminMilestoneSpec[];
  concepts: AdminConceptSpec[];
  selectedConceptId: string | null;
  onChange: (next: AdminMilestoneSpec[]) => void;
}) {
  function update(index: number, patch: Partial<AdminMilestoneSpec>) {
    onChange(milestones.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function toggleConcept(index: number, conceptId: string) {
    const current = milestones[index]?.concepts || [];
    const next = current.includes(conceptId)
      ? current.filter((id) => id !== conceptId)
      : [...current, conceptId];
    update(index, { concepts: next });
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-stone-500">Milestones</p>
          <h2 className="font-serif text-xl text-stone-50">Sequence</h2>
        </div>
        <Button variant="secondary" onClick={() => onChange([...milestones, emptyMilestone()])}>
          Add
        </Button>
      </div>
      <p className="mt-2 text-xs text-stone-500">
        Assign concepts to each milestone. Saving updates the catalog only. Use
        Apply to existing enrollments to add new work onto milestones students
        have not started.
      </p>
      <ul className="mt-4 space-y-3">
        {milestones.map((milestone, index) => (
          <li key={`${milestone.title}-${index}`} className="rounded-xl border border-stone-800 bg-stone-900/40 p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs text-stone-500">M{String(index + 1).padStart(2, "0")}</p>
              <button
                type="button"
                className="text-xs text-stone-500 hover:text-red-400"
                onClick={() => onChange(milestones.filter((_, i) => i !== index))}
              >
                Remove
              </button>
            </div>
            <input
              className="mt-1 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-sm text-stone-100"
              value={milestone.title}
              onChange={(event) => update(index, { title: event.target.value })}
            />
            <textarea
              className="mt-2 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-xs text-stone-200"
              placeholder="Description"
              value={milestone.description}
              onChange={(event) => update(index, { description: event.target.value })}
            />
            <textarea
              className="mt-2 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-xs text-stone-200"
              placeholder="Instructions"
              value={milestone.instructions}
              onChange={(event) => update(index, { instructions: event.target.value })}
            />
            <input
              className="mt-2 w-full rounded border border-stone-700 bg-stone-950 px-2 py-1 text-xs text-stone-200"
              placeholder="Success criteria"
              value={milestone.success_criteria}
              onChange={(event) => update(index, { success_criteria: event.target.value })}
            />
            <div className="mt-2 flex flex-wrap gap-1">
              {concepts.map((concept) => {
                const active = milestone.concepts.includes(concept.id);
                return (
                  <button
                    key={concept.id}
                    type="button"
                    onClick={() => toggleConcept(index, concept.id)}
                    className={`rounded-full px-2 py-0.5 text-[11px] ${
                      active
                        ? "bg-amber-500/20 text-amber-200"
                        : "bg-stone-800 text-stone-400 hover:text-stone-200"
                    }`}
                  >
                    {concept.title}
                  </button>
                );
              })}
            </div>
            {selectedConceptId && !milestone.concepts.includes(selectedConceptId) && (
              <button
                type="button"
                className="mt-2 text-xs text-amber-500"
                onClick={() => toggleConcept(index, selectedConceptId)}
              >
                Add selected concept
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
