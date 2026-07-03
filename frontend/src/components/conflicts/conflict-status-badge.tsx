import { Badge } from "@/components/ui/badge";
import type { ConflictStatus } from "@/lib/types";

/** Status pill for a conflict: amber while open, green once resolved. */
function ConflictStatusBadge({ status }: { status: ConflictStatus }) {
  return status === "resolved" ? (
    <Badge variant="success">resolved</Badge>
  ) : (
    <Badge variant="warning">open</Badge>
  );
}

export { ConflictStatusBadge };
