import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { Source } from "@/lib/types";

type ConfigMode = "demo" | "live";

/** Field is a secret (masked on read, "unchanged unless replaced" on write). */
interface FieldSpec {
  key: string;
  label: string;
  secret?: boolean;
  /** Comma-separated list input (e.g. repos, channels, space_keys). */
  list?: boolean;
}

const TYPE_FIELDS: Record<string, FieldSpec[]> = {
  github: [
    { key: "token", label: "Token", secret: true },
    { key: "org", label: "Org" },
    { key: "repos", label: "Repos", list: true },
    { key: "team_name", label: "Team name" },
  ],
  jira: [
    { key: "base_url", label: "Base URL" },
    { key: "email", label: "Email" },
    { key: "api_token", label: "API token", secret: true },
    { key: "jql", label: "JQL" },
  ],
  slack: [
    { key: "token", label: "Token", secret: true },
    { key: "channels", label: "Channels", list: true },
  ],
  confluence: [
    { key: "base_url", label: "Base URL" },
    { key: "email", label: "Email" },
    { key: "api_token", label: "API token", secret: true },
    { key: "space_keys", label: "Space keys", list: true },
  ],
  notion: [
    { key: "token", label: "Integration token", secret: true },
    { key: "query", label: "Search query" },
  ],
  linear: [
    { key: "api_key", label: "API key", secret: true },
    { key: "team_keys", label: "Team keys", list: true },
  ],
  zendesk: [
    { key: "base_url", label: "Base URL" },
    { key: "email", label: "Email" },
    { key: "api_token", label: "API token", secret: true },
  ],
  gdrive: [
    { key: "service_account_json", label: "Service account JSON", secret: true },
    { key: "subject", label: "Impersonate user (email)" },
    { key: "folder_ids", label: "Folder IDs", list: true },
  ],
  gmail: [
    { key: "service_account_json", label: "Service account JSON", secret: true },
    { key: "subject", label: "Mailbox (email)" },
    { key: "query", label: "Gmail search query" },
  ],
  gcal: [
    { key: "service_account_json", label: "Service account JSON", secret: true },
    { key: "subject", label: "Impersonate user (email)" },
    { key: "calendar_ids", label: "Calendar IDs", list: true },
  ],
};

function isMasked(value: unknown): boolean {
  return typeof value === "string" && value.startsWith("•••");
}

function toFieldString(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function buildInitialFields(type: string, config: Record<string, unknown>) {
  const specs = TYPE_FIELDS[type] ?? [];
  const values: Record<string, string> = {};
  for (const spec of specs) {
    values[spec.key] = toFieldString(config[spec.key]);
  }
  return values;
}

interface ConfigureSourceDialogProps {
  source: Source;
  readOnly: boolean;
}

function ConfigureSourceDialog({ source, readOnly }: ConfigureSourceDialogProps) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<ConfigMode>(
    (source.config.mode as ConfigMode | undefined) ?? "demo",
  );
  const [fields, setFields] = useState<Record<string, string>>(() =>
    buildInitialFields(source.type, source.config),
  );
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Reset local form state whenever the dialog (re)opens for this source.
  useEffect(() => {
    if (!open) return;
    setMode((source.config.mode as ConfigMode | undefined) ?? "demo");
    setFields(buildInitialFields(source.type, source.config));
  }, [open, source]);

  const mutation = useMutation({
    mutationFn: () => {
      const specs = TYPE_FIELDS[source.type] ?? [];
      const config: Record<string, unknown> = { ...source.config, mode };
      for (const spec of specs) {
        const raw = fields[spec.key] ?? "";
        // Masked sentinel left untouched → keep the stored secret as-is by
        // omitting it from the diff (backend PATCH keeps prior value for any
        // key not present... but contract says PATCH accepts full config and
        // ignores masked sentinels, so we may safely send it back verbatim).
        config[spec.key] = spec.list
          ? raw
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : raw;
      }
      return api.patch<Source>(`/v1/sources/${source.id}`, { config });
    },
    onSuccess: () => {
      toast({ title: "Source configuration saved", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources() });
      setOpen(false);
    },
    onError: (error) => {
      toast({
        title: "Failed to save configuration",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  const specs = TYPE_FIELDS[source.type] ?? [];
  const syncStateEntries = Object.entries(source.sync_state ?? {});

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        aria-label={`Configure ${source.name}`}
        onClick={() => setOpen(true)}
      >
        <Settings2 aria-hidden="true" />
        Configure
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Configure {source.name}</DialogTitle>
            <DialogDescription>
              {readOnly
                ? "Read-only — you do not have permission to change this source."
                : "Switch between the seeded demo connector and a live integration with real credentials."}
            </DialogDescription>
          </DialogHeader>

          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (readOnly || mutation.isPending) return;
              mutation.mutate();
            }}
          >
            <label className="flex flex-col gap-1 text-xs font-medium">
              Mode
              <Select
                aria-label="Config mode"
                value={mode}
                disabled={readOnly}
                onChange={(e) => setMode(e.target.value as ConfigMode)}
              >
                <option value="demo">Demo (seeded data)</option>
                <option value="live">Live (real credentials)</option>
              </Select>
            </label>

            {mode === "live"
              ? specs.map((spec) => {
                  const value = fields[spec.key] ?? "";
                  const masked = spec.secret && isMasked(value);
                  return (
                    <label
                      key={spec.key}
                      className="flex flex-col gap-1 text-xs font-medium"
                    >
                      {spec.label}
                      <Input
                        aria-label={spec.label}
                        type={spec.secret ? "password" : "text"}
                        disabled={readOnly}
                        value={value}
                        placeholder={masked ? "unchanged unless replaced" : undefined}
                        onChange={(e) =>
                          setFields((prev) => ({ ...prev, [spec.key]: e.target.value }))
                        }
                      />
                      {masked ? (
                        <span className="text-[11px] font-normal text-muted-foreground">
                          unchanged unless replaced
                        </span>
                      ) : null}
                    </label>
                  );
                })
              : null}

            {syncStateEntries.length > 0 ? (
              <div className="rounded-md border bg-muted/40 px-3 py-2">
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Sync cursors
                </p>
                <ul className="space-y-0.5 font-mono text-[11px] text-muted-foreground">
                  {syncStateEntries.map(([key, value]) => (
                    <li key={key} className="truncate">
                      {key}: {String(value)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <DialogFooter>
              <Button
                variant="outline"
                type="button"
                aria-label={readOnly ? "Close configuration dialog" : undefined}
                onClick={() => setOpen(false)}
              >
                {readOnly ? "Close" : "Cancel"}
              </Button>
              {!readOnly ? (
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? (
                    <Spinner className="text-primary-foreground" />
                  ) : null}
                  Save
                </Button>
              ) : null}
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

export { ConfigureSourceDialog };
