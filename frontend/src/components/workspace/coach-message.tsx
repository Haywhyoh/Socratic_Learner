"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Normalize coach text before markdown (backticks in prose, loose URLs). */
export function prepareCoachMarkdown(raw: string): string {
  let text = raw.trim();
  // Smart quotes from some models → straight quotes for cleaner display
  text = text.replace(/[\u201c\u201d]/g, '"').replace(/[\u2018\u2019]/g, "'");
  return text;
}

const components: Components = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 leading-relaxed text-stone-300">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-stone-100">{children}</strong>
  ),
  em: ({ children }) => <em className="text-stone-400">{children}</em>,
  ul: ({ children }) => (
    <ul className="mb-2 list-disc space-y-1 pl-5 text-stone-300">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 list-decimal space-y-1 pl-5 text-stone-300">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => (
    <h3 className="mb-2 mt-3 first:mt-0 font-serif text-base text-stone-100">
      {children}
    </h3>
  ),
  h2: ({ children }) => (
    <h4 className="mb-2 mt-3 first:mt-0 text-sm font-semibold text-stone-100">
      {children}
    </h4>
  ),
  h3: ({ children }) => (
    <h4 className="mb-1.5 mt-2 first:mt-0 text-sm font-medium text-stone-200">
      {children}
    </h4>
  ),
  hr: () => <hr className="my-3 border-stone-700" />,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="break-all text-amber-400 underline decoration-amber-600/50 underline-offset-2 hover:text-amber-300"
    >
      {children}
    </a>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <code className={`${className ?? ""} text-stone-200`} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded bg-stone-800 px-1.5 py-0.5 font-mono text-[0.85em] text-amber-200/90"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded-lg border border-stone-700 bg-stone-900/90 p-3 font-mono text-xs leading-relaxed text-stone-200">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 border-amber-700/50 pl-3 text-stone-400">
      {children}
    </blockquote>
  ),
};

interface CoachMessageContentProps {
  content: string;
}

export function CoachMessageContent({ content }: CoachMessageContentProps) {
  const md = prepareCoachMarkdown(content);
  return (
    <div className="coach-markdown text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {md}
      </ReactMarkdown>
    </div>
  );
}
