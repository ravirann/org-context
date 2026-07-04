import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { InlineTextInput } from "@/components/admin/inline-text-input";
import { QueryBoundary } from "@/components/admin/query-boundary";
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
import type { AdminTeam, CreateTeamRequest, ItemsResponse } from "@/lib/types";

function CreateTeamDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      api.post<AdminTeam>("/v1/admin/teams", {
        name,
        description: description || undefined,
      } satisfies CreateTeamRequest),
    onSuccess: (team) => {
      toast({ title: "Team created", description: team.name, variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminTeams() });
      setOpen(false);
      setName("");
      setDescription("");
    },
    onError: (error) => {
      toast({
        title: "Failed to create team",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus aria-hidden="true" />
        Add team
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add team</DialogTitle>
            <DialogDescription>Teams group users for ACLs and ownership.</DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim() === "" || mutation.isPending) return;
              mutation.mutate();
            }}
          >
            <label className="flex flex-col gap-1 text-xs font-medium">
              Name
              <Input
                aria-label="Team name"
                placeholder="e.g. Payments"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Description
              <Input
                aria-label="Team description"
                placeholder="Optional"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={name.trim() === "" || mutation.isPending}>
                {mutation.isPending ? (
                  <Spinner className="text-primary-foreground" />
                ) : null}
                Create team
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

interface TeamRowProps {
  team: AdminTeam;
  onRename: (id: string, name: string) => void;
  onDelete: (team: AdminTeam) => void;
}

function TeamRow({ team, onRename, onDelete }: TeamRowProps) {
  return (
    <TableRow data-testid={`admin-team-row-${team.id}`}>
      <TableCell>
        <InlineTextInput
          aria-label={`Team name for ${team.name}`}
          value={team.name}
          onCommit={(name) => onRename(team.id, name)}
        />
      </TableCell>
      <TableCell className="text-right tabular-nums">{team.member_count}</TableCell>
      <TableCell className="text-right">
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Delete ${team.name}`}
          onClick={() => onDelete(team)}
        >
          <Trash2 className="text-destructive" aria-hidden="true" />
        </Button>
      </TableCell>
    </TableRow>
  );
}

/** Admin → Teams: create, inline rename, delete (confirm). */
function TeamsTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<AdminTeam | null>(null);

  const query = useQuery({
    queryKey: queryKeys.adminTeams(),
    queryFn: () => api.get<ItemsResponse<AdminTeam>>("/v1/admin/teams"),
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.patch<AdminTeam>(`/v1/admin/teams/${id}`, { name }),
    onSuccess: () => {
      toast({ title: "Team renamed", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminTeams() });
    },
    onError: (error) => {
      toast({
        title: "Failed to rename team",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/admin/teams/${id}`),
    onSuccess: () => {
      toast({ title: "Team deleted", variant: "success" });
      setDeleteTarget(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminTeams() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers() });
    },
    onError: (error) => {
      toast({
        title: "Failed to delete team",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <CreateTeamDialog />
      </div>
      <QueryBoundary query={query}>
        {({ items }) =>
          items.length === 0 ? (
            <EmptyState title="No teams" description="No teams exist in this workspace yet." />
          ) : (
            <Table data-testid="admin-teams-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Members</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((team) => (
                  <TeamRow
                    key={team.id}
                    team={team}
                    onRename={(id, name) => renameMutation.mutate({ id, name })}
                    onDelete={setDeleteTarget}
                  />
                ))}
              </TableBody>
            </Table>
          )
        }
      </QueryBoundary>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete team</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `This permanently removes "${deleteTarget.name}". Its members will be unassigned (team set to none) — document ACLs referencing this team are left untouched.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
              }}
            >
              Delete team
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export { TeamsTab };
