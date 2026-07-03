import type { GraphEdge, GraphNode } from "@/lib/types";

/**
 * Deterministic, force-free graph layout: nodes are grouped by type into
 * circular clusters, and the clusters themselves sit on a ring around the
 * canvas center. Same input always yields the same output (pure function).
 */

export interface NodePosition {
  x: number;
  y: number;
}

const CENTER_X = 0;
const CENTER_Y = 0;
/** Radial spacing between rings inside a cluster. */
const RING_SPACING = 90;
/** Padding added between neighboring clusters on the outer ring. */
const CLUSTER_GAP = 120;

/** Radius a cluster of `count` nodes needs (grows with sqrt of count). */
export function clusterRadius(count: number): number {
  if (count <= 1) return 40;
  return RING_SPACING * Math.ceil(solveRingCount(count));
}

/** Number of concentric rings needed for `count` nodes (1 center + 8k per ring). */
function solveRingCount(count: number): number {
  let remaining = count - 1;
  let rings = 0;
  while (remaining > 0) {
    rings += 1;
    remaining -= rings * 8;
  }
  return Math.max(rings, 1);
}

export function layoutNodes(
  nodes: GraphNode[],
  _edges: GraphEdge[],
): Record<string, NodePosition> {
  const positions: Record<string, NodePosition> = {};
  if (nodes.length === 0) return positions;

  // Group nodes by type; sort groups by size desc then type asc so the
  // ordering (and therefore the layout) is stable.
  const groups = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const list = groups.get(node.type);
    if (list) list.push(node);
    else groups.set(node.type, [node]);
  }
  const clusters = [...groups.entries()].sort(
    (a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]),
  );

  // Ring radius: big enough that neighboring clusters don't overlap.
  const circumference = clusters.reduce(
    (sum, [, members]) => sum + 2 * clusterRadius(members.length) + CLUSTER_GAP,
    0,
  );
  const ringRadius =
    clusters.length === 1 ? 0 : Math.max(320, circumference / (2 * Math.PI));

  clusters.forEach(([, members], clusterIndex) => {
    const angle = (2 * Math.PI * clusterIndex) / clusters.length - Math.PI / 2;
    const cx = CENTER_X + ringRadius * Math.cos(angle);
    const cy = CENTER_Y + ringRadius * Math.sin(angle);

    // Highest-degree nodes sit in the middle of their cluster.
    const ordered = [...members].sort(
      (a, b) => b.degree - a.degree || a.id.localeCompare(b.id),
    );

    let placed = 0;
    let ring = 0;
    while (placed < ordered.length) {
      if (ring === 0) {
        positions[ordered[0].id] = { x: cx, y: cy };
        placed = 1;
        ring = 1;
        continue;
      }
      const capacity = ring * 8;
      const slice = ordered.slice(placed, placed + capacity);
      const r = ring * RING_SPACING;
      slice.forEach((node, i) => {
        const theta = (2 * Math.PI * i) / slice.length + ring * 0.35;
        positions[node.id] = {
          x: cx + r * Math.cos(theta),
          y: cy + r * Math.sin(theta),
        };
      });
      placed += slice.length;
      ring += 1;
    }
  });

  return positions;
}
