import type { GraphEdge, GraphNode, PathStep } from "@/lib/types";

import { EDGE_TYPES, NODE_TYPES } from "@/components/graph/constants";

/**
 * Pure helpers behind the graph page: API param building, focus-mode
 * filtering, search matching and shortest-path highlighting. All unit-tested
 * directly (no React Flow required).
 */

export type GraphQueryParams = {
  limit: number;
  node_types?: string;
  edge_types?: string;
};

/**
 * Chips act as an "only show these" filter: an empty (or full) selection
 * means "all types", so the param is omitted and the server default applies.
 */
export function buildGraphParams(
  nodeTypes: string[],
  edgeTypes: string[],
  limit: number,
): GraphQueryParams {
  const params: GraphQueryParams = { limit };
  if (nodeTypes.length > 0 && nodeTypes.length < NODE_TYPES.length) {
    params.node_types = [...nodeTypes].sort().join(",");
  }
  if (edgeTypes.length > 0 && edgeTypes.length < EDGE_TYPES.length) {
    params.edge_types = [...edgeTypes].sort().join(",");
  }
  return params;
}

/** The node itself plus every node it shares an edge with. */
export function neighborIds(nodeId: string, edges: GraphEdge[]): Set<string> {
  const ids = new Set<string>([nodeId]);
  for (const edge of edges) {
    if (edge.source === nodeId) ids.add(edge.target);
    if (edge.target === nodeId) ids.add(edge.source);
  }
  return ids;
}

/**
 * Focus mode: keep only `focusId` + direct neighbors (and edges fully inside
 * that set). With no focus, everything is visible.
 */
export function visibleElements(
  nodes: GraphNode[],
  edges: GraphEdge[],
  focusId: string | null,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (!focusId) return { nodes, edges };
  const keep = neighborIds(focusId, edges);
  return {
    nodes: nodes.filter((n) => keep.has(n.id)),
    edges: edges.filter((e) => keep.has(e.source) && keep.has(e.target)),
  };
}

/**
 * Best match for a search query: exact label match wins, then prefix match,
 * then substring; ties broken alphabetically so results are deterministic.
 */
export function matchNode(nodes: GraphNode[], query: string): GraphNode | null {
  const q = query.trim().toLowerCase();
  if (!q) return null;
  const sorted = [...nodes].sort((a, b) => a.label.localeCompare(b.label));
  return (
    sorted.find((n) => n.label.toLowerCase() === q) ??
    sorted.find((n) => n.label.toLowerCase().startsWith(q)) ??
    sorted.find((n) => n.label.toLowerCase().includes(q)) ??
    null
  );
}

export interface PathHighlight {
  nodeIds: Set<string>;
  edgeIds: Set<string>;
}

/** Node/edge id sets to highlight for a returned shortest path. */
export function pathHighlight(path: PathStep[]): PathHighlight {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();
  for (const step of path) {
    nodeIds.add(step.node.id);
    if (step.edge) edgeIds.add(step.edge.id);
  }
  return { nodeIds, edgeIds };
}

/** "A —owns→ B —uses→ C" style summary of a path. */
export function pathSummary(path: PathStep[]): string {
  return path
    .map((step) =>
      step.edge ? `—${step.edge.type}→ ${step.node.label}` : step.node.label,
    )
    .join(" ");
}

/** Route for a node's underlying record, when the ref is navigable. */
export function nodeRoute(node: GraphNode): string | null {
  if (!node.ref) return null;
  switch (node.type) {
    case "context_packet":
      return `/packets/${node.ref}`;
    case "agent_run":
      return `/agent-runs/${node.ref}`;
    case "doc":
    case "adr":
    case "pr":
    case "ticket":
    case "incident":
      return `/explorer/documents/${node.ref}`;
    default:
      return null;
  }
}
