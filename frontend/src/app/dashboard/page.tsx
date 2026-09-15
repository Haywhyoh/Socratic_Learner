"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";
import { api } from "@/lib/api";
import type { EnrollmentRead } from "@/lib/types";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [enrollments, setEnrollments] = useState<EnrollmentRead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listEnrollments()
      .then(setEnrollments)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl text-stone-50">Dashboard</h1>
          <p className="mt-1 text-sm text-stone-500">{user?.email}</p>
        </div>
        <div className="flex gap-2">
          <Link href="/onboard">
            <Button>New path</Button>
          </Link>
          <Button
            variant="ghost"
            onClick={() => {
              logout();
              router.push("/");
            }}
          >
            Sign out
          </Button>
        </div>
      </header>

      <section className="mt-10">
        <h2 className="text-sm font-medium uppercase tracking-wide text-stone-500">
          Your enrollments
        </h2>
        {loading && <p className="mt-4 text-stone-500">Loading…</p>}
        {!loading && enrollments.length === 0 && (
          <div className="mt-6 rounded-xl border border-dashed border-stone-700 p-8 text-center">
            <p className="text-stone-400">No paths yet.</p>
            <Link href="/onboard" className="mt-4 inline-block">
              <Button>Choose course & stack</Button>
            </Link>
          </div>
        )}
        <ul className="mt-4 space-y-3">
          {enrollments.map((e) => (
            <li key={e.id}>
              <Link
                href={`/workspace/${e.id}`}
                className="block rounded-xl border border-stone-800 bg-stone-900/30 p-4 transition hover:border-amber-800/50"
              >
                <p className="font-medium text-stone-100">
                  {e.course?.name ?? `Course ${e.course_id}`}
                </p>
                <p className="mt-1 text-sm text-stone-500">
                  {e.primary_option?.name} · {e.secondary_option?.name} ·{" "}
                  {e.learning_mode}
                </p>
                {e.user_project?.project && (
                  <p className="mt-2 text-xs text-amber-600/90">
                    {e.user_project.project.title}
                  </p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <AuthGate>
      <DashboardContent />
    </AuthGate>
  );
}
