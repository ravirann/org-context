import { useQuery } from "@tanstack/react-query";
import { BookOpen, Cpu, KeyRound } from "lucide-react";

import { QueryBoundary } from "@/components/admin/query-boundary";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Kbd } from "@/components/ui/kbd";
import { api, API_BASE_URL } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { Settings, SystemInfo } from "@/lib/types";

/** Admin → System → Runtime: embedding provider, auth mode, queue depth, version. */
function RuntimeCard() {
  const query = useQuery({
    queryKey: queryKeys.systemInfo(),
    queryFn: () => api.get<SystemInfo>("/v1/system/info"),
  });

  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          <Cpu className="size-3.5" aria-hidden="true" />
          Runtime
        </CardTitle>
        <CardDescription>
          Live embedding provider, auth mode and worker queue depth from /v1/system/info.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <QueryBoundary query={query}>
          {(info) => (
            <div data-testid="system-runtime-card" className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Embedding
                </p>
                <p className="text-xs">
                  <span className="font-medium">{info.embedding.provider}</span>
                  {" · "}
                  {info.embedding.model}
                  {" · "}
                  {info.embedding.dim} dim
                </p>
                {info.embedding.provider === "deterministic" ? (
                  <p className="text-[11px] text-muted-foreground">
                    no semantic signal — deterministic
                  </p>
                ) : null}
              </div>
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Auth mode
                </p>
                <Badge variant="outline">{info.auth_mode}</Badge>
              </div>
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Queue depth
                </p>
                <p className="text-xs tabular-nums">
                  {info.queue_depth === null ? "—" : info.queue_depth}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Version
                </p>
                <p className="text-xs font-mono">{info.version}</p>
              </div>
            </div>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  );
}

/** Admin → System: read-only settings dump, MCP hint and API docs links. */
function SystemTab() {
  const query = useQuery({
    queryKey: queryKeys.settings(),
    queryFn: () => api.get<Settings>("/v1/settings"),
  });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <RuntimeCard />

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Current settings</CardTitle>
          <CardDescription>
            Read-only snapshot of /v1/settings — edit via the Retrieval and Rules tabs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <QueryBoundary query={query}>
            {(settings) => (
              <pre
                data-testid="system-settings-json"
                className="scroll-area max-h-96 overflow-auto rounded-md border bg-muted/30 p-3 font-mono text-[11px] leading-relaxed"
              >
                {JSON.stringify(settings, null, 2)}
              </pre>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            <KeyRound className="size-3.5" aria-hidden="true" />
            MCP server access
          </CardTitle>
          <CardDescription>
            Agents connect to the MCP server with a bearer token. In the demo stack use{" "}
            <Kbd>demo-mcp-token</Kbd>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Token material for real deployments is provisioned via the backend CLI and is
            never displayed in this UI.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            <BookOpen className="size-3.5" aria-hidden="true" />
            API documentation
          </CardTitle>
          <CardDescription>Interactive OpenAPI docs served by the backend.</CardDescription>
        </CardHeader>
        <CardContent>
          <a
            href={`${API_BASE_URL}/docs`}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-medium text-primary hover:underline"
          >
            {API_BASE_URL}/docs
          </a>
        </CardContent>
      </Card>
    </div>
  );
}

export { SystemTab };
