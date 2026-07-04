import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { ActiveDot } from "@/components/admin/badges";
import { QueryBoundary } from "@/components/admin/query-boundary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
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
import type {
  AdminUser,
  ApiKeyCreated,
  ApiKeyKind,
  ApiKeyOut,
  CreateApiKeyRequest,
  ItemsResponse,
} from "@/lib/types";
import { timeAgo } from "@/lib/utils";

interface CreateKeyDialogProps {
  users: AdminUser[];
}

function CreateKeyDialog({ users }: CreateKeyDialogProps) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<ApiKeyKind>("api");
  const [userId, setUserId] = useState(users[0]?.id ?? "");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      api.post<ApiKeyCreated>("/v1/admin/api-keys", {
        label,
        kind,
        user_id: userId,
      } satisfies CreateApiKeyRequest),
    onSuccess: (key) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminApiKeys() });
      setCreated(key);
    },
    onError: (error) => {
      toast({
        title: "Failed to create key",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  const reset = () => {
    setOpen(false);
    setLabel("");
    setKind("api");
    setUserId(users[0]?.id ?? "");
    setCreated(null);
    setCopied(false);
  };

  return (
    <>
      <Button size="sm" disabled={users.length === 0} onClick={() => setOpen(true)}>
        <Plus aria-hidden="true" />
        Create key
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) reset();
          else setOpen(true);
        }}
      >
        <DialogContent>
          {created ? (
            <>
              <DialogHeader>
                <DialogTitle>Key created</DialogTitle>
                <DialogDescription>
                  Copy this key now — it is shown only once and cannot be retrieved later.
                </DialogDescription>
              </DialogHeader>
              <div
                data-testid="raw-key-block"
                className="break-all rounded-md border bg-muted/40 px-3 py-2 font-mono text-xs"
              >
                {created.raw_key}
              </div>
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    await navigator.clipboard.writeText(created.raw_key);
                    setCopied(true);
                    toast({ title: "Copied to clipboard", variant: "success" });
                  }}
                >
                  {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
              <DialogFooter>
                <Button onClick={reset}>Done</Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Create API key</DialogTitle>
                <DialogDescription>
                  Issues a key for programmatic (api) or MCP access on behalf of a user.
                </DialogDescription>
              </DialogHeader>
              <form
                className="flex flex-col gap-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (label.trim() === "" || !userId || mutation.isPending) return;
                  mutation.mutate();
                }}
              >
                <label className="flex flex-col gap-1 text-xs font-medium">
                  Label
                  <Input
                    aria-label="Key label"
                    placeholder="e.g. ci-deploy-bot"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium">
                  Kind
                  <Select
                    aria-label="Key kind"
                    value={kind}
                    onChange={(e) => setKind(e.target.value as ApiKeyKind)}
                  >
                    <option value="api">api</option>
                    <option value="mcp">mcp</option>
                  </Select>
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium">
                  User
                  <Select
                    aria-label="Key user"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                  >
                    {users.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.name} ({user.email})
                      </option>
                    ))}
                  </Select>
                </label>
                <DialogFooter>
                  <Button variant="outline" type="button" onClick={reset}>
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={label.trim() === "" || !userId || mutation.isPending}
                  >
                    {mutation.isPending ? (
                      <Spinner className="text-primary-foreground" />
                    ) : null}
                    Create key
                  </Button>
                </DialogFooter>
              </form>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Admin → API keys: create (raw key shown once), revoke, metadata list. */
function ApiKeysTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [revokeTarget, setRevokeTarget] = useState<ApiKeyOut | null>(null);

  const keysQuery = useQuery({
    queryKey: queryKeys.adminApiKeys(),
    queryFn: () => api.get<ItemsResponse<ApiKeyOut>>("/v1/admin/api-keys"),
  });
  const usersQuery = useQuery({
    queryKey: queryKeys.adminUsers(),
    queryFn: () => api.get<ItemsResponse<AdminUser>>("/v1/admin/users"),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) =>
      api.post<ApiKeyOut>(`/v1/admin/api-keys/${id}/revoke`),
    onSuccess: () => {
      toast({ title: "Key revoked", variant: "success" });
      setRevokeTarget(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminApiKeys() });
    },
    onError: (error) => {
      toast({
        title: "Failed to revoke key",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  return (
    <div className="space-y-3">
      <p className="flex items-start gap-2 rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        Raw key material is shown only once, right after creation. Only metadata is listed
        below afterwards.
      </p>
      <div className="flex justify-end">
        <CreateKeyDialog users={usersQuery.data?.items ?? []} />
      </div>
      <QueryBoundary query={keysQuery}>
        {({ items }) =>
          items.length === 0 ? (
            <EmptyState title="No API keys" description="No API keys have been issued yet." />
          ) : (
            <Table data-testid="admin-api-keys-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last used</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((key) => (
                  <TableRow key={key.id} data-testid={`admin-key-row-${key.id}`}>
                    <TableCell className="font-mono text-xs">{key.label}</TableCell>
                    <TableCell>
                      <Badge variant={key.kind === "mcp" ? "secondary" : "outline"}>
                        {key.kind}
                      </Badge>
                    </TableCell>
                    <TableCell>{key.user_name}</TableCell>
                    <TableCell>
                      <ActiveDot active={key.is_active} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {key.last_used_at ? timeAgo(key.last_used_at) : "never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!key.is_active}
                        onClick={() => setRevokeTarget(key)}
                      >
                        Revoke
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )
        }
      </QueryBoundary>

      <Dialog
        open={revokeTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRevokeTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke key</DialogTitle>
            <DialogDescription>
              {revokeTarget
                ? `"${revokeTarget.label}" will stop working immediately. This cannot be undone.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevokeTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={revokeMutation.isPending}
              onClick={() => {
                if (revokeTarget) revokeMutation.mutate(revokeTarget.id);
              }}
            >
              Revoke key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export { ApiKeysTab };
