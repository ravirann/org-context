import { Lock } from "lucide-react";

import { cn } from "@/lib/utils";

interface PermissionDeniedProps {
  /** The caller's current role, shown in the hint when provided. */
  role?: string;
  message?: string;
  className?: string;
}

/** 403 placeholder — render when the API rejects an action for the role. */
function PermissionDenied({ role, message, className }: PermissionDeniedProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center",
        className,
      )}
    >
      <Lock className="size-8 text-muted-foreground/60" aria-hidden="true" />
      <p className="text-sm font-medium">Permission denied</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        {message ??
          (role
            ? `Your current role (${role}) does not have access to this. Switch to a key with more privileges from the topbar.`
            : "Your current role does not have access to this. Switch to a key with more privileges from the topbar.")}
      </p>
    </div>
  );
}

export { PermissionDenied };
