import {
  Bot,
  Database,
  FlaskConical,
  GitCompareArrows,
  Grid3x3,
  LayoutDashboard,
  MessageSquare,
  Package,
  Search,
  Settings,
  TrendingDown,
  Waypoints,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Match exactly (only for "/"). */
  end?: boolean;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    label: "Explore",
    items: [
      { to: "/explorer", label: "Context Explorer", icon: Search },
      { to: "/graph", label: "Relationship Graph", icon: Waypoints },
      { to: "/heatmaps", label: "Heatmaps", icon: Grid3x3 },
    ],
  },
  {
    label: "Context",
    items: [
      { to: "/packets", label: "Packets", icon: Package },
      { to: "/agent-runs", label: "Agent Runs", icon: Bot },
      { to: "/evals", label: "Evals", icon: FlaskConical },
    ],
  },
  {
    label: "Quality",
    items: [
      { to: "/conflicts", label: "Conflicts", icon: GitCompareArrows },
      { to: "/context-debt", label: "Context Debt", icon: TrendingDown },
      { to: "/feedback", label: "Feedback", icon: MessageSquare },
    ],
  },
  {
    label: "Admin",
    items: [
      { to: "/sources", label: "Sources", icon: Database },
      { to: "/admin", label: "Settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  /**
   * "responsive" (default): icon rail below lg, full width at lg+.
   * "full": always full width (used inside the mobile sheet).
   */
  variant?: "responsive" | "full";
  /** Called when a nav link is clicked (used to close the mobile sheet). */
  onNavigate?: () => void;
  className?: string;
}

function Sidebar({ variant = "responsive", onNavigate, className }: SidebarProps) {
  const responsive = variant === "responsive";
  return (
    <nav
      aria-label="Primary"
      className={cn(
        "flex h-full flex-col gap-4 overflow-y-auto bg-sidebar px-2 py-3 text-sidebar-foreground",
        className,
      )}
    >
      {NAV_SECTIONS.map((section) => (
        <div key={section.label} className="flex flex-col gap-0.5">
          <p
            className={cn(
              "mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground",
              responsive && "hidden lg:block",
            )}
          >
            {section.label}
          </p>
          {section.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={item.label}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                  responsive && "justify-center lg:justify-start",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                )
              }
            >
              <item.icon className="size-4 shrink-0" aria-hidden="true" />
              <span className={cn("truncate", responsive && "hidden lg:inline")}>
                {item.label}
              </span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

export { Sidebar };
