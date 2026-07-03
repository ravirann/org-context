import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EDGE_TYPES, NODE_TYPES, nodeTypeMeta } from "@/components/graph/constants";
import {
  buildGraphParams,
  matchNode,
  neighborIds,
  nodeRoute,
  pathHighlight,
  pathSummary,
  visibleElements,
} from "@/components/graph/graph-utils";
import { layoutNodes } from "@/components/graph/layout";
import { useToastStore } from "@/components/ui/toast";
import GraphPage from "@/pages/graph";

import {
  graphFixture,
  meFixture,
  noPathFixture,
  pathFixture,
} from "../fixtures-graph";
import { mockFetchRoutes, mockResponse, renderWithProviders } from "../utils";

/* ----------------------- React Flow jsdom prerequisites ----------------------- */
// Per xyflow's testing guide: DOMMatrixReadOnly + element size getters. The
// global setup's afterEach unstubs globals, so re-stub before each test.

class DOMMatrixReadOnlyStub {
  m22: number;
  constructor(transform?: string) {
    const scale = transform?.match(/scale\(([\d.]+)\)/)?.[1];
    this.m22 = scale !== undefined ? Number(scale) : 1;
  }
}

Object.defineProperties(window.HTMLElement.prototype, {
  offsetHeight: {
    configurable: true,
    get(this: HTMLElement) {
      return Number.parseFloat(this.style.height) || 200;
    },
  },
  offsetWidth: {
    configurable: true,
    get(this: HTMLElement) {
      return Number.parseFloat(this.style.width) || 200;
    },
  },
});

(
  window.SVGElement.prototype as unknown as { getBBox: () => unknown }
).getBBox = () => ({ x: 0, y: 0, width: 0, height: 0 });

beforeEach(() => {
  vi.stubGlobal("DOMMatrixReadOnly", DOMMatrixReadOnlyStub);
  useToastStore.setState({ toasts: [] });
});

/* ------------------------------- pure functions ------------------------------- */

describe("layoutNodes", () => {
  it("is deterministic for the same input", () => {
    const a = layoutNodes(graphFixture.nodes, graphFixture.edges);
    const b = layoutNodes(graphFixture.nodes, graphFixture.edges);
    expect(a).toEqual(b);
  });

  it("positions every node with finite coordinates", () => {
    const positions = layoutNodes(graphFixture.nodes, graphFixture.edges);
    for (const node of graphFixture.nodes) {
      expect(positions[node.id]).toBeDefined();
      expect(Number.isFinite(positions[node.id].x)).toBe(true);
      expect(Number.isFinite(positions[node.id].y)).toBe(true);
    }
  });

  it("gives every node a distinct position", () => {
    const positions = layoutNodes(graphFixture.nodes, graphFixture.edges);
    const keys = new Set(
      Object.values(positions).map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`),
    );
    expect(keys.size).toBe(graphFixture.nodes.length);
  });

  it("clusters nodes of the same type closer together than other types", () => {
    const positions = layoutNodes(graphFixture.nodes, graphFixture.edges);
    const dist = (a: string, b: string) =>
      Math.hypot(
        positions[a].x - positions[b].x,
        positions[a].y - positions[b].y,
      );
    // the two docs sit in the same cluster
    expect(dist("n-doc-1", "n-doc-2")).toBeLessThan(dist("n-doc-1", "n-user-1"));
  });

  it("handles empty input", () => {
    expect(layoutNodes([], [])).toEqual({});
  });
});

describe("graph-utils", () => {
  it("buildGraphParams omits type params for empty or full selections", () => {
    expect(buildGraphParams([], [], 300)).toEqual({ limit: 300 });
    expect(buildGraphParams(NODE_TYPES, EDGE_TYPES, 100)).toEqual({
      limit: 100,
    });
  });

  it("buildGraphParams joins sorted subsets with commas", () => {
    expect(buildGraphParams(["service", "repo"], ["owns"], 600)).toEqual({
      limit: 600,
      node_types: "repo,service",
      edge_types: "owns",
    });
  });

  it("neighborIds returns the node plus direct neighbors", () => {
    const ids = neighborIds("n-repo-1", graphFixture.edges);
    expect(ids).toEqual(
      new Set(["n-repo-1", "n-team-1", "n-doc-1", "n-svc-1"]),
    );
  });

  it("visibleElements filters nodes and edges in focus mode", () => {
    const { nodes, edges } = visibleElements(
      graphFixture.nodes,
      graphFixture.edges,
      "n-user-1",
    );
    expect(nodes.map((n) => n.id).sort()).toEqual(["n-team-1", "n-user-1"]);
    expect(edges.map((e) => e.id)).toEqual(["e-2"]);
  });

  it("visibleElements is a no-op without focus", () => {
    const out = visibleElements(graphFixture.nodes, graphFixture.edges, null);
    expect(out.nodes).toHaveLength(graphFixture.nodes.length);
    expect(out.edges).toHaveLength(graphFixture.edges.length);
  });

  it("matchNode prefers exact, then prefix, then substring matches", () => {
    expect(matchNode(graphFixture.nodes, "payments")?.id).toBe("n-svc-1");
    expect(matchNode(graphFixture.nodes, "payments-")?.id).toBe("n-repo-1");
    expect(matchNode(graphFixture.nodes, "retries")?.id).toBe("n-doc-1");
    expect(matchNode(graphFixture.nodes, "")).toBeNull();
    expect(matchNode(graphFixture.nodes, "zzz")).toBeNull();
  });

  it("pathHighlight collects node and edge ids", () => {
    const { nodeIds, edgeIds } = pathHighlight(pathFixture.path);
    expect(nodeIds).toEqual(
      new Set(["n-user-1", "n-team-1", "n-repo-1", "n-doc-1"]),
    );
    expect(edgeIds).toEqual(new Set(["e-2", "e-1", "e-3"]));
  });

  it("pathSummary renders labels joined by edge types", () => {
    expect(pathSummary(pathFixture.path)).toBe(
      "Priya Nair —member_of→ Payments Squad —owns→ payments-api —references→ Payment retries runbook",
    );
  });

  it("nodeRoute maps refs to routes per node type", () => {
    expect(nodeRoute(graphFixture.nodes[4])).toBe(
      "/explorer/documents/0f1e2d3c-0000-4000-8000-000000000001",
    );
    expect(nodeRoute(graphFixture.nodes[6])).toBe(
      "/packets/0f1e2d3c-0000-4000-8000-00000000000a",
    );
    expect(nodeRoute(graphFixture.nodes[7])).toBe(
      "/agent-runs/0f1e2d3c-0000-4000-8000-00000000000b",
    );
    // repos have no navigable ref
    expect(nodeRoute(graphFixture.nodes[0])).toBeNull();
  });

  it("nodeTypeMeta falls back for unknown types", () => {
    expect(nodeTypeMeta("mystery").label).toBe("mystery");
    expect(nodeTypeMeta("repo").label).toBe("Repo");
  });
});

/* --------------------------------- page tests --------------------------------- */

function setup(overrides: Record<string, unknown> = {}, route = "/graph") {
  const fetchMock = mockFetchRoutes({
    "GET /v1/me": meFixture,
    "GET /v1/relationships/graph": graphFixture,
    "GET /v1/relationships/path": pathFixture,
    ...overrides,
  });
  const utils = renderWithProviders(<GraphPage />, { route, path: "/graph" });
  return { fetchMock, ...utils };
}

function graphCalls(fetchMock: ReturnType<typeof mockFetchRoutes>): string[] {
  return fetchMock.mock.calls
    .map((call) => String(call[0]))
    .filter((url) => url.includes("/v1/relationships/graph"));
}

describe("GraphPage", () => {
  it("renders every node returned by the API", async () => {
    setup();
    await screen.findByTestId("graph-node-n-repo-1");
    for (const node of graphFixture.nodes) {
      expect(screen.getByTestId(`graph-node-${node.id}`)).toBeInTheDocument();
    }
  });

  it("marks stale and conflicted nodes", async () => {
    setup();
    const stale = await screen.findByTestId("graph-node-n-doc-1");
    const conflicted = screen.getByTestId("graph-node-n-doc-2");
    expect(stale.className).toContain("border-dashed");
    expect(conflicted.className).toContain("ring-red-500");
  });

  it("shows a loading skeleton while the graph is pending", async () => {
    setup({ "GET /v1/relationships/graph": () => new Promise(() => {}) });
    expect(await screen.findByTestId("graph-skeleton")).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    const { fetchMock } = setup({
      "GET /v1/relationships/graph": mockResponse({ detail: "boom" }, 500),
    });
    await screen.findByText("Failed to load the graph");
    const before = graphCalls(fetchMock).length;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(graphCalls(fetchMock).length).toBeGreaterThan(before),
    );
  });

  it("shows PermissionDenied on 403", async () => {
    setup({
      "GET /v1/relationships/graph": mockResponse({ detail: "Forbidden" }, 403),
    });
    expect(await screen.findByText("Permission denied")).toBeInTheDocument();
  });

  it("shows an empty state when the graph has no nodes", async () => {
    setup({ "GET /v1/relationships/graph": { nodes: [], edges: [] } });
    expect(await screen.findByText("No graph data")).toBeInTheDocument();
  });

  it("re-queries with node_types when a node chip is toggled", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("graph-node-n-repo-1");
    fireEvent.click(screen.getByRole("button", { name: "Repo" }));
    await waitFor(() =>
      expect(
        graphCalls(fetchMock).some((url) => url.includes("node_types=repo")),
      ).toBe(true),
    );
  });

  it("re-queries with edge_types when an edge chip is toggled", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("graph-node-n-repo-1");
    fireEvent.click(screen.getByRole("button", { name: "owns" }));
    await waitFor(() =>
      expect(
        graphCalls(fetchMock).some((url) => url.includes("edge_types=owns")),
      ).toBe(true),
    );
  });

  it("re-queries when the limit changes", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("graph-node-n-repo-1");
    fireEvent.change(screen.getByLabelText("Node limit"), {
      target: { value: "600" },
    });
    await waitFor(() =>
      expect(
        graphCalls(fetchMock).some((url) => url.includes("limit=600")),
      ).toBe(true),
    );
  });

  it("highlights the matching node when searching", async () => {
    const user = userEvent.setup();
    setup();
    await screen.findByTestId("graph-node-n-user-1");
    await user.type(screen.getByLabelText("Search nodes"), "Priya");
    await waitFor(() =>
      expect(screen.getByTestId("graph-node-n-user-1")).toHaveAttribute(
        "data-highlighted",
        "true",
      ),
    );
  });

  it("initializes the search from the ?q= URL param", async () => {
    setup({}, "/graph?q=Priya%20Nair");
    await waitFor(() =>
      expect(screen.getByTestId("graph-node-n-user-1")).toHaveAttribute(
        "data-highlighted",
        "true",
      ),
    );
  });

  it("path mode fetches the shortest path and shows a summary", async () => {
    const { fetchMock } = setup();
    await screen.findByTestId("graph-node-n-user-1");
    fireEvent.click(screen.getByRole("button", { name: "Path" }));
    expect(screen.getByTestId("path-strip")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-node-n-user-1"));
    fireEvent.click(screen.getByTestId("graph-node-n-doc-1"));
    await waitFor(() => {
      const pathCall = fetchMock.mock.calls
        .map((call) => String(call[0]))
        .find((url) => url.includes("/v1/relationships/path"));
      expect(pathCall).toContain("from_id=n-user-1");
      expect(pathCall).toContain("to_id=n-doc-1");
    });
    const summary = await screen.findByTestId("path-summary");
    expect(summary.textContent).toContain("—owns→");
    // off-path nodes are dimmed
    expect(screen.getByTestId("graph-node-n-run-1")).toHaveAttribute(
      "data-dimmed",
      "true",
    );
  });

  it("toasts when no path is found", async () => {
    setup({ "GET /v1/relationships/path": noPathFixture });
    await screen.findByTestId("graph-node-n-user-1");
    fireEvent.click(screen.getByRole("button", { name: "Path" }));
    fireEvent.click(screen.getByTestId("graph-node-n-user-1"));
    fireEvent.click(screen.getByTestId("graph-node-n-doc-2"));
    await waitFor(() =>
      expect(
        useToastStore
          .getState()
          .toasts.some((t) => t.title === "No path found"),
      ).toBe(true),
    );
    expect(
      screen.getByText("No path found between the selected nodes."),
    ).toBeInTheDocument();
  });

  it("opens the side panel on node click", async () => {
    setup();
    await screen.findByTestId("graph-node-n-doc-1");
    fireEvent.click(screen.getByTestId("graph-node-n-doc-1"));
    const panel = await screen.findByTestId("node-panel");
    expect(panel).toHaveTextContent("Payment retries runbook");
    expect(panel).toHaveTextContent("Stale");
    expect(panel).toHaveTextContent("2"); // degree
    expect(
      screen.getByRole("button", { name: /Focus neighbors/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Start path here/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Open source document/ }),
    ).toBeInTheDocument();
  });

  it("focus mode shows only the node and its neighbors, and resets", async () => {
    setup();
    await screen.findByTestId("graph-node-n-user-1");
    fireEvent.click(screen.getByTestId("graph-node-n-user-1"));
    await screen.findByTestId("node-panel");
    fireEvent.click(screen.getByRole("button", { name: /Focus neighbors/ }));
    await waitFor(() =>
      expect(screen.queryByTestId("graph-node-n-run-1")).toBeNull(),
    );
    expect(screen.getByTestId("graph-node-n-team-1")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-n-user-1")).toBeInTheDocument();
    // "Show all" resets focus mode
    fireEvent.click(screen.getByRole("button", { name: /Show all/ }));
    await screen.findByTestId("graph-node-n-run-1");
    // Escape also resets (re-focus first)
    fireEvent.click(screen.getByRole("button", { name: /Focus neighbors/ }));
    await waitFor(() =>
      expect(screen.queryByTestId("graph-node-n-run-1")).toBeNull(),
    );
    fireEvent.keyDown(document, { key: "Escape" });
    await screen.findByTestId("graph-node-n-run-1");
  });

  it("navigates on double-click when the node ref is navigable", async () => {
    setup();
    await screen.findByTestId("graph-node-n-doc-1");
    fireEvent.doubleClick(screen.getByTestId("graph-node-n-doc-1"));
    await waitFor(() => expect(screen.queryByTestId("page-graph")).toBeNull());
  });

  it("shows the legend popover", async () => {
    setup();
    await screen.findByTestId("graph-node-n-repo-1");
    fireEvent.click(screen.getByRole("button", { name: /Legend/ }));
    const legend = await screen.findByTestId("graph-legend");
    expect(legend).toHaveTextContent("Conflicted (red ring)");
    expect(legend).toHaveTextContent("Stale (amber dashed)");
    expect(legend).toHaveTextContent("Packet");
  });
});
