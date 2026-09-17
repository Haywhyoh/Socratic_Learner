"use client";

import { useEffect, useState } from "react";
import { GenerateForm } from "@/components/admin/generate-form";
import { GraphEditor } from "@/components/admin/graph-editor";
import { loadDraft } from "@/lib/admin-graph";
import type { AdminGraphPayload } from "@/lib/types";

export default function NewGraphPage() {
  const [graph, setGraph] = useState<AdminGraphPayload | null>(null);

  useEffect(() => {
    const draft = loadDraft();
    if (draft && !draft.project_id) {
      Promise.resolve(draft).then(setGraph);
    }
  }, []);

  if (!graph) {
    return <GenerateForm onGenerated={setGraph} />;
  }

  return <GraphEditor initial={graph} persistDraft />;
}
