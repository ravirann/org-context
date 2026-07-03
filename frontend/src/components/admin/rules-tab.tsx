import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { QueryBoundary } from "@/components/admin/query-boundary";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { Settings, SettingsUpdate } from "@/lib/types";

/** One PATCH /v1/settings per section, with success/error toasts. */
function useSaveSettings(sectionLabel: string) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: SettingsUpdate) => api.patch<Settings>("/v1/settings", update),
    onSuccess: () => {
      toast({ title: `${sectionLabel} saved`, variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings() });
    },
    onError: (error) => {
      toast({
        title: `Failed to save ${sectionLabel.toLowerCase()}`,
        description: isApiError(error) ? error.detail : String(error),
        variant: "error",
      });
    },
  });
}

function SectionCard({
  title,
  description,
  onSave,
  saving,
  children,
  testId,
}: {
  title: string;
  description: string;
  onSave: () => void;
  saving: boolean;
  children: ReactNode;
  testId: string;
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
      <CardFooter>
        <Button size="sm" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : `Save ${title.toLowerCase()}`}
        </Button>
      </CardFooter>
    </Card>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step = 1,
  min = 0,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-3">
      <label htmlFor={id} className="text-xs font-medium">
        {label}
      </label>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-28 text-right tabular-nums"
      />
    </div>
  );
}

function AuthoritySection({ settings }: { settings: Settings }) {
  const [ranks, setRanks] = useState(settings.authority_rules.source_type_ranks);
  const [windowDays, setWindowDays] = useState(settings.freshness_window_days);
  const save = useSaveSettings("Authority rules");

  return (
    <SectionCard
      title="Authority rules"
      description="Rank sources by type (higher rank ⇒ more authoritative) and set the global freshness window."
      onSave={() =>
        save.mutate({
          authority_rules: { source_type_ranks: ranks },
          freshness_window_days: windowDays,
        })
      }
      saving={save.isPending}
      testId="rules-authority"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Source type</TableHead>
            <TableHead className="text-right">Rank</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(ranks).map(([sourceType, rank]) => (
            <TableRow key={sourceType}>
              <TableCell className="font-mono text-xs">{sourceType}</TableCell>
              <TableCell className="text-right">
                <Input
                  type="number"
                  min={0}
                  value={rank}
                  onChange={(e) =>
                    setRanks((prev) => ({ ...prev, [sourceType]: Number(e.target.value) }))
                  }
                  className="ml-auto w-20 text-right tabular-nums"
                  aria-label={`Rank for ${sourceType}`}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <NumberField
        label="Freshness window (days)"
        value={windowDays}
        onChange={setWindowDays}
      />
    </SectionCard>
  );
}

function EvalThresholdsSection({ settings }: { settings: Settings }) {
  const [minScore, setMinScore] = useState(settings.eval_thresholds.min_score);
  const [delta, setDelta] = useState(settings.eval_thresholds.regression_delta);
  const save = useSaveSettings("Eval thresholds");

  return (
    <SectionCard
      title="Eval thresholds"
      description="Minimum acceptable eval score and the delta that flags a regression."
      onSave={() =>
        save.mutate({ eval_thresholds: { min_score: minScore, regression_delta: delta } })
      }
      saving={save.isPending}
      testId="rules-evals"
    >
      <NumberField label="Min score" value={minScore} onChange={setMinScore} step={0.05} max={1} />
      <NumberField
        label="Regression delta"
        value={delta}
        onChange={setDelta}
        step={0.01}
        max={1}
      />
    </SectionCard>
  );
}

function RetentionSection({ settings }: { settings: Settings }) {
  const [auditDays, setAuditDays] = useState(settings.retention.audit_days);
  const [packetDays, setPacketDays] = useState(settings.retention.packet_days);
  const save = useSaveSettings("Retention");

  return (
    <SectionCard
      title="Retention"
      description="How long audit logs and context packets are kept before pruning."
      onSave={() =>
        save.mutate({ retention: { audit_days: auditDays, packet_days: packetDays } })
      }
      saving={save.isPending}
      testId="rules-retention"
    >
      <NumberField label="Audit log days" value={auditDays} onChange={setAuditDays} />
      <NumberField label="Packet days" value={packetDays} onChange={setPacketDays} />
    </SectionCard>
  );
}

function PiiSection({ settings }: { settings: Settings }) {
  const [enabled, setEnabled] = useState(settings.pii_redaction.enabled);
  const [patterns, setPatterns] = useState(settings.pii_redaction.patterns);
  const [draft, setDraft] = useState("");
  const save = useSaveSettings("PII redaction");
  const enabledId = useId();

  const addPattern = () => {
    const value = draft.trim();
    if (!value || patterns.includes(value)) return;
    setPatterns((prev) => [...prev, value]);
    setDraft("");
  };

  return (
    <SectionCard
      title="PII redaction"
      description="Regex patterns scrubbed from compiled context before it reaches an agent."
      onSave={() => save.mutate({ pii_redaction: { enabled, patterns } })}
      saving={save.isPending}
      testId="rules-pii"
    >
      <label htmlFor={enabledId} className="flex items-center gap-2 text-xs font-medium">
        <input
          id={enabledId}
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="size-3.5 accent-[var(--primary)]"
        />
        Redaction enabled
      </label>
      <ul className="space-y-1">
        {patterns.map((pattern) => (
          <li
            key={pattern}
            className="flex items-center justify-between gap-2 rounded-md border bg-muted/30 px-2 py-1"
          >
            <code className="break-all font-mono text-xs">{pattern}</code>
            <button
              type="button"
              aria-label={`Remove pattern ${pattern}`}
              className="shrink-0 rounded-sm text-muted-foreground transition-colors hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => setPatterns((prev) => prev.filter((p) => p !== pattern))}
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </li>
        ))}
        {patterns.length === 0 ? (
          <li className="text-xs text-muted-foreground">No patterns configured.</li>
        ) : null}
      </ul>
      <div className="flex items-center gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addPattern();
            }
          }}
          placeholder="e.g. \b\d{3}-\d{2}-\d{4}\b"
          aria-label="New PII pattern"
          className="font-mono text-xs"
        />
        <Button variant="outline" size="sm" onClick={addPattern}>
          <Plus aria-hidden="true" />
          Add
        </Button>
      </div>
    </SectionCard>
  );
}

function FeatureFlagsSection({ settings }: { settings: Settings }) {
  const [flags, setFlags] = useState(settings.feature_flags);
  const save = useSaveSettings("Feature flags");

  return (
    <SectionCard
      title="Feature flags"
      description="Runtime switches for experimental behavior."
      onSave={() => save.mutate({ feature_flags: flags })}
      saving={save.isPending}
      testId="rules-flags"
    >
      {Object.keys(flags).length === 0 ? (
        <p className="text-xs text-muted-foreground">No feature flags defined.</p>
      ) : (
        <ul className="space-y-1.5">
          {Object.entries(flags).map(([name, value]) => (
            <li key={name}>
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={value}
                  onChange={(e) =>
                    setFlags((prev) => ({ ...prev, [name]: e.target.checked }))
                  }
                  className="size-3.5 accent-[var(--primary)]"
                  aria-label={`Toggle ${name}`}
                />
                <code className="font-mono">{name}</code>
              </label>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

/** Admin → Rules: authority, eval, retention, PII and feature-flag settings. */
function RulesTab() {
  const query = useQuery({
    queryKey: queryKeys.settings(),
    queryFn: () => api.get<Settings>("/v1/settings"),
  });

  return (
    <QueryBoundary query={query}>
      {(settings) => (
        <div className="grid gap-4 lg:grid-cols-2">
          <AuthoritySection settings={settings} />
          <div className="space-y-4">
            <EvalThresholdsSection settings={settings} />
            <RetentionSection settings={settings} />
          </div>
          <PiiSection settings={settings} />
          <FeatureFlagsSection settings={settings} />
        </div>
      )}
    </QueryBoundary>
  );
}

export { RulesTab };
