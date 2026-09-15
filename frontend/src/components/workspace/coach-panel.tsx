"use client";

import { Lightbulb, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ConceptCardRead, MentorTurnRead } from "@/lib/types";
import type { MilestoneTask } from "@/lib/milestones";
import { CoachMessageContent } from "@/components/workspace/coach-message";

interface CoachPanelProps {
  userProjectId: number;
  userMilestoneId: number | null;
  milestoneTitle?: string | null;
  activeTask?: MilestoneTask | null;
  questionsComplete?: boolean;
  initialReply?: string | null;
  initialQuestion?: string | null;
  initialTurns?: MentorTurnRead[];
  initialCards?: ConceptCardRead[];
}

function isCoachTurn(role: string): boolean {
  return role === "assistant" || role === "tutor" || role === "system";
}

export function CoachPanel({
  userProjectId,
  userMilestoneId,
  milestoneTitle,
  activeTask,
  questionsComplete = false,
  initialReply,
  initialQuestion,
  initialTurns = [],
  initialCards = [],
}: CoachPanelProps) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [turns, setTurns] = useState<MentorTurnRead[]>(initialTurns);
  const [cards, setCards] = useState<ConceptCardRead[]>(initialCards);
  const [currentQuestion, setCurrentQuestion] = useState(initialQuestion);
  const [questionsDone, setQuestionsDone] = useState(questionsComplete);
  const [hintMeta, setHintMeta] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuestionsDone(questionsComplete);
  }, [questionsComplete]);

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
        if (res.learner_state) {
          setQuestionsDone(res.learner_state.questions_complete);
        } else if (res.answer_status === "passed" && !res.current_question) {
          setQuestionsDone(true);
        }
        if (res.cards.length) setCards(res.cards);
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

  const suggestions = activeTask
    ? [
        `How do I do step/task ${activeTask.index}?`,
        "I finished this step — done",
        "I hit an error on this step",
      ]
    : [
        "How do I get started on the first step?",
        "done",
        "I hit an error — what should I check?",
      ];

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden border-l border-stone-800 bg-stone-900/50">
      <div className="shrink-0 border-b border-stone-800 px-4 py-3">
        <h2 className="font-serif text-lg text-stone-100">Senior Engineer</h2>
        <p className="text-xs text-stone-500">
          Ask specific questions — commands, errors, design. I won&apos;t paste the full app.
        </p>
        {milestoneTitle && (
          <p className="mt-2 text-xs text-stone-400">
            Milestone: <span className="text-stone-200">{milestoneTitle}</span>
          </p>
        )}
        {activeTask && (
          <p className="mt-1 text-xs text-amber-500/90">
            Focus task {activeTask.index}: {activeTask.text}
          </p>
        )}
      </div>

      {currentQuestion && !questionsDone && (
        <div className="shrink-0 border-b border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-100/90">
          <span className="text-xs font-medium uppercase tracking-wide text-amber-500">
            Think first — checkpoint
          </span>
          <p className="mt-1">{currentQuestion}</p>
          <p className="mt-2 text-xs text-amber-200/60">
            Answer this in your own words before asking for build help.
          </p>
        </div>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <div className="space-y-2 text-sm text-stone-500">
            <p>
              Flow: answer the checkpoint → pick a task on the left → ask how to
              approach it → implement in the editor/terminal.
            </p>
            <p className="text-xs text-stone-600">
              I won&apos;t paste a full solution. I will challenge your plan and
              point you at the next decision.
            </p>
          </div>
        )}
        {turns.map((turn) => (
          <div
            key={turn.id}
            className={
              turn.role === "user"
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

      <div className="shrink-0 space-y-2 border-t border-stone-800 p-3">
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((prompt) => (
            <button
              key={prompt}
              type="button"
              disabled={sending}
              onClick={() => void sendMessage(prompt)}
              className="rounded-md border border-stone-700 bg-stone-950 px-2 py-1 text-left text-[11px] text-stone-400 hover:border-amber-800/50 hover:text-stone-200 disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>
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
            placeholder="Ask how to approach a task — not “write the code for me”…"
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

      {cards.length > 0 && (
        <div className="max-h-40 shrink-0 overflow-y-auto border-t border-stone-800 p-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-stone-500">
            Concept cards
          </p>
          <ul className="space-y-2">
            {cards.map((card) => (
              <li
                key={card.id}
                className="rounded-lg border border-stone-800 bg-stone-950/80 p-2 text-xs"
              >
                <p className="font-medium text-stone-200">{card.name}</p>
                <p className="mt-1 text-stone-500">{card.why_it_matters}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
