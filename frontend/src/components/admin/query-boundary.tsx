import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { ErrorState } from "@/components/ui/error-state";
import { PermissionDenied } from "@/components/ui/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";

interface QueryBoundaryProps<T> {
  query: UseQueryResult<T>;
  /** Custom loading placeholder; defaults to a stack of skeleton rows. */
  skeleton?: ReactNode;
  children: (data: T) => ReactNode;
}

function DefaultSkeleton() {
  return (
    <div className="space-y-2" data-testid="tab-skeleton">
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-3/4" />
    </div>
  );
}

/** Standard loading / 403 / error / data switch for one admin tab query. */
function QueryBoundary<T>({ query, skeleton, children }: QueryBoundaryProps<T>) {
  if (query.isPending) return <>{skeleton ?? <DefaultSkeleton />}</>;
  if (query.isError) {
    const error = query.error as { status?: number; detail?: string; message?: string };
    if (error.status === 403) return <PermissionDenied />;
    return (
      <ErrorState
        message={error.detail ?? error.message ?? "Request failed"}
        onRetry={() => void query.refetch()}
      />
    );
  }
  return <>{children(query.data)}</>;
}

export { QueryBoundary };
