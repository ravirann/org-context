import { useAuthStore } from "@/stores/auth";

/**
 * Typed fetch wrapper for the /v1 API.
 *
 *   const me = await api.get<Me>("/v1/me");
 *   const res = await api.post<SearchResponse>("/v1/search", { query: "auth" });
 *
 * - Base URL: import.meta.env.VITE_API_URL ?? "http://localhost:8000"
 * - Sends `Authorization: Bearer <apiKey>` from useAuthStore on every request.
 * - Throws ApiError { status, detail } on any non-2xx response (parses the
 *   FastAPI `{detail}` error shape when present).
 * - 204 responses resolve to undefined.
 */

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export type QueryParams = Record<
  string,
  string | number | boolean | Array<string | number> | null | undefined
>;

export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function buildUrl(path: string, params?: QueryParams): string {
  const url = `${API_BASE_URL}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item));
    } else {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  options: { params?: QueryParams; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${useAuthStore.getState().apiKey}`,
  };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(buildUrl(path, options.params), {
    method,
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let detail = response.statusText || `Request failed (${response.status})`;
    try {
      const data: unknown = await response.json();
      if (
        typeof data === "object" &&
        data !== null &&
        "detail" in data &&
        typeof (data as { detail: unknown }).detail === "string"
      ) {
        detail = (data as { detail: string }).detail;
      }
    } catch {
      // non-JSON error body — keep the fallback detail
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: QueryParams): Promise<T> =>
    request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown, params?: QueryParams): Promise<T> =>
    request<T>("POST", path, { body, params }),
  patch: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>("PATCH", path, { body }),
  delete: <T = void>(path: string): Promise<T> => request<T>("DELETE", path),
};
