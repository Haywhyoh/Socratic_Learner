"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { GraphEditor } from "@/components/admin/graph-editor";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AdminGraphPayload } from "@/lib/types";

export default function EditGraphPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Number(params.projectId);
  const invalid = !Number.isFinite(projectId);
  const [graph, setGraph] = useState<AdminGraphPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (invalid) return;
    api
      .getAdminGraph(projectId)
      .then(setGraph)
      .catch((err: Error) => setError(err.message));
  }, [invalid, projectId]);

  if (invalid || error) {
    return (
      <main className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="text-red-400">{error ?? "Invalid graph id"}</p>
        <Link href="/admin" className="mt-4 inline-block">
          <Button variant="secondary">Back to graphs</Button>
        </Link>
      </main>
    );
  }
  if (!graph) {
    return <p className="px-4 py-16 text-center text-stone-500">Loading graph…</p>;
  }
  return <GraphEditor initial={graph} />;
}
