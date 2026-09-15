"use client";

import { Check, Lock } from "lucide-react";
import clsx from "clsx";
import type { UserMilestoneRead } from "@/lib/types";
import {
  getActiveUserMilestone,
  milestonePhase,
  parseMilestoneTasks,
  sortUserMilestones,
  type MilestoneTask,
} from "@/lib/milestones";

interface MilestoneRailProps {
  userMilestones: UserMilestoneRead[];
  selectedId: number | null;
  activeTaskId: string | null;
  onSelect: (um: UserMilestoneRead) => void;
  onSelectTask: (task: MilestoneTask) => void;
}

export function MilestoneRail({
  userMilestones,
  selectedId,
  activeTaskId,
  onSelect,
  onSelectTask,
}: MilestoneRailProps) {
  const sorted = sortUserMilestones(userMilestones);
  const active = getActiveUserMilestone(userMilestones);

  return (
    <nav className="flex h-full min-h-0 flex-col overflow-hidden border-r border-stone-800 bg-stone-950">
      <div className="shrink-0 border-b border-stone-800 px-4 py-4">
        <h2 className="font-serif text-lg text-stone-100">Milestones</h2>
        <p className="text-xs text-stone-500">
          Tasks unlock with the milestone — work them in order.
        </p>
      </div>
      <ol className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {sorted.map((um, index) => {
          const phase = milestonePhase(um, active?.id ?? null);
          const title = um.milestone?.title ?? `Milestone ${index + 1}`;
          const selectable = phase !== "locked";
          const expanded = selectedId === um.id && selectable;
          const tasks = parseMilestoneTasks(um.milestone?.instructions);
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
                  {um.milestone?.description && (
                    <span className="mt-1 block text-xs text-stone-500 line-clamp-2">
                      {um.milestone.description}
                    </span>
                  )}
                </span>
              </button>

              {expanded && tasks.length > 0 && (
                <ol className="ml-5 mt-1 space-y-1 border-l border-stone-800 pl-3">
                  <li className="px-1 pb-1 text-[10px] font-medium uppercase tracking-wide text-stone-600">
                    Tasks
                  </li>
                  {tasks.map((task) => (
                    <li key={task.id}>
                      <button
                        type="button"
                        onClick={() => onSelectTask(task)}
                        className={clsx(
                          "w-full rounded-md px-2 py-2 text-left text-xs transition-colors",
                          activeTaskId === task.id
                            ? "bg-amber-950/50 text-amber-100 ring-1 ring-amber-800/60"
                            : "text-stone-400 hover:bg-stone-900 hover:text-stone-200",
                        )}
                      >
                        <span className="font-medium text-stone-500">
                          {task.index}.
                        </span>{" "}
                        {task.text}
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
