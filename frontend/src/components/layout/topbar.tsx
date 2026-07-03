import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, KeyRound, Menu, Moon, Search, Sun, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Kbd } from "@/components/ui/kbd";
import { useMe } from "@/hooks/use-me";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";

/** Seeded demo keys — one per role — switchable at runtime. */
const DEMO_KEYS: Array<{ label: string; key: string }> = [
  { label: "Admin", key: "demo-admin-key" },
  { label: "Lead", key: "demo-lead-key" },
  { label: "Engineer", key: "demo-engineer-key" },
  { label: "Viewer", key: "demo-viewer-key" },
];

interface TopbarProps {
  onMenuClick: () => void;
}

function Topbar({ onMenuClick }: TopbarProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const { resolvedTheme, toggleTheme } = useThemeStore();
  const apiKey = useAuthStore((s) => s.apiKey);
  const setApiKey = useAuthStore((s) => s.setApiKey);
  const { data: me } = useMe();
  const [customKey, setCustomKey] = useState("");

  // Cmd/Ctrl+K focuses the global search.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (q) navigate(`/explorer?q=${encodeURIComponent(q)}`);
  };

  const switchKey = (key: string) => {
    setApiKey(key);
    queryClient.clear();
  };

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-background px-3">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Open navigation"
        onClick={onMenuClick}
      >
        <Menu aria-hidden="true" />
      </Button>

      <form
        role="search"
        onSubmit={submitSearch}
        className="relative flex w-full max-w-md items-center"
      >
        <Search
          className="pointer-events-none absolute left-2.5 size-3.5 text-muted-foreground"
          aria-hidden="true"
        />
        <input
          ref={searchRef}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search the org context…"
          aria-label="Global search"
          className="h-8 w-full rounded-md border border-input bg-card pl-8 pr-14 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Kbd className="absolute right-2.5 hidden sm:inline-flex">⌘K</Kbd>
      </form>

      <div className="ml-auto flex items-center gap-1.5">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
          onClick={toggleTheme}
        >
          {resolvedTheme === "dark" ? (
            <Sun aria-hidden="true" />
          ) : (
            <Moon aria-hidden="true" />
          )}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="Switch API key"
            className="flex h-8 items-center gap-1.5 rounded-md px-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <UserRound className="size-3.5 text-muted-foreground" aria-hidden="true" />
            <span className="hidden max-w-32 truncate sm:inline">
              {me?.name ?? "Unknown user"}
            </span>
            {me?.role ? <Badge variant="secondary">{me.role}</Badge> : null}
            <ChevronDown className="size-3 text-muted-foreground" aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>Demo API keys</DropdownMenuLabel>
            {DEMO_KEYS.map((entry) => (
              <DropdownMenuItem
                key={entry.key}
                onSelect={() => switchKey(entry.key)}
              >
                <KeyRound aria-hidden="true" />
                <span className="flex-1">{entry.label}</span>
                {apiKey === entry.key ? (
                  <Badge variant="default">active</Badge>
                ) : null}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Custom key</DropdownMenuLabel>
            <form
              className="px-2 pb-1.5"
              onSubmit={(event) => {
                event.preventDefault();
                if (customKey.trim()) {
                  switchKey(customKey.trim());
                  setCustomKey("");
                }
              }}
            >
              <input
                value={customKey}
                onChange={(event) => setCustomKey(event.target.value)}
                placeholder="Paste API key, press Enter"
                aria-label="Custom API key"
                className="h-7 w-full rounded-md border border-input bg-card px-2 text-xs shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </form>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

export { Topbar };
