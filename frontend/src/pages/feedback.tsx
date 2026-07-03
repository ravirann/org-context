import { useMutation } from "@tanstack/react-query";
import {
  Clock,
  FileWarning,
  Lock,
  MessageSquarePlus,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import type { Feedback, FeedbackCreate, FeedbackType } from "@/lib/types";

const FEEDBACK_TYPES: Array<{
  value: FeedbackType;
  label: string;
  description: string;
}> = [
  {
    value: "useful",
    label: "Useful",
    description: "The context helped complete the task.",
  },
  {
    value: "irrelevant",
    label: "Irrelevant",
    description: "The context did not apply to the task at hand.",
  },
  {
    value: "missing_context",
    label: "Missing context",
    description: "Important information was absent from the packet.",
  },
  {
    value: "stale_context",
    label: "Stale context",
    description: "The information is outdated — the document will be marked stale.",
  },
  {
    value: "permission_issue",
    label: "Permission issue",
    description: "Content needed for the task was blocked by access control.",
  },
  {
    value: "suggest_source",
    label: "Suggest a source",
    description: "Propose a new source that should be connected and indexed.",
  },
  {
    value: "promote_authoritative",
    label: "Promote as authoritative",
    description: "Raise this document's authority score to the maximum.",
  },
  {
    value: "mark_deprecated",
    label: "Mark as deprecated",
    description: "Flag this document as no longer valid — it will be deprecated.",
  },
];

const QUICK_ACTIONS: Array<{
  type: FeedbackType;
  title: string;
  hint: string;
  icon: typeof Clock;
  /** Which target field the action focuses. */
  target: "packet" | "document";
}> = [
  {
    type: "missing_context",
    title: "Report missing context",
    hint: "A packet lacked something important",
    icon: FileWarning,
    target: "packet",
  },
  {
    type: "stale_context",
    title: "Report stale context",
    hint: "A document is out of date",
    icon: Clock,
    target: "document",
  },
  {
    type: "permission_issue",
    title: "Report permission issue",
    hint: "ACLs blocked needed content",
    icon: Lock,
    target: "packet",
  },
  {
    type: "promote_authoritative",
    title: "Promote source as authoritative",
    hint: "Make a document the trusted answer",
    icon: ShieldCheck,
    target: "document",
  },
  {
    type: "mark_deprecated",
    title: "Mark source as deprecated",
    hint: "Retire an obsolete document",
    icon: Trash2,
    target: "document",
  },
];

const DEFAULT_TYPE: FeedbackType = "useful";

export default function FeedbackPage() {
  usePageTitle("Feedback");
  const { toast } = useToast();

  const [type, setType] = useState<FeedbackType>(DEFAULT_TYPE);
  const [packetId, setPacketId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [comment, setComment] = useState("");
  const [targetError, setTargetError] = useState(false);

  const packetInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);

  const selectedType = FEEDBACK_TYPES.find((t) => t.value === type);

  const submit = useMutation({
    mutationFn: (body: FeedbackCreate) => api.post<Feedback>("/v1/feedback", body),
    onSuccess: () => {
      toast({
        title: "Feedback submitted",
        description: "Thanks — this feeds retrieval ranking and context debt.",
        variant: "success",
      });
      setType(DEFAULT_TYPE);
      setPacketId("");
      setDocumentId("");
      setComment("");
      setTargetError(false);
    },
    onError: (error) => {
      toast({
        title: "Failed to submit feedback",
        description: isApiError(error) ? error.detail : String(error),
        variant: "error",
      });
    },
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!packetId.trim() && !documentId.trim()) {
      setTargetError(true);
      return;
    }
    setTargetError(false);
    submit.mutate({
      type,
      context_packet_id: packetId.trim() || undefined,
      document_id: documentId.trim() || undefined,
      comment: comment.trim() || undefined,
    });
  };

  const applyQuickAction = (action: (typeof QUICK_ACTIONS)[number]) => {
    setType(action.type);
    const input =
      action.target === "packet" ? packetInputRef.current : documentInputRef.current;
    input?.scrollIntoView({ block: "center" });
    input?.focus();
  };

  return (
    <>
      <PageHeader
        title="Feedback"
        description="Close the loop: rate context packets and documents so retrieval keeps improving."
      />
      <div data-testid="page-feedback" className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.type}
              type="button"
              onClick={() => applyQuickAction(action)}
              className="rounded-lg border bg-card p-3 text-left shadow-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <action.icon className="size-4 text-primary" aria-hidden="true" />
              <p className="mt-1.5 text-xs font-semibold leading-snug">{action.title}</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{action.hint}</p>
            </button>
          ))}
        </div>

        <div className="grid items-start gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Submit feedback</CardTitle>
              <CardDescription>
                Target a context packet, a document, or both. Some feedback types have
                immediate side effects (stale, deprecated, authoritative).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="space-y-3">
                <div className="space-y-1">
                  <label htmlFor="feedback-type" className="text-xs font-medium">
                    Feedback type
                  </label>
                  <Select
                    id="feedback-type"
                    value={type}
                    onChange={(e) => setType(e.target.value as FeedbackType)}
                  >
                    {FEEDBACK_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </Select>
                  {selectedType ? (
                    <p className="text-[11px] text-muted-foreground">
                      {selectedType.description}
                    </p>
                  ) : null}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label htmlFor="feedback-packet-id" className="text-xs font-medium">
                      Context packet ID
                    </label>
                    <Input
                      id="feedback-packet-id"
                      ref={packetInputRef}
                      value={packetId}
                      onChange={(e) => setPacketId(e.target.value)}
                      placeholder="packet UUID"
                      className="font-mono text-xs"
                      aria-invalid={targetError}
                    />
                  </div>
                  <div className="space-y-1">
                    <label htmlFor="feedback-document-id" className="text-xs font-medium">
                      Document ID
                    </label>
                    <Input
                      id="feedback-document-id"
                      ref={documentInputRef}
                      value={documentId}
                      onChange={(e) => setDocumentId(e.target.value)}
                      placeholder="document UUID"
                      className="font-mono text-xs"
                      aria-invalid={targetError}
                    />
                  </div>
                </div>
                {targetError ? (
                  <p role="alert" className="text-xs text-destructive">
                    Provide a context packet ID or a document ID (at least one).
                  </p>
                ) : null}

                <div className="space-y-1">
                  <label htmlFor="feedback-comment" className="text-xs font-medium">
                    Comment <span className="text-muted-foreground">(optional)</span>
                  </label>
                  <Textarea
                    id="feedback-comment"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="What was wrong, missing or great?"
                  />
                </div>

                <Button type="submit" disabled={submit.isPending}>
                  <MessageSquarePlus aria-hidden="true" />
                  {submit.isPending ? "Submitting…" : "Submit feedback"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Why feedback matters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-muted-foreground">
              <p>
                Every signal is attributed to you and audited. Feedback adjusts document
                scores, feeds the context-debt report and tunes what future packets
                include.
              </p>
              <ul className="list-disc space-y-1 pl-4">
                <li>
                  <strong className="text-foreground">Stale context</strong> marks the
                  document stale immediately.
                </li>
                <li>
                  <strong className="text-foreground">Promote as authoritative</strong>{" "}
                  sets its authority score to 1.0.
                </li>
                <li>
                  <strong className="text-foreground">Mark as deprecated</strong> retires
                  the document from retrieval.
                </li>
              </ul>
              <p>
                Find IDs on the packet and document detail pages — each header shows a
                copyable UUID.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
