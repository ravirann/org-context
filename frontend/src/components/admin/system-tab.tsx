import { useQuery } from "@tanstack/react-query";
import { BookOpen, KeyRound } from "lucide-react";

import { QueryBoundary } from "@/components/admin/query-boundary";
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
import type { Settings } from "@/lib/types";

/** Admin → System: read-only settings dump, MCP hint and API docs links. */
function SystemTab() {
  const query = useQuery({
    queryKey: queryKeys.settings(),
    queryFn: () => api.get<Settings>("/v1/settings"),
  });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
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
