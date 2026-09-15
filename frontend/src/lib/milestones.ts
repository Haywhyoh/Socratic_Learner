import type { UserMilestoneRead } from "./types";

export type MilestonePhase = "completed" | "active" | "locked";

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
