"use client";

import { Lightbulb, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ConceptCardRead, MentorTurnRead } from "@/lib/types";

interface CoachPanelProps {
  userProjectId: number;
  userMilestoneId: number | null;
  initialReply?: string | null;
  initialQuestion?: string | null;
  initialTurns?: MentorTurnRead[];
  initialCards?: ConceptCardRead[];
}

export function CoachPanel({
  userProjectId,
  userMilestoneId,
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
  const [hintMeta, setHintMeta] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns]);

  const sendMessage = useCallback(async () => {
    const trimmed = message.trim();
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
      if (res.cards.length) setCards(res.cards);
    } finally {
      setSending(false);
    }
  }, [message, sending, userProjectId]);

  const requestHint = useCallback(async () => {
    if (!userMilestoneId || hintLoading) return;
    setHintLoading(true);
    setHintMeta(null);
    try {
      const res = await api.requestHint(userMilestoneId);
      if (res.hint_blocked_reason) {
        setHintMeta(res.hint_blocked_reason);
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

  return (
    <div className="flex h-full flex-col border-l border-stone-800 bg-stone-900/50">
      <div className="border-b border-stone-800 px-4 py-3">
        <h2 className="font-serif text-lg text-stone-100">Senior Engineer</h2>
        <p className="text-xs text-stone-500">
          Think first — questions before answers.
        </p>
      </div>

      {currentQuestion && (
        <div className="border-b border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-100/90">
          <span className="text-xs font-medium uppercase tracking-wide text-amber-500">
            Checkpoint
          </span>
          <p className="mt-1">{currentQuestion}</p>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <p className="text-sm text-stone-500">
            Share what you&apos;ve tried, your assumptions, or where you&apos;re
            stuck. The coach won&apos;t paste a full solution.
          </p>
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
            {turn.content}
          </div>
        ))}
      </div>

      {hintMeta && (
        <p className="px-4 pb-2 text-xs text-amber-600/90">{hintMeta}</p>
      )}

      <div className="space-y-2 border-t border-stone-800 p-3">
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            className="shrink-0 text-xs"
            disabled={!userMilestoneId || hintLoading}
            onClick={requestHint}
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
                void sendMessage();
              }
            }}
            rows={2}
            placeholder="Your thinking, not “write it for me”…"
            className="flex-1 resize-none rounded-lg border border-stone-700 bg-stone-950 px-3 py-2 text-sm text-stone-100 placeholder:text-stone-600 focus:border-amber-700 focus:outline-none"
          />
          <Button
            type="button"
            className="self-end"
            disabled={sending || !message.trim()}
            onClick={() => void sendMessage()}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {cards.length > 0 && (
        <div className="max-h-48 overflow-y-auto border-t border-stone-800 p-3">
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
