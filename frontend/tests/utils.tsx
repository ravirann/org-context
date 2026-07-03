/**
 * Shared test helpers for ALL frontend tests.
 *
 *   renderWithProviders(<PacketsPage />, { route: "/packets" })
 *   renderWithProviders(<PacketDetailPage />, {
 *     route: "/packets/abc-123",
 *     path: "/packets/:id",          // registers a <Route> so useParams works
 *   })
 *
 *   mockFetchRoutes({
 *     "GET /v1/me": me,
 *     "GET /v1/context-packets": paginated,
 *     "POST /v1/search": (url, init) => ({ items: [], ... }),
 *     "GET /v1/settings": mockResponse({ detail: "Forbidden" }, 403),
 *   })
 *
 * Route keys are "<METHOD> <path-prefix>". Query strings are ignored when
 * matching; the longest matching prefix wins. Unmatched requests reject with
 * an error listing every registered route.
 */
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi, type Mock } from "vitest";

/* ------------------------------ render helpers -------------------------------- */

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

interface RenderOptions {
  /** Initial URL, e.g. "/packets/abc?page=2". Default "/". */
  route?: string;
  /** Optional route pattern (e.g. "/packets/:id") so useParams() resolves. */
  path?: string;
  queryClient?: QueryClient;
}

export function renderWithProviders(
  ui: ReactElement,
  { route = "/", path, queryClient = createTestQueryClient() }: RenderOptions = {},
): RenderResult & { queryClient: QueryClient } {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          {path ? (
            <Routes>
              <Route path={path} element={children} />
            </Routes>
          ) : (
            children
          )}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  const result = render(ui, { wrapper: Wrapper });
  return { ...result, queryClient };
}

/* ------------------------------- fetch mocking -------------------------------- */

const RESPONSE_MARKER = Symbol("mockResponse");

interface MockResponseSpec {
  [RESPONSE_MARKER]: true;
  body: unknown;
  status: number;
}

/** Wrap a body to control the HTTP status, e.g. mockResponse({detail: "x"}, 403). */
export function mockResponse(body: unknown, status = 200): MockResponseSpec {
  return { [RESPONSE_MARKER]: true, body, status };
}

function isSpec(value: unknown): value is MockResponseSpec {
  return (
    typeof value === "object" &&
    value !== null &&
    RESPONSE_MARKER in value
  );
}

type RouteHandler = (url: URL, init?: RequestInit) => unknown;
type RouteValue = unknown | MockResponseSpec | RouteHandler;

function toResponse(value: unknown): Response {
  const spec = isSpec(value) ? value : { body: value, status: 200 };
  return new Response(JSON.stringify(spec.body), {
    status: spec.status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL): URL {
  const raw =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.toString()
        : input.url;
  return new URL(raw, "http://localhost:8000");
}

/**
 * Stub global fetch with method + path-prefix matched routes. Returns the
 * vi.fn() so tests can assert on calls. Values may be plain data (200 JSON),
 * mockResponse(body, status), or a handler (url, init) => data|mockResponse.
 */
export function mockFetchRoutes(routes: Record<string, RouteValue>): Mock {
  const entries = Object.entries(routes).map(([key, value]) => {
    const spaceAt = key.indexOf(" ");
    if (spaceAt === -1) {
      throw new Error(
        `mockFetchRoutes: route key "${key}" must look like "GET /v1/path"`,
      );
    }
    return {
      method: key.slice(0, spaceAt).toUpperCase(),
      path: key.slice(spaceAt + 1),
      value,
    };
  });

  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = requestUrl(input);
      const method = (init?.method ?? "GET").toUpperCase();

      const match = entries
        .filter((e) => e.method === method && url.pathname.startsWith(e.path))
        .sort((a, b) => b.path.length - a.path.length)[0];

      if (!match) {
        const registered = entries
          .map((e) => `  ${e.method} ${e.path}`)
          .join("\n");
        throw new Error(
          `mockFetchRoutes: no route matches "${method} ${url.pathname}".\n` +
            `Registered routes:\n${registered || "  (none)"}`,
        );
      }

      const value =
        typeof match.value === "function"
          ? await (match.value as RouteHandler)(url, init)
          : match.value;
      return toResponse(value);
    },
  );

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** Stub global fetch to answer the next request(s) with a single payload. */
export function mockFetchOnce(
  data: unknown,
  { status = 200 }: { status?: number } = {},
): Mock {
  const fetchMock = vi.fn(async (): Promise<Response> => {
    return new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
