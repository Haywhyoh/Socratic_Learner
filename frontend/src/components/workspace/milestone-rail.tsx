"use client";

import { Check, Lock } from "lucide-react";
import clsx from "clsx";
import type { GraphMilestoneRead, GraphRead, UserMilestoneRead } from "@/lib/types";
import {
  getActiveUserMilestone,
  milestonePhase,
  sortUserMilestones,
} from "@/lib/milestones";

interface MilestoneRailProps {
  userMilestones: UserMilestoneRead[];
  graph: GraphRead | null;
  selectedId: number | null;
  activeConceptId: string | null;
  onSelect: (um: UserMilestoneRead) => void;
  onSelectConcept: (conceptId: string) => void;
}

function statusDot(status: string): string {
  if (status === "mastered" || status === "verified") return "bg-emerald-400";
  if (status === "locked") return "bg-stone-600";
  if (status === "blocked" || status === "knowledge_gap" || status === "needs_review")
    return "bg-red-400";
  return "bg-amber-400";
}

export function MilestoneRail({
  userMilestones,
  graph,
  selectedId,
  activeConceptId,
  onSelect,
  onSelectConcept,
}: MilestoneRailProps) {
  const sorted = sortUserMilestones(userMilestones);
  const active = getActiveUserMilestone(userMilestones);
  const graphByUm = new Map(
    (graph?.milestones ?? []).map((m) => [m.user_milestone_id, m]),
  );

  return (
    <nav className="flex h-full min-h-0 flex-col overflow-hidden border-r border-stone-800 bg-stone-950">
      <div className="shrink-0 border-b border-stone-800 px-4 py-4">
        <h2 className="font-serif text-lg text-stone-100">Progress</h2>
        <p className="text-xs text-stone-500">
          Concepts unlock in order. Mastery needs evidence, not a click.
        </p>
      </div>
      <ol className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {sorted.map((um, index) => {
          const phase = milestonePhase(um, active?.id ?? null);
          const title = um.milestone?.title ?? `Milestone ${index + 1}`;
          const selectable = phase !== "locked";
          const expanded = selectedId === um.id && selectable;
          const gm: GraphMilestoneRead | undefined = graphByUm.get(um.id);
          return (
            <li key={um.id}>
              <button
                type="button"
                disabled={!selectable}
                onClick={() => selectable && onSelect(um)}
                className={clsx(
                  "flex w-full items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors",
                  selectedId === um.id && "bg-stone-800/80 ring-1 ring-amber-700/50",
                  selectable && selectedId !== um.id && "hover:bg-stone-900",
                  !selectable && "cursor-not-allowed opacity-50",
                )}
              >
                <span
                  className={clsx(
                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                    phase === "completed" && "bg-emerald-900/80 text-emerald-300",
                    phase === "active" && "bg-amber-500 text-stone-950",
                    phase === "locked" && "bg-stone-800 text-stone-500",
                  )}
                >
                  {phase === "completed" ? (
                    <Check className="h-4 w-4" />
                  ) : phase === "locked" ? (
                    <Lock className="h-3.5 w-3.5" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span>
                  <span className="block text-sm font-medium text-stone-200">
                    M{String(um.milestone?.order_index ?? index + 1).padStart(2, "0")}{" "}
                    {title}
                  </span>
                  {phase === "active" && (
                    <span className="text-xs text-amber-500/90">In progress</span>
                  )}
                </span>
              </button>

              {expanded && gm && gm.concepts.length > 0 && (
                <ol className="ml-5 mt-1 space-y-1 border-l border-stone-800 pl-3">
                  {gm.concepts.map((concept) => (
                    <li key={concept.id}>
                      <button
                        type="button"
                        onClick={() => onSelectConcept(concept.id)}
                        className={clsx(
                          "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs transition-colors",
                          activeConceptId === concept.id
                            ? "bg-amber-950/50 text-amber-100 ring-1 ring-amber-800/60"
                            : "text-stone-400 hover:bg-stone-900 hover:text-stone-200",
                        )}
                      >
                        <span
                          className={clsx(
                            "h-1.5 w-1.5 shrink-0 rounded-full",
                            statusDot(concept.status),
                          )}
                        />
                        <span className="min-w-0 flex-1 truncate">{concept.title}</span>
                        <span className="shrink-0 text-[10px] uppercase text-stone-600">
                          {concept.status}
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
