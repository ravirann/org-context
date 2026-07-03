import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, isApiError } from "@/lib/api";
import type { Feedback, FeedbackType } from "@/lib/types";
import { queryKeys } from "@/lib/queryKeys";

const TYPE_LABELS: Partial<Record<FeedbackType, string>> = {
  useful: "Useful",
  irrelevant: "Irrelevant",
  missing_context: "Missing context",
};

interface PacketFeedbackDialogProps {
  packetId: string;
  /** Which feedback type is being submitted; null keeps the dialog closed. */
  type: FeedbackType | null;
  onClose: () => void;
}

/**
 * Optional-comment dialog for packet feedback. POSTs /v1/feedback with
 * {context_packet_id, type, comment} and refetches the packet on success.
 */
function PacketFeedbackDialog({ packetId, type, onClose }: PacketFeedbackDialogProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [comment, setComment] = useState("");

  const submit = useMutation({
    mutationFn: (body: { type: FeedbackType; comment?: string }) =>
      api.post<Feedback>("/v1/feedback", {
        context_packet_id: packetId,
        type: body.type,
        comment: body.comment || undefined,
      }),
    onSuccess: () => {
      toast({ title: "Feedback recorded", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.packet(packetId) });
      setComment("");
      onClose();
    },
    onError: (error) => {
      toast({
        title: "Failed to send feedback",
        description: isApiError(error) ? error.detail : "Unexpected error",
        variant: "error",
      });
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!type) return;
    submit.mutate({ type, comment: comment.trim() });
  };

  return (
    <Dialog open={type !== null} onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Mark packet as {type ? (TYPE_LABELS[type] ?? type).toLowerCase() : ""}
          </DialogTitle>
          <DialogDescription>
            Optionally add a comment — it helps tune retrieval for future packets.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-3">
          <Textarea
            aria-label="Feedback comment"
            placeholder="Optional comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={submit.isPending}>
              {submit.isPending ? <Spinner className="size-3.5" /> : null}
              Submit feedback
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export { PacketFeedbackDialog, TYPE_LABELS as PACKET_FEEDBACK_LABELS };
