"use client";

import { Lightbulb, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type {
  ConceptRead,
  GraphRead,
  MentorContractRead,
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
}

function isCoachTurn(role: string): boolean {
  return role === "assistant" || role === "tutor" || role === "system";
}

function actionLabel(action: string | undefined): string {
  switch (action) {
    case "ASK_RESEARCH":
      return "Research";
    case "HINT":
      return "Hint";
    case "ASK_DIAGNOSTIC_QUESTION":
      return "Diagnosis";
    case "ASK_IMPLEMENTATION":
      return "Build";
    case "ASK_REFLECTION":
      return "Reflection";
    case "ASK_DEFENSE":
      return "Defense";
    case "HOLD":
      return "Hold";
    case "REVIEW":
      return "Review";
    default:
      return "Question";
  }
}

export function CoachPanel({
  userProjectId,
  userMilestoneId,
  milestoneTitle,
  graph,
  initialReply,
  initialQuestion,
  initialTurns = [],
  initialContract = null,
  initialConcept = null,
}: CoachPanelProps) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [turns, setTurns] = useState<MentorTurnRead[]>(initialTurns);
  const [currentQuestion, setCurrentQuestion] = useState(initialQuestion);
  const [contract, setContract] = useState<MentorContractRead | null>(initialContract);
  const [concept, setConcept] = useState<ConceptRead | null>(initialConcept);
  const [hintMeta, setHintMeta] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [summary, setSummary] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const conceptId = graph?.current_concept_id ?? concept?.id ?? null;
  const conceptState = graph?.concept_state ?? null;

  useEffect(() => {
    if (initialReply) {
      setTurns((prev) => {
        if (prev.some((t) => t.content === initialReply)) return prev;
        return [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content: initialReply,
            created_at: new Date().toISOString(),
          },
        ];
      });
    }
  }, [initialReply]);

  useEffect(() => {
    setCurrentQuestion(initialQuestion ?? null);
  }, [initialQuestion]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns]);

  const sendMessage = useCallback(
    async (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed || sending) return;
      setSending(true);
      setMessage("");
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
        setCurrentQuestion(res.current_question);
        if (res.contract) setContract(res.contract);
        if (res.concept?.id) setConcept(res.concept);
      } finally {
        setSending(false);
      }
    },
    [sending, userProjectId],
  );

  const requestHint = useCallback(async () => {
    if (!userMilestoneId || hintLoading) return;
    setHintLoading(true);
    setHintMeta(null);
    try {
      const res = await api.requestHint(userMilestoneId);
      if (res.hint_blocked_reason) {
        setHintMeta(
          res.hint_blocked_reason === "need_effort"
            ? "Hints unlock after effort — try a step in the editor/terminal, or share what you attempted."
            : res.hint_blocked_reason,
        );
      } else {
        const label =
          res.hint_level !== null ? `Hint level ${res.hint_level}` : "Hint";
        setTurns((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content: `[${label}] ${res.reply}`,
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } finally {
      setHintLoading(false);
    }
  }, [userMilestoneId, hintLoading]);

  const submitResearch = useCallback(async () => {
    if (!conceptId || (!notes.trim() && !summary.trim())) return;
    setSending(true);
    try {
      await api.submitResearch(userProjectId, conceptId, {
        question: concept?.research_questions?.[0] ?? "",
        learner_notes: notes,
        learner_summary: summary,
      });
      await sendMessage(
        `I researched this. Notes: ${notes || summary}. ${summary}`.slice(0, 2000),
      );
      setNotes("");
      setSummary("");
    } finally {
      setSending(false);
    }
  }, [conceptId, notes, summary, userProjectId, concept, sendMessage]);

  const action = contract?.action;
  const showResearch =
    action === "ASK_RESEARCH" ||
    conceptState === "researching" ||
    conceptState === "introduced";

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden border-l border-stone-800 bg-stone-900/50">
      <div className="shrink-0 border-b border-stone-800 px-4 py-3">
        <h2 className="font-serif text-lg text-stone-100">Senior Engineer</h2>
        <p className="text-xs text-stone-500">
          You do the thinking. I question, hint, and review — I will not write the framework for you.
        </p>
        {milestoneTitle && (
          <p className="mt-2 text-xs text-stone-400">
            Milestone: <span className="text-stone-200">{milestoneTitle}</span>
          </p>
        )}
        {concept?.title && (
          <p className="mt-1 text-xs text-amber-500/90">
            {concept.title}
            {conceptState ? ` · ${conceptState}` : ""}
          </p>
        )}
      </div>

      {currentQuestion && (
        <div className="shrink-0 border-b border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-100/90">
          <span className="text-xs font-medium uppercase tracking-wide text-amber-500">
            {actionLabel(action)}
          </span>
          <p className="mt-1">{currentQuestion}</p>
        </div>
      )}

      {contract?.identified_gap && (
        <div className="shrink-0 border-b border-red-900/40 bg-red-950/20 px-4 py-2 text-xs text-red-200/90">
          Investigating a possible gap in{" "}
          <span className="font-medium">{contract.identified_gap.concept}</span>
        </div>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <div className="space-y-2 text-sm text-stone-500">
            <p>Flow: problem → question → research → discuss → build → test → explain → reflect.</p>
          </div>
        )}
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

      {showResearch && (
        <div className="shrink-0 space-y-2 border-t border-stone-800 p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-stone-500">
            Your research notes
          </p>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="What did you find? Don't paste a definition — write what you understand."
            className="w-full resize-none rounded-lg border border-stone-700 bg-stone-950 px-3 py-2 text-xs text-stone-100 placeholder:text-stone-600"
          />
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={2}
            placeholder="Summarize in your own words."
            className="w-full resize-none rounded-lg border border-stone-700 bg-stone-950 px-3 py-2 text-xs text-stone-100 placeholder:text-stone-600"
          />
          <Button
            type="button"
            variant="secondary"
            className="text-xs"
            disabled={sending || (!notes.trim() && !summary.trim())}
            onClick={() => void submitResearch()}
          >
            Submit research
          </Button>
        </div>
      )}

      <div className="shrink-0 space-y-2 border-t border-stone-800 p-3">
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            className="shrink-0 text-xs"
            disabled={!userMilestoneId || hintLoading}
            onClick={() => void requestHint()}
          >
            <Lightbulb className="h-4 w-4" />
            {hintLoading ? "…" : "Hint"}
          </Button>
        </div>
        <div className="flex gap-2">
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
            placeholder="Answer, explain, or describe what you tried…"
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
    </div>
  );
}
