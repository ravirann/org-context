import { Badge } from "@/components/ui/badge";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

const ROLE_VARIANT = {
  admin: "default",
  lead: "success",
  engineer: "secondary",
  viewer: "muted",
} as const;

/** Colored badge for a user role: admin=primary, lead=green, ... */
function RoleBadge({ role }: { role: Role }) {
  return <Badge variant={ROLE_VARIANT[role] ?? "outline"}>{role}</Badge>;
}

/** Green/gray dot + label for an is_active flag. */
function ActiveDot({ active }: { active: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 rounded-full",
          active ? "bg-emerald-500" : "bg-muted-foreground/40",
        )}
      />
      {active ? "active" : "inactive"}
    </span>
  );
}

export { ActiveDot, RoleBadge };
