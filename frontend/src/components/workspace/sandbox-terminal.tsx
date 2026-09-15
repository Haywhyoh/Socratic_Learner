"use client";

import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/types";
import "@xterm/xterm/css/xterm.css";

export interface SandboxTerminalHandle {
  echo: (text: string) => void;
  runCommand: (command: string) => Promise<void>;
  focus: () => void;
}

interface SandboxTerminalProps {
  userProjectId: number;
  onFsMutated?: () => void;
}

function promptLabel(cwd: string): string {
  const loc = cwd || "~";
  return `\r\n\x1b[33mlearner\x1b[0m:\x1b[36m${loc}\x1b[0m$ `;
}

function normalizeCwd(parts: string[]): string {
  const out: string[] = [];
  for (const part of parts) {
    if (!part || part === ".") continue;
    if (part === "..") {
      out.pop();
      continue;
    }
    out.push(part);
  }
  return out.join("/");
}

export const SandboxTerminal = forwardRef<
  SandboxTerminalHandle,
  SandboxTerminalProps
>(function SandboxTerminal({ userProjectId, onFsMutated }, ref) {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const lineRef = useRef("");
  const historyRef = useRef<string[]>([]);
  const historyIdxRef = useRef(-1);
  const cwdRef = useRef("");
  const runningRef = useRef(false);
  const onFsMutatedRef = useRef(onFsMutated);
  onFsMutatedRef.current = onFsMutated;

  const writePrompt = useCallback(() => {
    termRef.current?.write(promptLabel(cwdRef.current));
  }, []);

  const replaceLine = useCallback((next: string) => {
    const term = termRef.current;
    if (!term) return;
    while (lineRef.current.length > 0) {
      lineRef.current = lineRef.current.slice(0, -1);
      term.write("\b \b");
    }
    lineRef.current = next;
    if (next) term.write(next);
  }, []);

  const echo = useCallback((text: string) => {
    const term = termRef.current;
    if (!term) return;
    term.write("\r\n" + text.replace(/\r?\n/g, "\r\n"));
  }, []);

  const execute = useCallback(
    async (raw: string) => {
      const term = termRef.current;
      if (!term || runningRef.current) return;
      const command = raw.trim();
      if (!command) {
        writePrompt();
        return;
      }

      if (command === "clear" || command === "cls") {
        term.clear();
        writePrompt();
        return;
      }

      if (command === "help") {
        term.writeln("");
        term.writeln("Sandbox terminal — one allowlisted command per line.");
        term.writeln("Examples:");
        term.writeln("  ls -la");
        term.writeln("  mkdir -p lib");
        term.writeln("  touch server.js");
        term.writeln("  node server.js");
        term.writeln("  node --test");
        term.writeln("  cd lib   (client-side cwd)");
        term.writeln("  clear");
        term.writeln("");
        term.writeln(
          "Note: no network in the sandbox. Node 20 is preinstalled. No Express.",
        );
        term.writeln(
          "Long-running servers stop after the sandbox timeout (smoke-test only).",
        );
        term.writeln(
          "If you see a Docker error: start Colima/Docker on your Mac (host), not here.",
        );
        term.writeln(
          "  colima start && cd backend && docker build -t socratic-sandbox-node:latest sandbox",
        );
        writePrompt();
        return;
      }

      if (command === "pwd") {
        term.writeln("");
        term.writeln(`/workspace${cwdRef.current ? `/${cwdRef.current}` : ""}`);
        writePrompt();
        return;
      }

      if (command === "cd" || command.startsWith("cd ")) {
        const arg = command === "cd" ? "" : command.slice(3).trim();
        if (!arg || arg === "~" || arg === "/") {
          cwdRef.current = "";
          writePrompt();
          return;
        }
        const joined = arg.startsWith("/")
          ? arg.replace(/^\/+/, "").replace(/^workspace\/?/, "")
          : normalizeCwd([
              ...(cwdRef.current ? cwdRef.current.split("/") : []),
              ...arg.split("/"),
            ]);
        cwdRef.current = joined;
        writePrompt();
        return;
      }

      runningRef.current = true;
      try {
        const res = await api.runSandbox(userProjectId, {
          command,
          cwd: cwdRef.current || null,
        });
        const chunks = [res.stdout, res.stderr]
          .filter(Boolean)
          .join("\n")
          .trimEnd();
        if (chunks) {
          term.write("\r\n" + chunks.replace(/\r?\n/g, "\r\n"));
        }
        if (res.timed_out) {
          term.write(
            "\r\n\x1b[33m[timed out — process stopped by sandbox]\x1b[0m",
          );
        } else if (res.exit_code !== 0) {
          term.write(`\r\n\x1b[31m[exit ${res.exit_code}]\x1b[0m`);
        }
        if (res.mutates_fs) {
          onFsMutatedRef.current?.();
        }
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "Command failed";
        term.write(`\r\n\x1b[31m${msg}\x1b[0m`);
      } finally {
        runningRef.current = false;
        writePrompt();
      }
    },
    [userProjectId, writePrompt],
  );

  useImperativeHandle(
    ref,
    () => ({
      echo,
      runCommand: async (command: string) => {
        const term = termRef.current;
        if (!term) return;
        term.write(`\r\n$ ${command}`);
        await execute(command);
      },
      focus: () => termRef.current?.focus(),
    }),
    [echo, execute],
  );

  useEffect(() => {
    if (!hostRef.current || termRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
      theme: {
        background: "#0c0a09",
        foreground: "#e7e5e4",
        cursor: "#f59e0b",
        selectionBackground: "#44403c",
      },
      convertEol: true,
      scrollback: 2000,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current);
    fit.fit();
    termRef.current = term;

    term.writeln(
      "\x1b[1mSocratic sandbox\x1b[0m — type \x1b[33mhelp\x1b[0m for commands.",
    );
    term.write(promptLabel(""));

    const onData = term.onData((data) => {
      if (runningRef.current) return;

      if (data === "\r") {
        const line = lineRef.current;
        lineRef.current = "";
        if (line.trim()) {
          historyRef.current.push(line);
          historyIdxRef.current = historyRef.current.length;
        }
        void execute(line);
        return;
      }

      if (data === "\x7f" || data === "\b") {
        if (lineRef.current.length > 0) {
          lineRef.current = lineRef.current.slice(0, -1);
          term.write("\b \b");
        }
        return;
      }

      if (data === "\u0003") {
        lineRef.current = "";
        term.write("^C");
        writePrompt();
        return;
      }

      if (data === "\u000c") {
        term.clear();
        writePrompt();
        if (lineRef.current) term.write(lineRef.current);
        return;
      }

      if (data === "\x1b[A") {
        if (historyRef.current.length === 0) return;
        historyIdxRef.current = Math.max(0, historyIdxRef.current - 1);
        replaceLine(historyRef.current[historyIdxRef.current] ?? "");
        return;
      }

      if (data === "\x1b[B") {
        if (historyRef.current.length === 0) return;
        historyIdxRef.current = Math.min(
          historyRef.current.length,
          historyIdxRef.current + 1,
        );
        const next =
          historyIdxRef.current >= historyRef.current.length
            ? ""
            : (historyRef.current[historyIdxRef.current] ?? "");
        replaceLine(next);
        return;
      }

      if (data.startsWith("\x1b")) return;

      for (const ch of data) {
        const code = ch.charCodeAt(0);
        if (code < 32) continue;
        lineRef.current += ch;
        term.write(ch);
      }
    });

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(hostRef.current);

    return () => {
      onData.dispose();
      window.removeEventListener("resize", onResize);
      ro.disconnect();
      term.dispose();
      termRef.current = null;
    };
  }, [execute, replaceLine, writePrompt]);

  return (
    <div className="flex h-full min-h-0 flex-col border-t border-stone-800 bg-stone-950">
      <div className="flex items-center justify-between border-b border-stone-800 px-3 py-1.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-stone-500">
          Terminal
        </p>
        <p className="text-[10px] text-stone-600">
          allowlisted cmds · no network · timeout-limited
        </p>
      </div>
      <div
        ref={hostRef}
        className="min-h-0 flex-1 px-2 py-1 [&_.xterm]:h-full"
        onClick={() => termRef.current?.focus()}
      />
    </div>
  );
});
