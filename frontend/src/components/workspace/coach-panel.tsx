"use client";

import { Lightbulb, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type {
  ConceptRead,
  GraphRead,
  MentorContractRead,
  MentorSessionSummary,
  MentorTurnRead,
} from "@/lib/types";
import { CoachMessageContent } from "@/components/workspace/coach-message";

interface CoachPanelProps {
  userProjectId: number;
  userMilestoneId: number | null;
  milestoneTitle?: string | null;
  graph: GraphRead | null;
  initialReply?: string | null;
  initialQuestion?: string | null;
  initialTurns?: MentorTurnRead[];
  initialContract?: MentorContractRead | null;
  initialConcept?: ConceptRead | null;
  readOnly?: boolean;
  attempts?: MentorSessionSummary[];
  selectedAttempt?: number | null;
  onSelectAttempt?: (attempt: number) => void;
  onGraphChange?: (graph: GraphRead) => void;
  onOpenFile?: (path: string) => Promise<void> | void;
}

function isCoachTurn(role: string): boolean {
  return role === "assistant" || role === "tutor" || role === "system";
}

export function CoachPanel({
  userProjectId,
  userMilestoneId,
  milestoneTitle,
  initialReply,
  initialTurns = [],
  initialContract = null,
  readOnly = false,
  attempts = [],
  selectedAttempt = null,
  onSelectAttempt,
  onGraphChange,
  onOpenFile,
}: CoachPanelProps) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [turns, setTurns] = useState<MentorTurnRead[]>(initialTurns);
  const [hintMeta, setHintMeta] = useState<string | null>(null);
  const [contract, setContract] = useState<MentorContractRead | null>(
    initialContract,
  );
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns(initialTurns);
  }, [initialTurns]);

  useEffect(() => {
    setContract(initialContract);
  }, [initialContract]);

  useEffect(() => {
    if (!initialReply || initialTurns.length > 0) return;
    setTurns((prev) => {
      if (prev.length > 0) return prev;
      return [
        {
          id: Date.now(),
          role: "assistant",
          content: initialReply,
          created_at: new Date().toISOString(),
        },
      ];
    });
  }, [initialReply, initialTurns.length]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns]);

  const refreshGraph = useCallback(async () => {
    if (!onGraphChange) return;
    try {
      onGraphChange(await api.getGraph(userProjectId));
    } catch {
      /* graph refresh is optional */
    }
  }, [onGraphChange, userProjectId]);

  const sendMessage = useCallback(
    async (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed || sending) return;
      setSending(true);
      setMessage("");
      setHintMeta(null);
      setTurns((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: "user",
          content: trimmed,
          created_at: new Date().toISOString(),
        },
      ]);
      try {
        const res = await api.coachMessage(userProjectId, trimmed);
        if (res.contract) setContract(res.contract);
        if (res.turns.length) {
          setTurns(res.turns);
        } else if (res.reply) {
          setTurns((prev) => [
            ...prev,
            {
              id: Date.now() + 1,
              role: "assistant",
              content: res.reply,
              created_at: new Date().toISOString(),
            },
          ]);
        }
        await refreshGraph();
        const nextFile = res.contract?.assigned_file;
        if (nextFile && onOpenFile) await onOpenFile(nextFile);
      } finally {
        setSending(false);
      }
    },
    [sending, userProjectId, refreshGraph],
  );

  const applyCoachResult = useCallback(
    async (res: {
      reply?: string;
      turns: MentorTurnRead[];
      contract?: MentorContractRead | null;
    }) => {
      if (res.contract) setContract(res.contract);
      if (res.turns.length) {
        setTurns(res.turns);
      } else if (res.reply) {
        setTurns((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "assistant",
            content: res.reply ?? "",
            created_at: new Date().toISOString(),
          },
        ]);
      }
      await refreshGraph();
      const nextFile = res.contract?.assigned_file;
      if (nextFile && onOpenFile) await onOpenFile(nextFile);
    },
    [refreshGraph, onOpenFile],
  );

  const checkWork = useCallback(async () => {
    if (checking || sending) return;
    setChecking(true);
    setHintMeta(null);
    try {
      const res = await api.evaluatePractice(userProjectId, {
        filename: contract?.assigned_file ?? undefined,
        task_id: contract?.practice_task_id ?? undefined,
      });
      await applyCoachResult(res);
    } finally {
      setChecking(false);
    }
  }, [checking, sending, userProjectId, contract, applyCoachResult]);

  const requestHint = useCallback(async () => {
    if (!userMilestoneId || hintLoading) return;
    setHintLoading(true);
    setHintMeta(null);
    try {
      const res = await api.requestHint(userMilestoneId);
      if (res.hint_blocked_reason) {
        setHintMeta(
          res.hint_blocked_reason === "need_effort"
            ? "Show me what you tried first — then I can hint."
            : res.hint_blocked_reason,
        );
      } else if (res.reply) {
        setTurns((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content: res.reply,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      await refreshGraph();
    } finally {
      setHintLoading(false);
    }
  }, [userMilestoneId, hintLoading, refreshGraph]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden border-l border-stone-800 bg-stone-900/50">
      <div className="shrink-0 border-b border-stone-800 px-4 py-3">
        <h2 className="font-serif text-lg text-stone-100">Senior Engineer</h2>
        <p className="text-xs text-stone-500">
          {readOnly
            ? milestoneTitle
              ? `Saved chat for ${milestoneTitle}. This thread is read-only.`
              : "Saved chat. This thread is read-only."
            : milestoneTitle
              ? `Working through ${milestoneTitle}. Ask, answer, or say what you tried.`
              : "Ask, answer, or say what you tried."}
        </p>
        {attempts.length > 1 && (
          <label className="mt-2 block text-[11px] text-stone-500">
            Attempt
            <select
              className="ml-2 rounded border border-stone-700 bg-stone-950 px-2 py-1 text-xs text-stone-200"
              value={selectedAttempt ?? attempts[attempts.length - 1]?.attempt ?? 1}
              onChange={(e) => onSelectAttempt?.(Number(e.target.value))}
            >
              {attempts.map((item) => (
                <option key={item.id} value={item.attempt}>
                  {item.attempt}
                  {item.status === "completed" ? " (saved)" : " (current)"}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {turns.map((turn) => (
          <div
            key={turn.id}
            className={
              turn.role === "user" || turn.role === "learner"
                ? "ml-6 rounded-lg bg-stone-800 px-3 py-2 text-sm text-stone-200"
                : "mr-4 rounded-lg border border-stone-700/80 bg-stone-950/60 px-3 py-2 text-sm text-stone-300"
            }
          >
            {isCoachTurn(turn.role) ? (
              <CoachMessageContent content={turn.content} />
            ) : (
              <span className="whitespace-pre-wrap">{turn.content}</span>
            )}
          </div>
        ))}
      </div>

      {hintMeta && (
        <p className="shrink-0 px-4 pb-2 text-xs text-amber-600/90">{hintMeta}</p>
      )}

      {readOnly ? (
        <p className="shrink-0 border-t border-stone-800 px-4 py-3 text-xs text-stone-500">
          This conversation was saved with the milestone. Redo the milestone to start a new chat.
        </p>
      ) : (
      <div className="shrink-0 border-t border-stone-800 p-3">
        {contract?.assigned_file && (
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-stone-400">
            <span>
              Assigned file:{" "}
              <code className="text-amber-200">{contract.assigned_file}</code>
            </span>
            {onOpenFile && (
              <Button
                type="button"
                variant="ghost"
                className="h-7 px-2 text-xs"
                onClick={() => void onOpenFile(contract.assigned_file!)}
              >
                Open file
              </Button>
            )}
            <Button
              type="button"
              variant="secondary"
              className="h-7 px-2 text-xs"
              disabled={checking || sending}
              onClick={() => void checkWork()}
            >
              {checking ? "Checking…" : "Check my work"}
            </Button>
          </div>
        )}
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            className="shrink-0 self-end text-xs"
            disabled={!userMilestoneId || hintLoading}
            onClick={() => void requestHint()}
          >
            <Lightbulb className="h-4 w-4" />
            {hintLoading ? "…" : "Hint"}
          </Button>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendMessage(message);
              }
            }}
            rows={2}
            placeholder="Reply…"
            className="flex-1 resize-none rounded-lg border border-stone-700 bg-stone-950 px-3 py-2 text-sm text-stone-100 placeholder:text-stone-600 focus:border-amber-700 focus:outline-none"
          />
          <Button
            type="button"
            className="self-end"
            disabled={sending || !message.trim()}
            onClick={() => void sendMessage(message)}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
      )}
    </div>
  );
}
