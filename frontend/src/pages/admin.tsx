import { useSearchParams } from "react-router-dom";

import { ApiKeysTab } from "@/components/admin/api-keys-tab";
import { AuditLogTab } from "@/components/admin/audit-log-tab";
import { RetrievalTab } from "@/components/admin/retrieval-tab";
import { RulesTab } from "@/components/admin/rules-tab";
import { SystemTab } from "@/components/admin/system-tab";
import { TeamsTab } from "@/components/admin/teams-tab";
import { UsersTab } from "@/components/admin/users-tab";
import { ErrorState } from "@/components/ui/error-state";
import { PageHeader } from "@/components/ui/page-header";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMe } from "@/hooks/use-me";
import { usePageTitle } from "@/hooks/use-page-title";
import { isApiError } from "@/lib/api";

const TABS = [
  { value: "users", label: "Users" },
  { value: "teams", label: "Teams" },
  { value: "api-keys", label: "API keys" },
  { value: "retrieval", label: "Retrieval" },
  { value: "rules", label: "Rules" },
  { value: "audit", label: "Audit log" },
  { value: "system", label: "System" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

function parseTab(raw: string | null): TabValue {
  return TABS.some((t) => t.value === raw) ? (raw as TabValue) : "users";
}

/**
 * Admin settings. Gated on GET /v1/me — non-admin roles get the full-page
 * PermissionDenied and no /v1/admin/* or /v1/settings requests are fired
 * (tab content only mounts for admins).
 */
export default function AdminPage() {
  usePageTitle("Settings");
  const meQuery = useMe();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));

  const renderBody = () => {
    if (meQuery.isPending) {
      return (
        <div className="space-y-3" data-testid="admin-loading">
          <Skeleton className="h-8 w-96 max-w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-2/3" />
        </div>
      );
    }
    if (meQuery.isError) {
      return (
        <ErrorState
          message={
            isApiError(meQuery.error)
              ? meQuery.error.detail
              : "Could not determine your role"
          }
          onRetry={() => void meQuery.refetch()}
        />
      );
    }
    if (meQuery.data.role !== "admin") {
      return <PermissionDenied role={meQuery.data.role} />;
    }

    return (
      <Tabs value={tab} onValueChange={(value) => setSearchParams({ tab: value })}>
        <TabsList className="h-auto flex-wrap">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="users">
          <UsersTab />
        </TabsContent>
        <TabsContent value="teams">
          <TeamsTab />
        </TabsContent>
        <TabsContent value="api-keys">
          <ApiKeysTab />
        </TabsContent>
        <TabsContent value="retrieval">
          <RetrievalTab />
        </TabsContent>
        <TabsContent value="rules">
          <RulesTab />
        </TabsContent>
        <TabsContent value="audit">
          <AuditLogTab />
        </TabsContent>
        <TabsContent value="system">
          <SystemTab />
        </TabsContent>
      </Tabs>
    );
  };

  return (
    <>
      <PageHeader
        title="Settings"
        description="Users, teams, keys, retrieval tuning, governance rules and the audit trail."
      />
      <div data-testid="page-admin">{renderBody()}</div>
    </>
  );
}
