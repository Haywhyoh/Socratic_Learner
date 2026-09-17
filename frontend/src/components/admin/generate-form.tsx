"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { formatApiDetail, saveDraft, TRACK_LANGUAGES } from "@/lib/admin-graph";
import { api } from "@/lib/api";
import { ApiError, type AdminGenerateRequest, type AdminGraphPayload } from "@/lib/types";

export function GenerateForm({
  onGenerated,
}: {
  onGenerated: (graph: AdminGraphPayload) => void;
}) {
  const [topic, setTopic] = useState("");
  const [slug, setSlug] = useState("");
  const [courseName, setCourseName] = useState("");
  const [language, setLanguage] = useState("python");
  const [difficulty, setDifficulty] = useState("beginner");
  const [audience, setAudience] = useState("");
  const [capstone, setCapstone] = useState("");
  const [constraints, setConstraints] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function slugFromTopic(value: string) {
    return value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const payload: AdminGenerateRequest = {
      topic,
      language,
      slug: slug || slugFromTopic(topic) || "track",
      audience,
      constraints: constraints
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      capstone,
      difficulty,
      course_name: courseName || topic,
    };
    try {
      const graph = await api.generateAdminGraph(payload);
      saveDraft(graph);
      onGenerated(graph);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(formatApiDetail(err.detail ?? err.message));
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Could not generate a graph");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-2xl space-y-4 px-4 py-10">
      <div>
        <p className="text-xs uppercase tracking-wide text-amber-600">Admin</p>
        <h1 className="mt-1 font-serif text-3xl text-stone-50">New knowledge graph</h1>
        <p className="mt-2 text-sm text-stone-400">
          Describe the track. The model drafts a Python-style graph; you edit the DAG before
          publishing.
        </p>
      </div>
      <label className="block text-sm text-stone-300">
        Topic
        <input
          required
          className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
          value={topic}
          onChange={(event) => {
            setTopic(event.target.value);
            if (!slug) setSlug(slugFromTopic(event.target.value));
          }}
          placeholder="Go CLI notes, SQL joins, HTTP from scratch…"
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm text-stone-300">
          Course slug
          <input
            required
            className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 font-mono text-sm"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
          />
        </label>
        <label className="block text-sm text-stone-300">
          Course name
          <input
            className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
            value={courseName}
            onChange={(event) => setCourseName(event.target.value)}
          />
        </label>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm text-stone-300">
          Language
          <select
            className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
          >
            {TRACK_LANGUAGES.map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm text-stone-300">
          Difficulty
          <select
            className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
            value={difficulty}
            onChange={(event) => setDifficulty(event.target.value)}
          >
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </label>
      </div>
      <label className="block text-sm text-stone-300">
        Audience
        <input
          className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
          value={audience}
          onChange={(event) => setAudience(event.target.value)}
          placeholder="No prior Python required"
        />
      </label>
      <label className="block text-sm text-stone-300">
        Capstone idea
        <input
          className="mt-1 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
          value={capstone}
          onChange={(event) => setCapstone(event.target.value)}
          placeholder="A stdlib CLI notebook"
        />
      </label>
      <label className="block text-sm text-stone-300">
        Constraints (one per line)
        <textarea
          className="mt-1 min-h-20 w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2"
          value={constraints}
          onChange={(event) => setConstraints(event.target.value)}
        />
      </label>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <Button type="submit" disabled={busy} className="px-6">
        {busy ? "Generating…" : "Generate draft"}
      </Button>
      <p className="text-sm text-stone-500">
        <Link href="/admin" className="text-amber-500 hover:text-amber-400">
          Back to graphs
        </Link>
      </p>
    </form>
  );
}
