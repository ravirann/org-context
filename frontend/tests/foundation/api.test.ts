import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, isApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

import { mockFetchOnce, mockFetchRoutes, mockResponse } from "../utils";

describe("api", () => {
  beforeEach(() => {
    useAuthStore.setState({ apiKey: "demo-admin-key" });
  });

  it("GET sends the Authorization header and parses JSON", async () => {
    const fetchMock = mockFetchOnce({ id: "u1", name: "Demo Admin" });
    const me = await api.get<{ id: string; name: string }>("/v1/me");

    expect(me.name).toBe("Demo Admin");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/v1/me");
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer demo-admin-key",
    );
  });

  it("serializes query params, arrays, and skips nullish/empty values", async () => {
    const fetchMock = mockFetchOnce({ items: [] });
    await api.get("/v1/context-packets", {
      page: 2,
      repo: "org/api",
      service: undefined,
      intent: null,
      q: "",
      doc_types: ["adr", "pr"],
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe(
      "http://localhost:8000/v1/context-packets?page=2&repo=org%2Fapi&doc_types=adr&doc_types=pr",
    );
  });

  it("POST sends a JSON body with Content-Type", async () => {
    const fetchMock = mockFetchRoutes({
      "POST /v1/search": (_url: URL, init?: RequestInit) => {
        expect(JSON.parse(String(init?.body))).toEqual({ query: "auth" });
        return { items: [], total: 0, page: 1, page_size: 20, acl_blocked_count: 0 };
      },
    });
    const res = await api.post<{ total: number }>("/v1/search", { query: "auth" });
    expect(res.total).toBe(0);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
  });

  it("throws ApiError with parsed {detail} on non-2xx", async () => {
    mockFetchOnce({ detail: "Forbidden for role viewer" }, { status: 403 });
    const error = await api.get("/v1/settings").catch((e: unknown) => e);

    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).detail).toBe("Forbidden for role viewer");
    expect((error as ApiError).message).toBe("Forbidden for role viewer");
  });

  it("falls back to a generic detail when the error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>boom</html>", { status: 500 })),
    );
    const error = await api.get("/v1/me").catch((e: unknown) => e);
    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).status).toBe(500);
    expect((error as ApiError).detail).toBeTruthy();
  });

  it("resolves undefined for 204 responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 204 })),
    );
    await expect(api.delete("/v1/sources/abc")).resolves.toBeUndefined();
  });

  it("mockFetchRoutes rejects unmatched requests with registered routes listed", async () => {
    mockFetchRoutes({ "GET /v1/me": { id: "u1" } });
    const error = await api.get("/v1/unknown").catch((e: unknown) => e);
    expect(String(error)).toContain('no route matches "GET /v1/unknown"');
    expect(String(error)).toContain("GET /v1/me");
  });

  it("mockFetchRoutes supports mockResponse status wrappers and prefix matching", async () => {
    mockFetchRoutes({
      "GET /v1/documents": mockResponse({ detail: "Not found" }, 404),
    });
    const error = await api.get("/v1/documents/some-id").catch((e: unknown) => e);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).detail).toBe("Not found");
  });
});
