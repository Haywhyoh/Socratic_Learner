"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "@/components/auth-gate";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { api } from "@/lib/api";
import type { EnrollmentDetail } from "@/lib/types";

function WorkspacePageInner() {
  const params = useParams();
  const enrollmentId = Number(params.enrollmentId);
  const [enrollment, setEnrollment] = useState<EnrollmentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(enrollmentId)) return;
    try {
      const data = await api.getEnrollment(enrollmentId);
      setEnrollment(data);
    } catch {
      setError("Could not load enrollment");
    }
  }, [enrollmentId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="p-8 text-red-400">
        {error}{" "}
        <Link href="/dashboard" className="text-amber-500 underline">
          Back
        </Link>
      </div>
    );
  }

  if (!enrollment) {
    return (
      <div className="flex min-h-screen items-center justify-center text-stone-500">
        Loading workspace…
      </div>
    );
  }

  return (
    <WorkspaceShell
      enrollment={enrollment}
      onEnrollmentChange={setEnrollment}
    />
  );
}

export default function WorkspacePage() {
  return (
    <AuthGate>
      <WorkspacePageInner />
    </AuthGate>
  );
}
