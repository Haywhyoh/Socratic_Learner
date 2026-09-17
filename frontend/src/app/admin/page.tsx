"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AdminGraphSummary } from "@/lib/types";

export default function AdminPage() {
  const [graphs, setGraphs] = useState<AdminGraphSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listAdminGraphs()
      .then(setGraphs)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-amber-600">Public for testing</p>
          <h1 className="font-serif text-3xl text-stone-50">Knowledge graphs</h1>
          <p className="mt-2 text-sm text-stone-400">
            Generate a track from a topic, edit the DAG, then publish so learners can enroll.
          </p>
        </div>
          <Link href="/">
            <Button variant="ghost">Home</Button>
          </Link>
          <Link href="/admin/graphs/new">
            <Button>New graph</Button>
          </Link>
      </header>

      {loading && <p className="mt-8 text-stone-500">Loading…</p>}
      {error && <p className="mt-8 text-red-400">{error}</p>}
      {!loading && !error && graphs.length === 0 && (
        <div className="mt-8 rounded-xl border border-dashed border-stone-700 p-8 text-center text-stone-400">
          No graphs yet. Generate the first one.
        </div>
      )}
      <ul className="mt-8 space-y-3">
        {graphs.map((graph) => (
          <li key={graph.project_id}>
            <Link
              href={`/admin/graphs/${graph.project_id}`}
              className="block rounded-xl border border-stone-800 bg-stone-900/30 p-4 transition hover:border-amber-800/50"
            >
              <p className="font-medium text-stone-100">{graph.title}</p>
              <p className="mt-1 text-sm text-stone-500">
                {graph.course_name} · {graph.language || "unknown"} · {graph.difficulty}
              </p>
              <p className="mt-2 text-xs text-amber-600/90">
                {graph.concept_count} concepts · {graph.edge_count} edges · {graph.milestone_count}{" "}
                milestones
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
