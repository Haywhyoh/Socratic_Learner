"use client";

import {
  ChevronDown,
  ChevronRight,
  FileCode,
  Folder,
  FolderOpen,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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

interface FileTreeProps {
  entries: SandboxFileEntry[];
  activePath: string | null;
  onSelectFile: (path: string) => void;
}

export function FileTree({ entries, activePath, onSelectFile }: FileTreeProps) {
  const tree = useMemo(() => buildFileTree(entries), [entries]);
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    collectAncestorDirs(activePath),
  );

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

  const toggleDir = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  if (tree.length === 0) {
    return (
      <p className="px-2 py-2 text-xs text-stone-600">No files yet</p>
    );
  }

  return (
    <ul className="space-y-0.5" role="tree">
      {tree.map((node) => (
        <TreeItem
          key={node.path}
          node={node}
          depth={0}
          activePath={activePath}
          expanded={expanded}
          onToggle={toggleDir}
          onSelectFile={onSelectFile}
        />
      ))}
    </ul>
  );
}

interface TreeItemProps {
  node: FileTreeNode;
  depth: number;
  activePath: string | null;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelectFile: (path: string) => void;
}

function TreeItem({
  node,
  depth,
  activePath,
  expanded,
  onToggle,
  onSelectFile,
}: TreeItemProps) {
  const isOpen = expanded.has(node.path);
  const paddingLeft = 8 + depth * 12;

  if (node.isDir) {
    return (
      <li role="treeitem" aria-expanded={isOpen}>
        <button
          type="button"
          onClick={() => onToggle(node.path)}
          style={{ paddingLeft }}
          className="flex w-full items-center gap-1 rounded px-1 py-1 text-left text-xs text-stone-400 hover:bg-stone-900 hover:text-stone-200"
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
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen && node.children.length > 0 && (
          <ul className="space-y-0.5" role="group">
            {node.children.map((child) => (
              <TreeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                activePath={activePath}
                expanded={expanded}
                onToggle={onToggle}
                onSelectFile={onSelectFile}
              />
            ))}
          </ul>
        )}
      </li>
    );
  }

  const active = activePath === node.path;

  return (
    <li role="treeitem">
      <button
        type="button"
        onClick={() => onSelectFile(node.path)}
        style={{ paddingLeft }}
        className={`flex w-full items-center gap-1.5 rounded px-1 py-1 text-left text-xs ${
          active
            ? "bg-stone-800 text-amber-200"
            : "text-stone-400 hover:bg-stone-900 hover:text-stone-200"
        }`}
      >
        <span className="w-3 shrink-0" />
        <FileCode className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{node.name}</span>
      </button>
    </li>
  );
}
