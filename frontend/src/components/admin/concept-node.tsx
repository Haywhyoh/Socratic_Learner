"use client";

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

export type ConceptNodeType = Node<{ label: string; category: string }, "concept">;

export function ConceptNode({ data, selected }: NodeProps<ConceptNodeType>) {
  return (
    <div
      className={`min-w-[180px] rounded-xl border px-3 py-2 shadow-sm ${
        selected
          ? "border-amber-400 bg-stone-800"
          : "border-stone-700 bg-stone-900"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-amber-500" />
      <p className="text-[10px] uppercase tracking-wide text-amber-600/90">
        {data.category}
      </p>
      <p className="mt-1 max-w-[200px] truncate text-sm font-medium text-stone-100">
        {data.label}
      </p>
      <Handle type="source" position={Position.Right} className="!bg-amber-500" />
    </div>
  );
}
