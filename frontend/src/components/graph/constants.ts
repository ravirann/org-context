import {
  Bot,
  Circle,
  Database,
  FileText,
  Flame,
  FolderGit2,
  GitPullRequest,
  Package,
  Plug,
  Scale,
  Server,
  Ticket,
  User,
  Users,
  type LucideIcon,
} from "lucide-react";

/** Stable per-node-type presentation: lucide icon + chart palette color. */
export interface NodeTypeMeta {
  icon: LucideIcon;
  /** CSS color value (chart palette var) used for borders/legend swatches. */
  color: string;
  label: string;
}

export const NODE_TYPE_META: Record<string, NodeTypeMeta> = {
  repo: { icon: FolderGit2, color: "var(--chart-1)", label: "Repo" },
  service: { icon: Server, color: "var(--chart-2)", label: "Service" },
  user: { icon: User, color: "var(--chart-3)", label: "User" },
  team: { icon: Users, color: "var(--chart-4)", label: "Team" },
  pr: { icon: GitPullRequest, color: "var(--chart-5)", label: "PR" },
  ticket: { icon: Ticket, color: "var(--chart-6)", label: "Ticket" },
  doc: { icon: FileText, color: "var(--chart-1)", label: "Doc" },
  adr: { icon: Scale, color: "var(--chart-2)", label: "ADR" },
  incident: { icon: Flame, color: "var(--chart-5)", label: "Incident" },
  api: { icon: Plug, color: "var(--chart-6)", label: "API" },
  db_table: { icon: Database, color: "var(--chart-4)", label: "DB table" },
  context_packet: { icon: Package, color: "var(--chart-3)", label: "Packet" },
  agent_run: { icon: Bot, color: "var(--chart-2)", label: "Agent run" },
};

const FALLBACK_META: NodeTypeMeta = {
  icon: Circle,
  color: "var(--muted-foreground)",
  label: "Other",
};

export function nodeTypeMeta(type: string): NodeTypeMeta {
  return NODE_TYPE_META[type] ?? { ...FALLBACK_META, label: type };
}

export const NODE_TYPES: string[] = Object.keys(NODE_TYPE_META);

/** Edge types offered as filter chips (superset of what the API may return). */
export const EDGE_TYPES: string[] = [
  "owns",
  "authored",
  "references",
  "modifies",
  "mentions",
  "member_of",
  "depends_on",
  "uses",
  "resolves",
];
