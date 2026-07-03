import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

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
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, isApiError } from "@/lib/api";
import type { CompileRequest, ContextPacket } from "@/lib/types";

interface CompilePacketDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * "Compile context" dialog: POST /v1/context/compile then navigate to the new
 * packet's inspector page.
 */
function CompilePacketDialog({ open, onOpenChange }: CompilePacketDialogProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [task, setTask] = useState("");
  const [repo, setRepo] = useState("");
  const [service, setService] = useState("");
  const [maxTokens, setMaxTokens] = useState("");

  const compile = useMutation({
    mutationFn: (body: CompileRequest) =>
      api.post<ContextPacket>("/v1/context/compile", body),
    onSuccess: (packet) => {
      void queryClient.invalidateQueries({ queryKey: ["context-packets"] });
      toast({ title: "Context packet compiled", variant: "success" });
      onOpenChange(false);
      navigate(`/packets/${packet.id}`);
    },
    onError: (error) => {
      toast({
        title: "Failed to compile context",
        description: isApiError(error) ? error.detail : "Unexpected error",
        variant: "error",
      });
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = task.trim();
    if (!trimmed) return;
    const parsedMaxTokens = Number.parseInt(maxTokens, 10);
    compile.mutate({
      task: trimmed,
      repo: repo.trim() || undefined,
      service: service.trim() || undefined,
      max_tokens:
        Number.isFinite(parsedMaxTokens) && parsedMaxTokens > 0
          ? parsedMaxTokens
          : undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Compile context</DialogTitle>
          <DialogDescription>
            Describe the task; the engine assembles the best context packet for it.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-3">
          <label className="grid gap-1 text-xs font-medium">
            Task
            <Textarea
              required
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="e.g. Fix the retry logic in the payment webhook handler"
              aria-label="Task"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="grid gap-1 text-xs font-medium">
              Repo
              <Input
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                placeholder="optional"
                aria-label="Repo"
              />
            </label>
            <label className="grid gap-1 text-xs font-medium">
              Service
              <Input
                value={service}
                onChange={(e) => setService(e.target.value)}
                placeholder="optional"
                aria-label="Service"
              />
            </label>
          </div>
          <label className="grid gap-1 text-xs font-medium">
            Max tokens
            <Input
              type="number"
              min={1}
              value={maxTokens}
              onChange={(e) => setMaxTokens(e.target.value)}
              placeholder="engine default"
              aria-label="Max tokens"
            />
          </label>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={compile.isPending || !task.trim()}>
              {compile.isPending ? <Spinner className="size-3.5" /> : null}
              Compile
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export { CompilePacketDialog };
