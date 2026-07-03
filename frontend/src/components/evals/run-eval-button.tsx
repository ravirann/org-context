import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, isApiError } from "@/lib/api";
import type { EvalMode, EvalRunEnqueued } from "@/lib/types";

const MODES: EvalMode[] = ["comparison", "baseline", "context_engine"];

/** PageHeader action: pick a mode and enqueue an eval run. */
function RunEvalButton() {
  const [mode, setMode] = useState<EvalMode>("comparison");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => api.post<EvalRunEnqueued>("/v1/evals/run", { mode }),
    onSuccess: () => {
      toast({ title: "Eval queued", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["evals"] });
    },
    onError: (error) => {
      toast({
        title:
          isApiError(error) && error.status === 403
            ? "Requires admin"
            : "Failed to queue eval",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  return (
    <div className="flex items-center gap-2">
      <Select
        aria-label="Eval mode"
        className="w-36"
        value={mode}
        disabled={mutation.isPending}
        onChange={(e) => setMode(e.target.value as EvalMode)}
      >
        {MODES.map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </Select>
      <Button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? <Spinner className="text-primary-foreground" /> : <Play aria-hidden="true" />}
        Run eval
      </Button>
    </div>
  );
}

export { RunEvalButton };
