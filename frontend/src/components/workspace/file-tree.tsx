"use client";

import {
  ChevronDown,
  ChevronRight,
  FileCode,
  FilePlus,
  Folder,
  FolderOpen,
  FolderPlus,
  Pencil,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SandboxFileEntry } from "@/lib/types";

export interface FileTreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: FileTreeNode[];
}

export function buildFileTree(entries: SandboxFileEntry[]): FileTreeNode[] {
  type MutableNode = {
    name: string;
    path: string;
    isDir: boolean;
    children: Map<string, MutableNode>;
  };

  const root = new Map<string, MutableNode>();

  const ensureDir = (
    map: Map<string, MutableNode>,
    name: string,
    path: string,
  ): MutableNode => {
    let node = map.get(name);
    if (!node) {
      node = { name, path, isDir: true, children: new Map() };
      map.set(name, node);
    } else if (!node.isDir) {
      node.isDir = true;
    }
    return node;
  };

  for (const entry of entries) {
    const parts = entry.path.split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i]!;
      const path = parts.slice(0, i + 1).join("/");
      const isLast = i === parts.length - 1;

      if (isLast && !entry.is_dir) {
        const existing = current.get(name);
        if (existing) {
          existing.isDir = false;
        } else {
          current.set(name, {
            name,
            path,
            isDir: false,
            children: new Map(),
          });
        }
      } else {
        const dir = ensureDir(current, name, path);
        current = dir.children;
      }
    }
  }

  const toSorted = (map: Map<string, MutableNode>): FileTreeNode[] =>
    [...map.values()]
      .sort((a, b) => {
        if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map((node) => ({
        name: node.name,
        path: node.path,
        isDir: node.isDir,
        children: toSorted(node.children),
      }));

  return toSorted(root);
}

function collectAncestorDirs(path: string | null): Set<string> {
  const dirs = new Set<string>();
  if (!path) return dirs;
  const parts = path.split("/").filter(Boolean);
  for (let i = 1; i < parts.length; i++) {
    dirs.add(parts.slice(0, i).join("/"));
  }
  return dirs;
}

function parentDirOf(path: string | null): string {
  if (!path) return "";
  const parts = path.split("/").filter(Boolean);
  if (parts.length <= 1) return "";
  return parts.slice(0, -1).join("/");
}

/** Normalize a user-entered relative path; returns null if invalid. */
export function normalizeWorkspacePath(raw: string): string | null {
  const trimmed = raw.trim().replace(/^\/+/, "").replace(/\\/g, "/");
  if (!trimmed) return null;
  const parts = trimmed.split("/").filter((p) => p.length > 0);
  if (parts.length === 0) return null;
  if (parts.some((p) => p === "." || p === ".." || p.includes("\0"))) {
    return null;
  }
  return parts.join("/");
}

type EditorMode = "file" | "folder" | "rename";

interface FileTreeProps {
  entries: SandboxFileEntry[];
  activePath: string | null;
  onSelectFile: (path: string) => void;
  onCreateFile?: (path: string) => Promise<void> | void;
  onCreateFolder?: (path: string) => Promise<void> | void;
  onRenameFile?: (source: string, dest: string) => Promise<void> | void;
  onDeleteFile?: (path: string) => Promise<void> | void;
  busy?: boolean;
  filePlaceholder?: string;
}

export function FileTree({
  entries,
  activePath,
  onSelectFile,
  onCreateFile,
  onCreateFolder,
  onRenameFile,
  onDeleteFile,
  busy = false,
  filePlaceholder = "src/index.js",
}: FileTreeProps) {
  const tree = useMemo(() => buildFileTree(entries), [entries]);
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    collectAncestorDirs(activePath),
  );
  const [selectedDir, setSelectedDir] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<EditorMode | null>(null);
  const [editorSource, setEditorSource] = useState<string | null>(null);
  const [createValue, setCreateValue] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const ancestors = collectAncestorDirs(activePath);
    if (ancestors.size === 0) return;
    setExpanded((prev) => {
      let changed = false;
      const next = new Set(prev);
      for (const dir of ancestors) {
        if (!next.has(dir)) {
          next.add(dir);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [activePath]);

  useEffect(() => {
    if (editorMode) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editorMode]);

  const toggleDir = (path: string) => {
    setSelectedDir(path);
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const startCreate = (mode: "file" | "folder") => {
    if (busy || submitting) return;
    const base = selectedDir ?? parentDirOf(activePath);
    setEditorMode(mode);
    setEditorSource(null);
    setCreateValue(base ? `${base}/` : "");
    setCreateError(null);
  };

  const startRename = (path: string) => {
    if (busy || submitting || !onRenameFile) return;
    setEditorMode("rename");
    setEditorSource(path);
    setCreateValue(path);
    setCreateError(null);
  };

  const cancelCreate = () => {
    setEditorMode(null);
    setEditorSource(null);
    setCreateValue("");
    setCreateError(null);
  };

  const submitCreate = async () => {
    if (!editorMode || submitting) return;
    const path = normalizeWorkspacePath(createValue);
    if (!path) {
      setCreateError("Enter a valid relative path");
      return;
    }
    if (editorMode !== "rename" && entries.some((e) => e.path === path)) {
      setCreateError("Already exists");
      return;
    }
    if (
      editorMode === "rename" &&
      path !== editorSource &&
      entries.some((e) => e.path === path)
    ) {
      setCreateError("Already exists");
      return;
    }

    setSubmitting(true);
    setCreateError(null);
    try {
      if (editorMode === "file") {
        await onCreateFile?.(path);
      } else if (editorMode === "folder") {
        await onCreateFolder?.(path);
        setSelectedDir(path);
        setExpanded((prev) => new Set(prev).add(path));
      } else if (editorSource) {
        await onRenameFile?.(editorSource, path);
      }
      cancelCreate();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Could not update file");
    } finally {
      setSubmitting(false);
    }
  };

  const deletePath = async (path: string) => {
    if (busy || submitting || !onDeleteFile) return;
    const confirmed = window.confirm(`Delete ${path}? This cannot be undone.`);
    if (!confirmed) return;
    setSubmitting(true);
    setCreateError(null);
    try {
      await onDeleteFile(path);
      if (editorSource === path) cancelCreate();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Could not delete");
    } finally {
      setSubmitting(false);
    }
  };

  const canCreate = Boolean(onCreateFile || onCreateFolder);

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex items-center justify-between gap-1 px-1 pb-1">
        <p className="px-1 text-xs font-medium uppercase text-stone-600">
          Files
        </p>
        {canCreate && (
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              title="New file"
              aria-label="New file"
              disabled={busy || submitting || !onCreateFile}
              onClick={() => startCreate("file")}
              className="rounded p-1 text-stone-500 hover:bg-stone-900 hover:text-stone-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <FilePlus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              title="New folder"
              aria-label="New folder"
              disabled={busy || submitting || !onCreateFolder}
              onClick={() => startCreate("folder")}
              className="rounded p-1 text-stone-500 hover:bg-stone-900 hover:text-stone-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <FolderPlus className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {editorMode && (
        <div className="mb-1 space-y-1 px-1">
          <label className="block text-[10px] uppercase tracking-wide text-stone-600">
            {editorMode === "file"
              ? "New file path"
              : editorMode === "folder"
                ? "New folder path"
                : "Rename path"}
          </label>
          <input
            ref={inputRef}
            value={createValue}
            disabled={submitting}
            onChange={(e) => {
              setCreateValue(e.target.value);
              setCreateError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void submitCreate();
              } else if (e.key === "Escape") {
                e.preventDefault();
                cancelCreate();
              }
            }}
            placeholder={
              editorMode === "folder" ? "src/utils" : filePlaceholder
            }
            className="w-full rounded border border-stone-700 bg-stone-950 px-1.5 py-1 text-xs text-stone-200 outline-none focus:border-amber-700"
          />
          {createError && (
            <p className="text-[10px] text-red-400">{createError}</p>
          )}
          <div className="flex gap-1">
            <button
              type="button"
              disabled={submitting}
              onClick={() => void submitCreate()}
              className="rounded bg-stone-800 px-2 py-0.5 text-[10px] text-stone-200 hover:bg-stone-700 disabled:opacity-40"
            >
              {submitting
                ? "Working…"
                : editorMode === "rename"
                  ? "Rename"
                  : "Create"}
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={cancelCreate}
              className="rounded px-2 py-0.5 text-[10px] text-stone-500 hover:text-stone-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {!editorMode && createError ? (
        <p className="mb-1 px-1 text-[10px] text-red-400">{createError}</p>
      ) : null}

      {tree.length === 0 && !editorMode ? (
        <p className="px-2 py-2 text-xs text-stone-600">No files yet</p>
      ) : (
        <ul className="space-y-0.5" role="tree">
          {tree.map((node) => (
            <TreeItem
              key={node.path}
              node={node}
              depth={0}
              activePath={activePath}
              selectedDir={selectedDir}
              expanded={expanded}
              busy={busy || submitting}
              canRename={Boolean(onRenameFile)}
              canDelete={Boolean(onDeleteFile)}
              onToggle={toggleDir}
              onSelectFile={(path) => {
                setSelectedDir(parentDirOf(path) || null);
                onSelectFile(path);
              }}
              onRename={startRename}
              onDelete={(path) => void deletePath(path)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface TreeItemProps {
  node: FileTreeNode;
  depth: number;
  activePath: string | null;
  selectedDir: string | null;
  expanded: Set<string>;
  busy: boolean;
  canRename: boolean;
  canDelete: boolean;
  onToggle: (path: string) => void;
  onSelectFile: (path: string) => void;
  onRename: (path: string) => void;
  onDelete: (path: string) => void;
}

function RowActions({
  path,
  busy,
  canRename,
  canDelete,
  onRename,
  onDelete,
}: {
  path: string;
  busy: boolean;
  canRename: boolean;
  canDelete: boolean;
  onRename: (path: string) => void;
  onDelete: (path: string) => void;
}) {
  if (!canRename && !canDelete) return null;
  return (
    <span className="ml-auto flex shrink-0 items-center opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
      {canRename ? (
        <button
          type="button"
          title={`Rename ${path}`}
          aria-label={`Rename ${path}`}
          disabled={busy}
          onClick={(event) => {
            event.stopPropagation();
            onRename(path);
          }}
          className="rounded p-0.5 text-stone-500 hover:bg-stone-800 hover:text-stone-200 disabled:opacity-40"
        >
          <Pencil className="h-3 w-3" />
        </button>
      ) : null}
      {canDelete ? (
        <button
          type="button"
          title={`Delete ${path}`}
          aria-label={`Delete ${path}`}
          disabled={busy}
          onClick={(event) => {
            event.stopPropagation();
            onDelete(path);
          }}
          className="rounded p-0.5 text-stone-500 hover:bg-stone-800 hover:text-red-300 disabled:opacity-40"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      ) : null}
    </span>
  );
}

function TreeItem({
  node,
  depth,
  activePath,
  selectedDir,
  expanded,
  busy,
  canRename,
  canDelete,
  onToggle,
  onSelectFile,
  onRename,
  onDelete,
}: TreeItemProps) {
  const isOpen = expanded.has(node.path);
  const paddingLeft = 8 + depth * 12;
  const childProps = {
    depth: depth + 1,
    activePath,
    selectedDir,
    expanded,
    busy,
    canRename,
    canDelete,
    onToggle,
    onSelectFile,
    onRename,
    onDelete,
  };

  if (node.isDir) {
    const selected = selectedDir === node.path;
    return (
      <li role="treeitem" aria-expanded={isOpen}>
        <div
          style={{ paddingLeft }}
          className={`group flex w-full items-center gap-1 rounded px-1 py-1 text-xs hover:bg-stone-900 hover:text-stone-200 ${
            selected ? "bg-stone-900 text-amber-200" : "text-stone-400"
          }`}
        >
          <button
            type="button"
            onClick={() => onToggle(node.path)}
            className="flex min-w-0 flex-1 items-center gap-1 text-left"
          >
            {isOpen ? (
              <ChevronDown className="h-3 w-3 shrink-0 text-stone-600" />
            ) : (
              <ChevronRight className="h-3 w-3 shrink-0 text-stone-600" />
            )}
            {isOpen ? (
              <FolderOpen className="h-3.5 w-3.5 shrink-0 text-amber-600/80" />
            ) : (
              <Folder className="h-3.5 w-3.5 shrink-0 text-amber-700/70" />
            )}
            <span className="min-w-0 truncate">{node.name}</span>
          </button>
          <RowActions
            path={node.path}
            busy={busy}
            canRename={canRename}
            canDelete={canDelete}
            onRename={onRename}
            onDelete={onDelete}
          />
        </div>
        {isOpen && node.children.length > 0 && (
          <ul className="space-y-0.5" role="group">
            {node.children.map((child) => (
              <TreeItem key={child.path} node={child} {...childProps} />
            ))}
          </ul>
        )}
      </li>
    );
  }

  const active = activePath === node.path;

  return (
    <li role="treeitem">
      <div
        style={{ paddingLeft }}
        className={`group flex w-full items-center gap-1.5 rounded px-1 py-1 text-xs ${
          active
            ? "bg-stone-800 text-amber-200"
            : "text-stone-400 hover:bg-stone-900 hover:text-stone-200"
        }`}
      >
        <button
          type="button"
          onClick={() => onSelectFile(node.path)}
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
        >
          <span className="w-3 shrink-0" />
          <FileCode className="h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 truncate">{node.name}</span>
        </button>
        <RowActions
          path={node.path}
          busy={busy}
          canRename={canRename}
          canDelete={canDelete}
          onRename={onRename}
          onDelete={onDelete}
        />
      </div>
    </li>
  );
}
