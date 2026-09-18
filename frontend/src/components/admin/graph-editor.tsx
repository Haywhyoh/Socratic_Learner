"use client";

import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ConceptNode, type ConceptNodeType } from "@/components/admin/concept-node";
import { ConceptPanel } from "@/components/admin/concept-panel";
import { MilestonePanel } from "@/components/admin/milestone-panel";
import { Button } from "@/components/ui/button";
import { emptyConcept, formatApiDetail, layoutConceptNodes, normalizeGraphPracticeTasks, saveDraft, TRACK_LANGUAGES } from "@/lib/admin-graph";
import { api } from "@/lib/api";
import { ApiError, type AdminConceptSpec, type AdminGraphPayload } from "@/lib/types";

const nodeTypes = { concept: ConceptNode };

function graphToEdges(graph: AdminGraphPayload): Edge[] {
  return graph.dependencies.map((dep) => ({
    id: `${dep.requires_concept_id}->${dep.concept_id}`,
    source: dep.requires_concept_id,
    target: dep.concept_id,
    label: dep.reason,
  }));
}

export function GraphEditor({
  initial,
  persistDraft = false,
}: {
  initial: AdminGraphPayload;
  persistDraft?: boolean;
}) {
  const router = useRouter();
  const [graph, setGraph] = useState<AdminGraphPayload>(() => normalizeGraphPracticeTasks(initial));
  const [selectedId, setSelectedId] = useState<string | null>(graph.concepts[0]?.id ?? null);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const initialNodes = useMemo(
    () =>
      layoutConceptNodes(initial.concepts, initial.dependencies).map((node) => ({
        ...node,
        type: "concept" as const,
      })),
    [initial],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState<ConceptNodeType>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graphToEdges(initial));

  useEffect(() => {
    if (persistDraft) saveDraft(graph);
  }, [graph, persistDraft]);

  const selected = graph.concepts.find((item) => item.id === selectedId) ?? null;
  const language = String(graph.project.runtime?.language || graph.course.primary_slug || "python");

  function replaceGraph(next: AdminGraphPayload, keepPositions = true) {
    setGraph(next);
    const positions = new Map(nodes.map((node) => [node.id, node.position]));
    const laidOut = layoutConceptNodes(next.concepts, next.dependencies).map((node) => ({
      ...node,
      type: "concept" as const,
      position: keepPositions && positions.has(node.id) ? positions.get(node.id)! : node.position,
    }));
    setNodes(laidOut);
    setEdges(graphToEdges(next));
  }

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      setEdges((current) => addEdge({ ...connection, label: "" }, current));
      setGraph((current) => {
        const exists = current.dependencies.some(
          (dep) =>
            dep.requires_concept_id === connection.source && dep.concept_id === connection.target,
        );
        if (exists) return current;
        return {
          ...current,
          dependencies: [
            ...current.dependencies,
            {
              concept_id: connection.target!,
              requires_concept_id: connection.source!,
              reason: `${connection.target} builds on ${connection.source}.`,
            },
          ],
        };
      });
    },
    [setEdges],
  );

  function addConcept() {
    const concept = emptyConcept(graph.course.slug, graph.concepts.length + 1);
    const next = { ...graph, concepts: [...graph.concepts, concept] };
    setGraph(next);
    setSelectedId(concept.id);
    setNodes((current) => [
      ...current,
      {
        id: concept.id,
        type: "concept" as const,
        position: { x: 80, y: current.length * 80 },
        data: { label: concept.title, category: concept.category },
      },
    ]);
  }

  function updateConcept(nextConcept: AdminConceptSpec) {
    const previousId = selectedId;
    const renamed = previousId && previousId !== nextConcept.id;
    setGraph((current) => {
      const concepts = current.concepts.map((item) =>
        item.id === previousId ? nextConcept : item,
      );
      const dependencies = current.dependencies.map((dep) => ({
        ...dep,
        concept_id: renamed && dep.concept_id === previousId ? nextConcept.id : dep.concept_id,
        requires_concept_id:
          renamed && dep.requires_concept_id === previousId
            ? nextConcept.id
            : dep.requires_concept_id,
      }));
      const milestones = current.milestones.map((milestone) => ({
        ...milestone,
        concepts: milestone.concepts.map((id) => (renamed && id === previousId ? nextConcept.id : id)),
      }));
      return { ...current, concepts, dependencies, milestones };
    });
    if (renamed) {
      setSelectedId(nextConcept.id);
      setNodes((current) =>
        current.map((node) =>
          node.id === previousId
            ? {
                ...node,
                id: nextConcept.id,
                data: { label: nextConcept.title, category: nextConcept.category },
              }
            : node,
        ),
      );
      setEdges((current) =>
        current.map((edge) => ({
          ...edge,
          id: edge.id.replaceAll(previousId!, nextConcept.id),
          source: edge.source === previousId ? nextConcept.id : edge.source,
          target: edge.target === previousId ? nextConcept.id : edge.target,
        })),
      );
    } else {
      setNodes((current) =>
        current.map((node) =>
          node.id === nextConcept.id
            ? { ...node, data: { label: nextConcept.title, category: nextConcept.category } }
            : node,
        ),
      );
    }
  }

  function deleteConcept(conceptId: string) {
    const next: AdminGraphPayload = {
      ...graph,
      concepts: graph.concepts.filter((item) => item.id !== conceptId),
      dependencies: graph.dependencies.filter(
        (dep) => dep.concept_id !== conceptId && dep.requires_concept_id !== conceptId,
      ),
      milestones: graph.milestones.map((milestone) => ({
        ...milestone,
        concepts: milestone.concepts.filter((id) => id !== conceptId),
      })),
    };
    replaceGraph(next);
    setSelectedId(next.concepts[0]?.id ?? null);
  }

    async function save() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        ...graph,
        project: {
          ...graph.project,
          runtime: { ...graph.project.runtime, language },
        },
      };
      const saved = graph.project_id
        ? await api.updateAdminGraph(graph.project_id, payload)
        : await api.publishAdminGraph(payload);
      setGraph(normalizeGraphPracticeTasks(saved));
      setMessage(
        graph.project_id
          ? "Saved catalog. Existing enrollments stay on their clone until you apply."
          : "Published. Learners can enroll from onboarding.",
      );
      if (persistDraft) {
        const { clearDraft } = await import("@/lib/admin-graph");
        clearDraft();
      }
      if (!graph.project_id && saved.project_id) {
        router.push(`/admin/graphs/${saved.project_id}`);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(formatApiDetail(err.detail ?? err.message));
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Could not save graph");
      }
    } finally {
      setSaving(false);
    }
  }

  async function applyToEnrollments() {
    if (!graph.project_id) return;
    const confirmed = window.confirm(
      "Add new catalog work only to milestones students have not started? Completed and current milestones will not change, and finished courses are skipped.",
    );
    if (!confirmed) return;
    setApplying(true);
    setError(null);
    setMessage(null);
    try {
      const report = await api.applyAdminGraphEnrollments(graph.project_id);
      const updated = report.results.reduce(
        (sum, row) =>
          sum + row.milestones_updated + row.milestones_added,
        0,
      );
      setMessage(
        report.applied === 0 && report.skipped === 0
          ? "No enrollments on this track yet."
          : `Applied to ${report.applied} in-progress enrollment${report.applied === 1 ? "" : "s"}${
              report.skipped ? `, skipped ${report.skipped} already finished` : ""
            }. ${updated} future milestone${updated === 1 ? " was" : "s were"} updated.`,
      );
    } catch (err) {
      if (err instanceof ApiError) {
        setError(formatApiDetail(err.detail ?? err.message));
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Could not apply catalog to enrollments");
      }
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-stone-950">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-800 px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs uppercase tracking-wide text-amber-600">Admin graph</p>
          <input
            className="w-full min-w-0 max-w-xl truncate bg-transparent font-serif text-2xl text-stone-50 outline-none"
            value={graph.project.title}
            onChange={(event) =>
              setGraph((current) => ({
                ...current,
                project: { ...current.project, title: event.target.value },
              }))
            }
          />
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
            <span>{graph.course.slug}</span>
            <select
              className="rounded border border-stone-700 bg-stone-900 px-2 py-0.5 text-xs text-stone-200"
              value={
                TRACK_LANGUAGES.some((item) => item.slug === language) ? language : "python"
              }
              onChange={(event) => {
                const next = event.target.value;
                const label =
                  TRACK_LANGUAGES.find((item) => item.slug === next)?.name ?? next;
                setGraph((current) => ({
                  ...current,
                  course: {
                    ...current.course,
                    primary_slug: next,
                    primary_name: label,
                  },
                  project: {
                    ...current.project,
                    runtime: { ...current.project.runtime, language: next },
                  },
                }));
              }}
            >
              {TRACK_LANGUAGES.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </select>
            <span>· {graph.concepts.length} concepts</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin">
            <Button variant="ghost">All graphs</Button>
          </Link>
          <Button variant="secondary" onClick={addConcept}>
            Add concept
          </Button>
          {graph.project_id ? (
            <Button
              variant="secondary"
              onClick={() => void applyToEnrollments()}
              disabled={saving || applying}
            >
              {applying ? "Applying…" : "Apply to existing enrollments"}
            </Button>
          ) : null}
          <Button onClick={save} disabled={saving || applying}>
            {saving ? "Saving…" : graph.project_id ? "Save" : "Publish"}
          </Button>
        </div>
      </header>
      {(error || message) && (
        <p className={`px-4 py-2 text-sm ${error ? "bg-red-950/60 text-red-200" : "bg-emerald-950/40 text-emerald-200"}`}>
          {error || message}
        </p>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="order-2 max-h-[40vh] overflow-hidden border-b border-stone-800 md:order-1 md:max-h-none md:overflow-hidden md:border-b-0 md:border-r">
          <MilestonePanel
            milestones={graph.milestones}
            concepts={graph.concepts}
            selectedConceptId={selectedId}
            onChange={(milestones) => setGraph((current) => ({ ...current, milestones }))}
          />
        </aside>
        <div className="order-1 h-[45vh] min-h-[320px] md:order-2 md:h-full md:min-h-0">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onEdgesDelete={(deleted) => {
              const removed = new Set(deleted.map((edge) => `${edge.source}->${edge.target}`));
              setGraph((current) => ({
                ...current,
                dependencies: current.dependencies.filter(
                  (dep) => !removed.has(`${dep.requires_concept_id}->${dep.concept_id}`),
                ),
              }));
            }}
            nodeTypes={nodeTypes}
            fitView
            colorMode="dark"
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <aside className="order-3 min-h-0 overflow-hidden border-t border-stone-800 md:border-l md:border-t-0">
          {selected ? (
            <ConceptPanel
              concept={selected}
              language={language}
              projectTitle={graph.project.title}
              slug={graph.course.slug}
              onChange={updateConcept}
              onDelete={() => deleteConcept(selected.id)}
            />
          ) : (
            <p className="p-4 text-sm text-stone-500">Select a concept node to edit it.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
