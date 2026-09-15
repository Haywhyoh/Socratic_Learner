"use client";

import { Check, Lock } from "lucide-react";
import clsx from "clsx";
import type { UserMilestoneRead } from "@/lib/types";
import {
  getActiveUserMilestone,
  milestonePhase,
  sortUserMilestones,
} from "@/lib/milestones";

interface MilestoneRailProps {
  userMilestones: UserMilestoneRead[];
  selectedId: number | null;
  onSelect: (um: UserMilestoneRead) => void;
}

export function MilestoneRail({
  userMilestones,
  selectedId,
  onSelect,
}: MilestoneRailProps) {
  const sorted = sortUserMilestones(userMilestones);
  const active = getActiveUserMilestone(userMilestones);

  return (
    <nav className="flex h-full flex-col border-r border-stone-800 bg-stone-950">
      <div className="border-b border-stone-800 px-4 py-4">
        <h2 className="font-serif text-lg text-stone-100">Milestones</h2>
        <p className="text-xs text-stone-500">Unlocked in order as you prove understanding.</p>
      </div>
      <ol className="flex-1 space-y-1 overflow-y-auto p-2">
        {sorted.map((um, index) => {
          const phase = milestonePhase(um, active?.id ?? null);
          const title = um.milestone?.title ?? `Milestone ${index + 1}`;
          const selectable = phase !== "locked";
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
                    {title}
                  </span>
                  {phase === "active" && (
                    <span className="text-xs text-amber-500/90">In progress</span>
                  )}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
