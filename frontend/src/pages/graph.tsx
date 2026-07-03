import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import {
  Crosshair,
  ExternalLink,
  Info,
  Route as RouteIcon,
  Waypoints,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  EDGE_TYPES,
  NODE_TYPES,
  nodeTypeMeta,
} from "@/components/graph/constants";
import {
  GraphNodeCard,
  type EntityFlowNode,
} from "@/components/graph/graph-node";
import {
  buildGraphParams,
  matchNode,
  nodeRoute,
  pathHighlight,
  pathSummary,
  visibleElements,
} from "@/components/graph/graph-utils";
import { layoutNodes } from "@/components/graph/layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Select } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useDebounce } from "@/hooks/use-debounce";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { GraphNode, GraphResponse, PathResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const FLOW_NODE_TYPES = { entity: GraphNodeCard };

const LIMIT_OPTIONS = [100, 300, 600];

/** Edge type labels only appear while hovering the edge. */
const EDGE_HOVER_CSS = `
[data-testid="graph-canvas"] .react-flow__edge .react-flow__edge-textwrapper { opacity: 0; transition: opacity 120ms ease; }
[data-testid="graph-canvas"] .react-flow__edge:hover .react-flow__edge-textwrapper,
[data-testid="graph-canvas"] .react-flow__edge.selected .react-flow__edge-textwrapper { opacity: 1; }
`;

export default function GraphPage() {
  usePageTitle("Relationship Graph");
  return (
    <>
      <PageHeader
        title="Relationship Graph"
        description="Entities across the org and how they connect."
      />
      <div data-testid="page-graph">
        <ReactFlowProvider>
          <GraphExplorer />
        </ReactFlowProvider>
      </div>
    </>
  );
}

function GraphExplorer() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { setCenter } = useReactFlow();
  const { data: me } = useMe();

  const [nodeTypes, setNodeTypes] = useState<string[]>([]);
  const [edgeTypes, setEdgeTypes] = useState<string[]>([]);
  const [limit, setLimit] = useState(300);
  const [search, setSearch] = useState(() => searchParams.get("q") ?? "");
  const debouncedSearch = useDebounce(search, 200);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [pathMode, setPathMode] = useState(false);
  const [pathFrom, setPathFrom] = useState<string | null>(null);
  const [pathTo, setPathTo] = useState<string | null>(null);
  const [legendOpen, setLegendOpen] = useState(false);

  const params = useMemo(
    () => buildGraphParams(nodeTypes, edgeTypes, limit),
    [nodeTypes, edgeTypes, limit],
  );

  const graphQuery = useQuery({
    queryKey: queryKeys.graph(params),
    queryFn: () => api.get<GraphResponse>("/v1/relationships/graph", params),
  });

  const pathReady = pathFrom !== null && pathTo !== null;
  const pathQuery = useQuery({
    queryKey: queryKeys.path(pathFrom ?? "", pathTo ?? ""),
    queryFn: () =>
      api.get<PathResponse>("/v1/relationships/path", {
        from_id: pathFrom,
        to_id: pathTo,
      }),
    enabled: pathReady,
  });

  useEffect(() => {
    if (pathQuery.data && !pathQuery.data.found) {
      toast({
        title: "No path found",
        description: "The two selected nodes are not connected.",
        variant: "info",
      });
    }
  }, [pathQuery.data, toast]);

  const graph = graphQuery.data;

  const positions = useMemo(
    () => (graph ? layoutNodes(graph.nodes, graph.edges) : {}),
    [graph],
  );

  const visible = useMemo(
    () =>
      graph
        ? visibleElements(graph.nodes, graph.edges, focusId)
        : { nodes: [] as GraphNode[], edges: [] },
    [graph, focusId],
  );

  const highlight = useMemo(
    () => (pathQuery.data?.found ? pathHighlight(pathQuery.data.path) : null),
    [pathQuery.data],
  );

  const searched = useMemo(
    () => matchNode(visible.nodes, debouncedSearch),
    [visible.nodes, debouncedSearch],
  );

  // Center the viewport on the search match.
  useEffect(() => {
    if (!searched) return;
    const pos = positions[searched.id];
    if (pos) setCenter(pos.x, pos.y, { zoom: 1.3, duration: 300 });
  }, [searched, positions, setCenter]);

  // Escape resets focus mode, path picks and selection.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setFocusId(null);
      setPathFrom(null);
      setPathTo(null);
      setSelectedId(null);
      setLegendOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const flowNodes: EntityFlowNode[] = useMemo(
    () =>
      visible.nodes.map((node) => ({
        id: node.id,
        type: "entity" as const,
        position: positions[node.id] ?? { x: 0, y: 0 },
        data: {
          entity: node,
          highlighted:
            searched?.id === node.id ||
            (highlight?.nodeIds.has(node.id) ?? false),
          dimmed: highlight ? !highlight.nodeIds.has(node.id) : false,
        },
      })),
    [visible.nodes, positions, searched, highlight],
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      visible.edges.map((edge) => {
        const onPath = highlight?.edgeIds.has(edge.id) ?? false;
        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type,
          animated: onPath,
          markerEnd: { type: MarkerType.ArrowClosed },
          style: {
            opacity: highlight && !onPath ? 0.15 : 1,
            strokeWidth: onPath ? 2 : 1,
          },
        };
      }),
    [visible.edges, highlight],
  );

  const selectedNode =
    graph?.nodes.find((node) => node.id === selectedId) ?? null;

  const resetPath = useCallback(() => {
    setPathFrom(null);
    setPathTo(null);
  }, []);

  const startPathAt = useCallback((nodeId: string) => {
    setPathMode(true);
    setPathFrom(nodeId);
    setPathTo(null);
  }, []);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      if (pathMode) {
        if (!pathFrom) {
          setPathFrom(node.id);
        } else if (!pathTo && node.id !== pathFrom) {
          setPathTo(node.id);
        } else {
          setPathFrom(node.id);
          setPathTo(null);
        }
        return;
      }
      if (selectedId === node.id) {
        // Second click on the selected node toggles focus mode.
        setFocusId(focusId === node.id ? null : node.id);
      } else {
        setSelectedId(node.id);
      }
    },
    [pathMode, pathFrom, pathTo, selectedId, focusId],
  );

  const onNodeDoubleClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const entity = graph?.nodes.find((n) => n.id === node.id);
      if (!entity) return;
      const route = nodeRoute(entity);
      if (route) navigate(route);
    },
    [graph, navigate],
  );

  const toggleType = (setter: typeof setNodeTypes) => (type: string) =>
    setter((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
    );
  const toggleNodeType = toggleType(setNodeTypes);
  const toggleEdgeType = toggleType(setEdgeTypes);

  /* ------------------------------- error states ------------------------------ */

  if (graphQuery.isError) {
    const error = graphQuery.error;
    if (isApiError(error) && error.status === 403) {
      return <PermissionDenied role={me?.role} />;
    }
    return (
      <ErrorState
        title="Failed to load the graph"
        message={isApiError(error) ? error.detail : String(error)}
        onRetry={() => void graphQuery.refetch()}
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* ------------------------------- toolbar -------------------------------- */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="Search nodes"
          placeholder="Search nodes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-56"
        />
        <Select
          aria-label="Node limit"
          value={String(limit)}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="w-32"
        >
          {LIMIT_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n} nodes
            </option>
          ))}
        </Select>
        <Button
          size="sm"
          variant={pathMode ? "default" : "outline"}
          aria-pressed={pathMode}
          onClick={() => {
            setPathMode((on) => !on);
            resetPath();
          }}
        >
          <RouteIcon aria-hidden="true" /> Path
        </Button>
        {focusId ? (
          <Button size="sm" variant="outline" onClick={() => setFocusId(null)}>
            <Waypoints aria-hidden="true" /> Show all
          </Button>
        ) : null}
        <div className="relative ml-auto">
          <Button
            size="sm"
            variant="outline"
            aria-expanded={legendOpen}
            onClick={() => setLegendOpen((open) => !open)}
          >
            <Info aria-hidden="true" /> Legend
          </Button>
          {legendOpen ? <LegendPopover /> : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1">
        <span className="mr-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Nodes
        </span>
        {NODE_TYPES.map((type) => {
          const meta = nodeTypeMeta(type);
          return (
            <FilterChip
              key={type}
              label={meta.label}
              color={meta.color}
              active={nodeTypes.includes(type)}
              onClick={() => toggleNodeType(type)}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <span className="mr-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Edges
        </span>
        {EDGE_TYPES.map((type) => (
          <FilterChip
            key={type}
            label={type}
            active={edgeTypes.includes(type)}
            onClick={() => toggleEdgeType(type)}
          />
        ))}
      </div>

      {/* ------------------------------ path strip ------------------------------ */}
      {pathMode ? (
        <div
          data-testid="path-strip"
          className="flex items-center gap-2 rounded-md border bg-card px-3 py-1.5 text-xs"
        >
          {pathQuery.data?.found ? (
            <span className="truncate font-mono" data-testid="path-summary">
              {pathSummary(pathQuery.data.path)}
            </span>
          ) : pathReady && pathQuery.data ? (
            <span className="text-muted-foreground">
              No path found between the selected nodes.
            </span>
          ) : (
            <span className="text-muted-foreground">
              {pathFrom
                ? "Node A picked — now click node B."
                : "Click node A, then node B to find the shortest path."}
            </span>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto"
            onClick={resetPath}
          >
            Clear
          </Button>
        </div>
      ) : null}

      {/* -------------------------------- canvas -------------------------------- */}
      {graphQuery.isPending ? (
        <Skeleton
          data-testid="graph-skeleton"
          className="h-[calc(100vh-12rem)] w-full"
        />
      ) : graph && graph.nodes.length === 0 ? (
        <EmptyState
          title="No graph data"
          description="No nodes match the current filters. Clear some filters or sync more sources."
        />
      ) : (
        <div className="flex gap-3">
          <div
            data-testid="graph-canvas"
            className="relative h-[calc(100vh-12rem)] min-w-0 flex-1 overflow-hidden rounded-lg border bg-card/40"
          >
            <style>{EDGE_HOVER_CSS}</style>
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={FLOW_NODE_TYPES}
              onNodeClick={onNodeClick}
              onNodeDoubleClick={onNodeDoubleClick}
              onPaneClick={() => setSelectedId(null)}
              nodesConnectable={false}
              fitView
              minZoom={0.05}
            >
              <Background variant={BackgroundVariant.Dots} gap={24} size={1} />
              <MiniMap pannable zoomable className="!bg-card" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          {selectedNode ? (
            <NodePanel
              node={selectedNode}
              focused={focusId === selectedNode.id}
              onClose={() => setSelectedId(null)}
              onFocus={() =>
                setFocusId(focusId === selectedNode.id ? null : selectedNode.id)
              }
              onStartPath={() => startPathAt(selectedNode.id)}
              onOpen={(route) => navigate(route)}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

/* -------------------------------- sub-components ------------------------------- */

interface FilterChipProps {
  label: string;
  active: boolean;
  color?: string;
  onClick: () => void;
}

function FilterChip({ label, active, color, onClick }: FilterChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] leading-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary bg-primary/10 text-primary"
          : "border-border text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      {color ? (
        <span
          className="size-2 rounded-full"
          style={{ background: color }}
          aria-hidden="true"
        />
      ) : null}
      {label}
    </button>
  );
}

function LegendPopover() {
  return (
    <div
      role="dialog"
      aria-label="Graph legend"
      data-testid="graph-legend"
      className="absolute right-0 z-30 mt-1 w-64 rounded-md border bg-card p-3 text-card-foreground shadow-lg"
    >
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Node types
      </p>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
        {NODE_TYPES.map((type) => {
          const meta = nodeTypeMeta(type);
          return (
            <li key={type} className="flex items-center gap-1.5 text-xs">
              <span
                className="size-2.5 shrink-0 rounded-sm"
                style={{ background: meta.color }}
                aria-hidden="true"
              />
              {meta.label}
            </li>
          );
        })}
      </ul>
      <Separator className="my-2" />
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        Markers
      </p>
      <ul className="flex flex-col gap-1 text-xs">
        <li className="flex items-center gap-1.5">
          <span
            className="size-2.5 shrink-0 rounded-sm ring-2 ring-red-500/80"
            aria-hidden="true"
          />
          Conflicted (red ring)
        </li>
        <li className="flex items-center gap-1.5">
          <span
            className="size-2.5 shrink-0 rounded-sm border border-dashed border-amber-500"
            aria-hidden="true"
          />
          Stale (amber dashed)
        </li>
      </ul>
    </div>
  );
}

interface NodePanelProps {
  node: GraphNode;
  focused: boolean;
  onClose: () => void;
  onFocus: () => void;
  onStartPath: () => void;
  onOpen: (route: string) => void;
}

function NodePanel({
  node,
  focused,
  onClose,
  onFocus,
  onStartPath,
  onOpen,
}: NodePanelProps) {
  const meta = nodeTypeMeta(node.type);
  const Icon = meta.icon;
  const route = nodeRoute(node);
  return (
    <aside
      data-testid="node-panel"
      aria-label="Selected node"
      className="flex w-60 shrink-0 flex-col gap-3 rounded-lg border bg-card p-3 text-card-foreground"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <Icon
            className="size-4 shrink-0"
            style={{ color: meta.color }}
            aria-hidden="true"
          />
          <span className="truncate text-sm font-medium">{node.label}</span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="size-6"
          aria-label="Close panel"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>
      </div>
      <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Type</dt>
        <dd>{meta.label}</dd>
        <dt className="text-muted-foreground">Degree</dt>
        <dd className="tabular-nums">{node.degree}</dd>
      </dl>
      <div className="flex flex-wrap gap-1">
        {node.stale ? <Badge variant="warning">Stale</Badge> : null}
        {node.conflicted ? (
          <Badge variant="destructive">Conflicted</Badge>
        ) : null}
        {!node.stale && !node.conflicted ? (
          <Badge variant="success">Healthy</Badge>
        ) : null}
      </div>
      <Separator />
      <div className="flex flex-col gap-1.5">
        <Button size="sm" variant="outline" onClick={onFocus}>
          <Crosshair aria-hidden="true" />
          {focused ? "Unfocus" : "Focus neighbors"}
        </Button>
        <Button size="sm" variant="outline" onClick={onStartPath}>
          <RouteIcon aria-hidden="true" /> Start path here
        </Button>
        {route ? (
          <Button size="sm" onClick={() => onOpen(route)}>
            <ExternalLink aria-hidden="true" /> Open source document
          </Button>
        ) : null}
      </div>
    </aside>
  );
}
