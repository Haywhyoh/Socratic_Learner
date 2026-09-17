import type {
  AdminConceptSpec,
  AdminDependencySpec,
  AdminGraphPayload,
  AdminMilestoneSpec,
} from "./types";

export const ADMIN_DRAFT_KEY = "socratic_admin_graph_draft";

export const TRACK_LANGUAGES = [
  { slug: "python", name: "Python" },
  { slug: "javascript", name: "JavaScript" },
  { slug: "typescript", name: "TypeScript" },
  { slug: "go", name: "Go" },
  { slug: "csharp", name: "C#" },
  { slug: "c", name: "C" },
] as const;

export function emptyConcept(slug: string, index = 1): AdminConceptSpec {
  const leaf = `concept-${index}`;
  const id = `${slug}.${leaf}`;
  return {
    id,
    title: "New concept",
    category: "foundation",
    description: "",
    learning_objectives: [],
    misconceptions: [],
    diagnostic_questions: [],
    research_questions: [],
    resources: [],
    hints: [
      "What is the smallest example of this idea?",
      "Try the smallest change that would prove you understand it.",
      "Name the mechanism in one sentence.",
      "Structure: write the smallest file that shows this.",
      "Run it and point at the output that proves it.",
    ],
    mastery_requirements: { explanation: true, implementation: true },
    practice_tasks: [],
    mentor_scripts: {},
  };
}

export function emptyMilestone(): AdminMilestoneSpec {
  return {
    title: "New milestone",
    description: "",
    instructions: "",
    success_criteria: "",
    concepts: [],
    questions: [],
  };
}

export function saveDraft(graph: AdminGraphPayload) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(ADMIN_DRAFT_KEY, JSON.stringify(graph));
}

export function loadDraft(): AdminGraphPayload | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(ADMIN_DRAFT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AdminGraphPayload;
  } catch {
    return null;
  }
}

export function clearDraft() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(ADMIN_DRAFT_KEY);
}

export function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => String(item)).join(" · ");
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return "Something went wrong";
}

export function layoutConceptNodes(
  concepts: AdminConceptSpec[],
  dependencies: AdminDependencySpec[],
) {
  const ids = concepts.map((item) => item.id);
  const remaining = new Map(ids.map((id) => [id, new Set<string>()]));
  for (const dep of dependencies) {
    remaining.get(dep.concept_id)?.add(dep.requires_concept_id);
  }
  const placed = new Set<string>();
  const layers: string[][] = [];
  while (placed.size < ids.length) {
    const ready = ids.filter((id) => {
      if (placed.has(id)) return false;
      const deps = remaining.get(id) ?? new Set();
      return [...deps].every((req) => placed.has(req) || !ids.includes(req));
    });
    const batch = ready.length ? ready : ids.filter((id) => !placed.has(id)).slice(0, 1);
    if (!batch.length) break;
    layers.push(batch);
    for (const id of batch) placed.add(id);
  }
  return concepts.map((concept) => {
    const layer = layers.findIndex((row) => row.includes(concept.id));
    const index = Math.max(0, layers[layer]?.indexOf(concept.id) ?? 0);
    return {
      id: concept.id,
      position: { x: Math.max(layer, 0) * 280, y: index * 120 },
      data: {
        label: concept.title,
        category: concept.category,
      },
    };
  });
}
