import type { GraphProgressRead } from "@/lib/types";

export function progressDetail(progress?: GraphProgressRead | null): string {
  if (!progress) return "";
  const parts: string[] = [];
  if (progress.questions_total) {
    parts.push(
      `${progress.questions_done ?? 0}/${progress.questions_total} questions`,
    );
  }
  if (progress.practice_total) {
    parts.push(
      `${progress.practice_done ?? 0}/${progress.practice_total} practice`,
    );
  }
  return parts.join(" · ");
}

export function ConceptProgressBar({
  progress,
  label,
  compact = false,
}: {
  progress?: GraphProgressRead | null;
  label?: string;
  compact?: boolean;
}) {
  if (!progress || !progress.total) return null;
  const percent = Math.max(0, Math.min(100, Math.round(progress.percent || 0)));
  const detail = progressDetail(progress);
  return (
    <div className={compact ? "" : "mt-2"}>
      <div className="flex items-center justify-between gap-2 text-[11px]">
        <span className="truncate text-stone-400">{label}</span>
        <span className="shrink-0 font-medium tabular-nums text-amber-400">
          {percent}%
        </span>
      </div>
      <div
        className={`mt-1 overflow-hidden rounded-full bg-stone-800 ${compact ? "h-1" : "h-1.5"}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label={label || "Concept progress"}
      >
        <div
          className="h-full rounded-full bg-amber-500 transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      {!compact && detail ? (
        <p className="mt-1 text-[10px] text-stone-600">{detail}</p>
      ) : null}
    </div>
  );
}
