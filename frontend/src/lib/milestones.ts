import type { UserMilestoneRead } from "./types";

export type MilestonePhase = "completed" | "active" | "locked";

export interface MilestoneTask {
  id: string;
  index: number;
  text: string;
}

export function sortUserMilestones(
  items: UserMilestoneRead[],
): UserMilestoneRead[] {
  return [...items].sort(
    (a, b) =>
      (a.milestone?.order_index ?? 0) - (b.milestone?.order_index ?? 0),
  );
}

export function getActiveUserMilestone(
  items: UserMilestoneRead[],
): UserMilestoneRead | null {
  const sorted = sortUserMilestones(items);
  return sorted.find((um) => um.status === "pending") ?? null;
}

export function milestonePhase(
  um: UserMilestoneRead,
  activeId: number | null,
): MilestonePhase {
  if (um.status === "completed") return "completed";
  if (activeId !== null && um.id === activeId) return "active";
  return "locked";
}

/** Parse numbered / bulleted steps from milestone instructions. */
export function parseMilestoneTasks(instructions: string | null | undefined): MilestoneTask[] {
  if (!instructions) return [];
  const tasks: MilestoneTask[] = [];
  for (const line of instructions.split("\n")) {
    const match = line.match(/^\s*(?:\d+[.)]\s+|[-*]\s+)(.+)$/);
    if (match?.[1]?.trim()) {
      const index = tasks.length + 1;
      tasks.push({
        id: `task-${index}`,
        index,
        text: match[1].trim(),
      });
    }
  }
  return tasks;
}
