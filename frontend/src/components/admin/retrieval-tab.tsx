import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useId, useState } from "react";

import { QueryBoundary } from "@/components/admin/query-boundary";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { RetrievalWeights, Settings } from "@/lib/types";

const WEIGHT_FIELDS: Array<{ key: keyof RetrievalWeights; label: string; hint: string }> = [
  { key: "vector", label: "Vector", hint: "Embedding similarity" },
  { key: "fts", label: "Full-text", hint: "Keyword / BM25 match" },
  { key: "freshness", label: "Freshness", hint: "Recency of the document" },
  { key: "authority", label: "Authority", hint: "Source trust ranking" },
];

function WeightField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
      <label htmlFor={id} className="text-xs font-medium">
        {label}
        <span className="ml-1.5 font-normal text-muted-foreground">{hint}</span>
      </label>
      <Input
        id={id}
        type="number"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-24 text-right tabular-nums"
        aria-label={`${label} weight`}
      />
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="col-span-2 h-1.5 w-full cursor-pointer accent-[var(--primary)]"
        aria-label={`${label} weight slider`}
      />
    </div>
  );
}

function RetrievalForm({ settings }: { settings: Settings }) {
  const [weights, setWeights] = useState<RetrievalWeights>(settings.retrieval_weights);
  const [maxTokens, setMaxTokens] = useState(settings.token_budget.max_packet_tokens);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const sum = WEIGHT_FIELDS.reduce((acc, f) => acc + (weights[f.key] || 0), 0);
  const sumOff = Math.abs(sum - 1) > 0.05;

  const save = useMutation({
    mutationFn: () =>
      api.patch<Settings>("/v1/settings", {
        retrieval_weights: weights,
        token_budget: { max_packet_tokens: maxTokens },
      }),
    onSuccess: () => {
      toast({ title: "Retrieval settings saved", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.settings() });
    },
    onError: (error) => {
      toast({
        title: "Failed to save settings",
        description: isApiError(error) ? error.detail : String(error),
        variant: "error",
      });
    },
  });

  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="retrieval-form">
      <Card>
        <CardHeader>
          <CardTitle>Ranking weights</CardTitle>
          <CardDescription>
            How each signal contributes to retrieval ranking (0–1 each; they should sum
            to ≈ 1).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {WEIGHT_FIELDS.map((field) => (
            <WeightField
              key={field.key}
              label={field.label}
              hint={field.hint}
              value={weights[field.key]}
              onChange={(value) =>
                setWeights((prev) => ({ ...prev, [field.key]: value }))
              }
            />
          ))}
          {sumOff ? (
            <p
              role="alert"
              className="flex items-center gap-1.5 rounded-md bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-700 dark:text-amber-400"
            >
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
              Weights sum to {sum.toFixed(2)} — expected ≈ 1.00.
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Token budget</CardTitle>
          <CardDescription>
            Hard cap on compiled context packet size, in tokens.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <label htmlFor="max-packet-tokens" className="text-xs font-medium">
            Max packet tokens
          </label>
          <Input
            id="max-packet-tokens"
            type="number"
            min={0}
            step={500}
            value={maxTokens}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            className="w-40 tabular-nums"
          />
        </CardContent>
      </Card>

      <div className="lg:col-span-2">
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save retrieval settings"}
        </Button>
      </div>
    </div>
  );
}

/** Admin → Retrieval: tune ranking weights and the packet token budget. */
function RetrievalTab() {
  const query = useQuery({
    queryKey: queryKeys.settings(),
    queryFn: () => api.get<Settings>("/v1/settings"),
  });

  return (
    <QueryBoundary query={query}>
      {(settings) => <RetrievalForm settings={settings} />}
    </QueryBoundary>
  );
}

export { RetrievalTab };
