"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import type { MilestoneRead, ProjectDetail } from "@/lib/types";

interface ProjectBriefModalProps {
  open: boolean;
  onClose: () => void;
  project: ProjectDetail | null;
  loading?: boolean;
  currentMilestone?: MilestoneRead | null;
}

export function ProjectBriefModal({
  open,
  onClose,
  project,
  loading,
  currentMilestone,
}: ProjectBriefModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-brief-title"
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-stone-700 bg-stone-950 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-amber-600">
              Project brief
            </p>
            <h2
              id="project-brief-title"
              className="mt-1 font-serif text-2xl text-stone-50"
            >
              {loading ? "Loading…" : project?.title ?? "Project"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-stone-500 hover:bg-stone-800 hover:text-stone-200"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {project && (
          <div className="mt-5 space-y-4 text-sm text-stone-300">
            {project.difficulty && (
              <p className="text-xs uppercase tracking-wide text-stone-500">
                {project.difficulty}
              </p>
            )}
            {project.description && (
              <p className="text-stone-400">{project.description}</p>
            )}
            {project.objective && (
              <section>
                <h3 className="text-xs font-medium uppercase tracking-wide text-stone-500">
                  Objective
                </h3>
                <p className="mt-1">{project.objective}</p>
              </section>
            )}
            {project.expected_outcome && (
              <section>
                <h3 className="text-xs font-medium uppercase tracking-wide text-stone-500">
                  Expected outcome
                </h3>
                <p className="mt-1">{project.expected_outcome}</p>
              </section>
            )}
            {project.constraints?.length > 0 && (
              <section>
                <h3 className="text-xs font-medium uppercase tracking-wide text-stone-500">
                  Constraints
                </h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-stone-400">
                  {project.constraints.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </section>
            )}
            {project.skills?.length > 0 && (
              <section>
                <h3 className="text-xs font-medium uppercase tracking-wide text-stone-500">
                  Skills
                </h3>
                <p className="mt-1 text-stone-400">{project.skills.join(" · ")}</p>
              </section>
            )}
            {currentMilestone && (
              <section className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-3">
                <h3 className="text-xs font-medium uppercase tracking-wide text-amber-500">
                  Current milestone
                </h3>
                <p className="mt-1 font-medium text-stone-100">
                  {currentMilestone.title}
                </p>
                <p className="mt-1 text-xs text-stone-400">
                  Success: {currentMilestone.success_criteria}
                </p>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
