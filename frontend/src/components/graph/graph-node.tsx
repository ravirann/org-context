import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { memo } from "react";

import { nodeTypeMeta } from "@/components/graph/constants";
import type { GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface EntityNodeData {
  entity: GraphNode;
  /** True when this node matches the toolbar search or is on the found path. */
  highlighted: boolean;
  /** True when a found path is shown and this node is not on it. */
  dimmed: boolean;
  [key: string]: unknown;
}

export type EntityFlowNode = Node<EntityNodeData, "entity">;

/**
 * Compact card rendered for every graph node: type icon + label with a
 * type-colored left border; red ring when conflicted, amber dashed border
 * when stale.
 */
export const GraphNodeCard = memo(function GraphNodeCard({
  data,
}: NodeProps<EntityFlowNode>) {
  const { entity, highlighted, dimmed } = data;
  const meta = nodeTypeMeta(entity.type);
  const Icon = meta.icon;

  return (
    <div
      data-testid={`graph-node-${entity.id}`}
      data-highlighted={highlighted || undefined}
      data-dimmed={dimmed || undefined}
      title={`${meta.label}: ${entity.label}`}
      className={cn(
        "flex w-40 items-center gap-1.5 rounded-md border bg-card px-2 py-1.5 text-card-foreground shadow-sm transition-opacity",
        "border-l-4",
        entity.stale && "border-dashed border-amber-500/70",
        entity.conflicted && "ring-2 ring-red-500/80",
        highlighted && "ring-2 ring-ring",
        dimmed && "opacity-25",
      )}
      style={{ borderLeftColor: meta.color }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !min-h-0 !min-w-0 !border-0 !bg-transparent"
        isConnectable={false}
      />
      <Icon
        className="size-3.5 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[11px] font-medium leading-tight">
          {entity.label}
        </span>
        <span className="block text-[9px] uppercase tracking-wide text-muted-foreground">
          {meta.label}
        </span>
      </span>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !min-h-0 !min-w-0 !border-0 !bg-transparent"
        isConnectable={false}
      />
    </div>
  );
});
