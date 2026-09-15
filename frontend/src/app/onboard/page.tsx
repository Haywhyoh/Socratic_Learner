"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { CourseOptionRead, CourseRead, LearningMode } from "@/lib/types";
import { ApiError } from "@/lib/types";

type Step = "course" | "primary" | "secondary" | "mode";

function OnboardWizard() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("course");
  const [courses, setCourses] = useState<CourseRead[]>([]);
  const [primaryOptions, setPrimaryOptions] = useState<CourseOptionRead[]>([]);
  const [secondaryOptions, setSecondaryOptions] = useState<CourseOptionRead[]>(
    [],
  );
  const [course, setCourse] = useState<CourseRead | null>(null);
  const [primary, setPrimary] = useState<CourseOptionRead | null>(null);
  const [secondary, setSecondary] = useState<CourseOptionRead | null>(null);
  const [mode, setMode] = useState<LearningMode>("project");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listCourses().then(setCourses).catch(() => setError("Could not load courses"));
  }, []);

  const loadPrimary = useCallback(async (c: CourseRead) => {
    const opts = await api.listPrimaryOptions(c.id);
    setPrimaryOptions(opts);
  }, []);

  const loadSecondary = useCallback(async (c: CourseRead, p: CourseOptionRead) => {
    const opts = await api.listSecondaryOptions(c.id, p.id);
    setSecondaryOptions(opts);
  }, []);

  async function enroll() {
    if (!course || !primary || !secondary) return;
    setSubmitting(true);
    setError(null);
    try {
      const detail = await api.createEnrollment({
        course_id: course.id,
        primary_option_id: primary.id,
        secondary_option_id: secondary.id,
        learning_mode: mode,
      });
      router.push(`/workspace/${detail.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Enrollment failed");
    } finally {
      setSubmitting(false);
    }
  }

  const stepIndex =
    step === "course" ? 1 : step === "primary" ? 2 : step === "secondary" ? 3 : 4;

  return (
    <main className="mx-auto min-h-screen max-w-2xl px-4 py-10">
      <Link href="/dashboard" className="text-sm text-stone-500 hover:text-stone-300">
        ← Dashboard
      </Link>
      <h1 className="mt-6 font-serif text-3xl text-stone-50">Choose your path</h1>
      <p className="mt-2 text-stone-500">
        Step {stepIndex} of 4 — each choice shapes your project and coach context.
      </p>

      <div className="mt-4 flex gap-2">
        {(["course", "primary", "secondary", "mode"] as Step[]).map((s, i) => (
          <div
            key={s}
            className={`h-1 flex-1 rounded-full ${
              stepIndex > i ? "bg-amber-500" : "bg-stone-800"
            }`}
          />
        ))}
      </div>

      <div className="mt-10 space-y-4">
        {step === "course" &&
          courses.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                setCourse(c);
                setPrimary(null);
                setSecondary(null);
                void loadPrimary(c);
                setStep("primary");
              }}
              className="block w-full rounded-xl border border-stone-800 bg-stone-900/40 p-5 text-left transition hover:border-amber-800/60"
            >
              <p className="font-medium text-stone-100">{c.name}</p>
              {c.description && (
                <p className="mt-2 text-sm text-stone-500">{c.description}</p>
              )}
            </button>
          ))}

        {step === "primary" && course && (
          <>
            <p className="text-sm text-stone-400">
              {course.primary_label}
            </p>
            {primaryOptions.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => {
                  setPrimary(o);
                  setSecondary(null);
                  void loadSecondary(course, o);
                  setStep("secondary");
                }}
                className="block w-full rounded-xl border border-stone-800 p-4 text-left hover:border-amber-800/60"
              >
                {o.name}
              </button>
            ))}
            <Button variant="ghost" onClick={() => setStep("course")}>
              Back
            </Button>
          </>
        )}

        {step === "secondary" && course && (
          <>
            <p className="text-sm text-stone-400">
              {course.secondary_label}
            </p>
            {secondaryOptions.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => {
                  setSecondary(o);
                  setStep("mode");
                }}
                className="block w-full rounded-xl border border-stone-800 p-4 text-left hover:border-amber-800/60"
              >
                {o.name}
              </button>
            ))}
            <Button variant="ghost" onClick={() => setStep("primary")}>
              Back
            </Button>
          </>
        )}

        {step === "mode" && (
          <>
            <p className="text-sm text-stone-400">Learning mode</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  {
                    id: "project" as LearningMode,
                    title: "Project-based",
                    desc: "Build milestones in the sandbox with tests and AI review.",
                  },
                  {
                    id: "concept" as LearningMode,
                    title: "Concept / debate",
                    desc: "Research, argue, and synthesize — UI stub for now.",
                  },
                ] as const
              ).map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={`rounded-xl border p-4 text-left ${
                    mode === m.id
                      ? "border-amber-600 bg-amber-950/30"
                      : "border-stone-800"
                  }`}
                >
                  <p className="font-medium text-stone-100">{m.title}</p>
                  <p className="mt-2 text-xs text-stone-500">{m.desc}</p>
                </button>
              ))}
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <div className="flex gap-3 pt-4">
              <Button variant="ghost" onClick={() => setStep("secondary")}>
                Back
              </Button>
              <Button disabled={submitting} onClick={() => void enroll()}>
                {submitting ? "Enrolling…" : "Enter workspace"}
              </Button>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

export default function OnboardPage() {
  return (
    <AuthGate>
      <OnboardWizard />
    </AuthGate>
  );
}
