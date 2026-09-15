"use client";

import Link from "next/link";
import {
  FileCode,
  Play,
  FlaskConical,
  Save,
  Loader2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { CodeEditor } from "@/components/workspace/code-editor";
import { CoachPanel } from "@/components/workspace/coach-panel";
import { MilestoneRail } from "@/components/workspace/milestone-rail";
import {
  SandboxTerminal,
  type SandboxTerminalHandle,
} from "@/components/workspace/sandbox-terminal";
import { ProjectBriefModal } from "@/components/workspace/project-brief-modal";
import { api } from "@/lib/api";
import {
  getActiveUserMilestone,
  parseMilestoneTasks,
  type MilestoneTask,
} from "@/lib/milestones";
import type {
  EnrollmentDetail,
  ProjectDetail,
  SandboxFileEntry,
  UserMilestoneRead,
} from "@/lib/types";
import { ApiError } from "@/lib/types";

interface WorkspaceShellProps {
  enrollment: EnrollmentDetail;
  onEnrollmentChange: (e: EnrollmentDetail) => void;
}

export function WorkspaceShell({
  enrollment,
  onEnrollmentChange,
}: WorkspaceShellProps) {
  const userProjectId = enrollment.user_project?.id;
  const userMilestones = enrollment.user_milestones ?? [];
  const activeUm = getActiveUserMilestone(userMilestones);
  const terminalRef = useRef<SandboxTerminalHandle>(null);

  const [selectedUm, setSelectedUm] = useState<UserMilestoneRead | null>(
    activeUm,
  );
  const [activeTask, setActiveTask] = useState<MilestoneTask | null>(() => {
    const tasks = parseMilestoneTasks(activeUm?.milestone?.instructions);
    return tasks[0] ?? null;
  });
  const [files, setFiles] = useState<SandboxFileEntry[]>([]);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [coachReady, setCoachReady] = useState(false);
  const [questionsComplete, setQuestionsComplete] = useState(false);
  const [coachBoot, setCoachBoot] = useState<{
    reply: string | null;
    question: string | null;
    cards: import("@/lib/types").ConceptCardRead[];
  }>({ reply: null, question: null, cards: [] });
  const [briefOpen, setBriefOpen] = useState(false);
  const [brief, setBrief] = useState<ProjectDetail | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);

  const displayUm = selectedUm ?? activeUm;
  const projectTitle =
    enrollment.assigned_project?.title ??
    enrollment.user_project?.project?.title ??
    "Project";

  const filePaths = useMemo(
    () => files.filter((f) => !f.is_dir).map((f) => f.path),
    [files],
  );

  const refreshFiles = useCallback(async () => {
    if (!userProjectId) return;
    const { files: listed } = await api.listSandboxFiles(userProjectId);
    setFiles(listed);
    return listed;
  }, [userProjectId]);

  const loadFile = useCallback(
    async (path: string) => {
      if (!userProjectId) return;
      const { content } = await api.readSandboxFile(userProjectId, path);
      setActiveFile(path);
      setEditorContent(content);
      setDirty(false);
    },
    [userProjectId],
  );

  const saveFile = useCallback(async () => {
    if (!userProjectId || !activeFile) return;
    setBusy("save");
    try {
      await api.writeSandboxFile(userProjectId, activeFile, editorContent);
      setDirty(false);
      terminalRef.current?.echo(`saved ${activeFile}`);
    } finally {
      setBusy(null);
    }
  }, [userProjectId, activeFile, editorContent]);

  useEffect(() => {
    if (!userProjectId) return;
    let cancelled = false;

    async function boot() {
      setBusy("init");
      try {
        await api.initSandbox(userProjectId!);
        const listed = await refreshFiles();
        const coach = await api.coachStart(userProjectId!);
        if (cancelled) return;
        setCoachBoot({
          reply: coach.reply,
          question: coach.current_question,
          cards: coach.cards,
        });
        setQuestionsComplete(
          Boolean(coach.learner_state?.questions_complete) ||
            !coach.current_question,
        );
        setCoachReady(true);
        const py = listed?.find((f) => f.path === "main.py" && !f.is_dir);
        const first =
          py?.path ?? listed?.find((f) => !f.is_dir)?.path ?? null;
        if (first) await loadFile(first);
      } catch (e) {
        terminalRef.current?.echo(
          e instanceof ApiError ? e.message : "Failed to initialize workspace",
        );
      } finally {
        if (!cancelled) setBusy(null);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, [userProjectId, refreshFiles, loadFile]);

  const openBrief = async () => {
    const projectId =
      enrollment.assigned_project_id ??
      enrollment.user_project?.project_id ??
      enrollment.assigned_project?.id;
    setBriefOpen(true);
    if (!projectId) return;
    if (brief?.id === projectId) return;
    setBriefLoading(true);
    try {
      setBrief(await api.getProject(projectId));
    } catch {
      setBrief(null);
    } finally {
      setBriefLoading(false);
    }
  };

  const runPython = async () => {
    if (!userProjectId) return;
    if (dirty && activeFile) await saveFile();
    setBusy("run");
    try {
      const cmd = activeFile?.endsWith(".py")
        ? `python ${activeFile}`
        : "python main.py";
      await terminalRef.current?.runCommand(cmd);
    } finally {
      setBusy(null);
    }
  };

  const runTests = async () => {
    if (!userProjectId) return;
    if (dirty && activeFile) await saveFile();
    setBusy("test");
    try {
      await terminalRef.current?.runCommand("pytest -q");
    } finally {
      setBusy(null);
    }
  };

  const requestReview = async () => {
    if (!displayUm) return;
    setBusy("review");
    try {
      const review = await api.requestMilestoneReview(displayUm.id);
      terminalRef.current?.echo(
        `Review (${review.verdict}): ${review.summary}\n` +
          (review.understanding_questions.length
            ? `Questions:\n${review.understanding_questions.map((q, i) => `${i + 1}. ${q}`).join("\n")}`
            : ""),
      );
    } catch (e) {
      terminalRef.current?.echo(
        e instanceof ApiError ? e.message : "Review failed",
      );
    } finally {
      setBusy(null);
    }
  };

  const completeMilestone = async () => {
    if (!displayUm || displayUm.id !== activeUm?.id) return;
    setBusy("complete");
    try {
      await api.completeMilestone(displayUm.id);
      const updated = await api.getEnrollment(enrollment.id);
      onEnrollmentChange(updated);
      const nextActive = getActiveUserMilestone(updated.user_milestones);
      setSelectedUm(nextActive);
      terminalRef.current?.echo("Milestone completed.");
    } catch (e) {
      terminalRef.current?.echo(
        e instanceof ApiError ? e.message : "Could not complete milestone",
      );
    } finally {
      setBusy(null);
    }
  };

  if (enrollment.learning_mode === "concept") {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center p-8 text-center text-stone-400">
        <p className="font-serif text-xl text-stone-200">Concept mode</p>
        <p className="mt-2 max-w-md text-sm">
          Debate and deep-thinking UI is coming next. Your enrollment is saved —
          switch to a project path or use the CLI for concept sessions today.
        </p>
      </div>
    );
  }

  if (!userProjectId) {
    return (
      <div className="p-8 text-stone-400">
        No project assigned for this enrollment.
      </div>
    );
  }

  const milestoneDetail = displayUm?.milestone;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-stone-800 px-4">
        <div>
          <Link
            href="/dashboard"
            className="text-xs text-stone-500 hover:text-stone-300"
          >
            ← Dashboard
          </Link>
          <h1 className="font-serif text-lg text-stone-100">
            <button
              type="button"
              onClick={() => void openBrief()}
              className="hover:text-amber-200"
              title="Open project brief"
            >
              {projectTitle}
            </button>
          </h1>
          <p className="text-xs text-stone-500">
            {enrollment.primary_option?.name} · {enrollment.secondary_option?.name}{" "}
            <button
              type="button"
              onClick={() => void openBrief()}
              className="ml-2 text-amber-600 hover:text-amber-400"
            >
              Brief
            </button>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            className="text-xs"
            disabled={!activeFile || busy !== null}
            onClick={() => void saveFile()}
          >
            {busy === "save" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </Button>
          <Button
            variant="secondary"
            className="text-xs"
            disabled={busy !== null}
            onClick={() => void runPython()}
          >
            <Play className="h-4 w-4" />
            Run
          </Button>
          <Button
            variant="secondary"
            className="text-xs"
            disabled={busy !== null}
            onClick={() => void runTests()}
          >
            <FlaskConical className="h-4 w-4" />
            Tests
          </Button>
          {displayUm?.id === activeUm?.id && (
            <>
              <Button
                variant="ghost"
                className="text-xs"
                disabled={busy !== null}
                onClick={() => void requestReview()}
              >
                AI review
              </Button>
              <Button
                className="text-xs"
                disabled={busy !== null}
                onClick={() => void completeMilestone()}
              >
                Complete milestone
              </Button>
            </>
          )}
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_360px]">
        <MilestoneRail
          userMilestones={userMilestones}
          selectedId={displayUm?.id ?? null}
          activeTaskId={activeTask?.id ?? null}
          onSelect={(um) => {
            setSelectedUm(um);
            const tasks = parseMilestoneTasks(um.milestone?.instructions);
            setActiveTask(tasks[0] ?? null);
          }}
          onSelectTask={setActiveTask}
        />

        <div className="flex min-w-0 flex-col">
          {milestoneDetail && (
            <div className="shrink-0 border-b border-stone-800 bg-stone-900/30 px-4 py-3 text-sm">
              <p className="font-medium text-stone-200">{milestoneDetail.title}</p>
              {activeTask ? (
                <p className="mt-1 text-stone-400">
                  <span className="text-amber-500/90">Task {activeTask.index}:</span>{" "}
                  {activeTask.text}
                </p>
              ) : (
                <p className="mt-1 text-stone-500">{milestoneDetail.description}</p>
              )}
              <p className="mt-2 text-xs text-stone-600">
                Success: {milestoneDetail.success_criteria}
              </p>
            </div>
          )}

          <div className="flex min-h-0 flex-1">
            <aside className="w-44 shrink-0 overflow-y-auto border-r border-stone-800 bg-stone-950 p-2">
              <p className="px-2 py-1 text-xs font-medium uppercase text-stone-600">
                Files
              </p>
              <ul className="space-y-0.5">
                {filePaths.map((path) => (
                  <li key={path}>
                    <button
                      type="button"
                      onClick={() => void loadFile(path)}
                      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs ${
                        activeFile === path
                          ? "bg-stone-800 text-amber-200"
                          : "text-stone-400 hover:bg-stone-900"
                      }`}
                    >
                      <FileCode className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{path}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </aside>

            <div className="flex min-w-0 flex-1 flex-col">
              <div className="min-h-0 flex-[3]">
                {activeFile ? (
                  <CodeEditor
                    path={activeFile}
                    value={editorContent}
                    onChange={(v) => {
                      setEditorContent(v);
                      setDirty(true);
                    }}
                    onSave={() => void saveFile()}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-stone-600">
                    {busy === "init" ? "Preparing sandbox…" : "Select a file"}
                  </div>
                )}
              </div>
              <div className="min-h-[11rem] flex-[2]">
                <SandboxTerminal
                  ref={terminalRef}
                  userProjectId={userProjectId}
                  onFsMutated={() => void refreshFiles()}
                />
              </div>
            </div>
          </div>
        </div>

        {coachReady && (
          <CoachPanel
            userProjectId={userProjectId}
            userMilestoneId={activeUm?.id ?? null}
            milestoneTitle={displayUm?.milestone?.title}
            activeTask={activeTask}
            questionsComplete={questionsComplete}
            initialReply={coachBoot.reply}
            initialQuestion={coachBoot.question}
            initialCards={coachBoot.cards}
          />
        )}
      </div>
      <ProjectBriefModal
        open={briefOpen}
        onClose={() => setBriefOpen(false)}
        project={brief}
        loading={briefLoading}
        currentMilestone={milestoneDetail}
      />
    </div>
  );
}
