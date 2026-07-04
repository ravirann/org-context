import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { ActiveDot } from "@/components/admin/badges";
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
import { useMe } from "@/hooks/use-me";
import { api, isApiError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type {
  AdminTeam,
  AdminUser,
  CreateUserRequest,
  ItemsResponse,
  Role,
  UpdateUserRequest,
} from "@/lib/types";

const ROLES: Role[] = ["admin", "lead", "engineer", "viewer"];

interface AddUserDialogProps {
  teams: AdminTeam[];
}

function AddUserDialog({ teams }: AddUserDialogProps) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [teamId, setTeamId] = useState<string>("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      api.post<AdminUser>("/v1/admin/users", {
        email,
        name,
        role,
        team_id: teamId || undefined,
      } satisfies CreateUserRequest),
    onSuccess: (user) => {
      toast({ title: "User added", description: user.email, variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers() });
      setOpen(false);
      setEmail("");
      setName("");
      setRole("viewer");
      setTeamId("");
    },
    onError: (error) => {
      toast({
        title: "Failed to add user",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus aria-hidden="true" />
        Add user
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add user</DialogTitle>
            <DialogDescription>
              Creates an account with the given role. They can sign in immediately.
            </DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (email.trim() === "" || name.trim() === "" || mutation.isPending) return;
              mutation.mutate();
            }}
          >
            <label className="flex flex-col gap-1 text-xs font-medium">
              Email
              <Input
                type="email"
                aria-label="Email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Name
              <Input
                aria-label="Name"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Role
              <Select
                aria-label="Role"
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </Select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Team
              <Select
                aria-label="Team"
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
              >
                <option value="">No team</option>
                {teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </Select>
            </label>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={email.trim() === "" || name.trim() === "" || mutation.isPending}
              >
                {mutation.isPending ? (
                  <Spinner className="text-primary-foreground" />
                ) : null}
                Create user
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

interface UserRowProps {
  user: AdminUser;
  teams: AdminTeam[];
  isSelf: boolean;
  onPatch: (id: string, body: UpdateUserRequest) => void;
}

function UserRow({ user, teams, isSelf, onPatch }: UserRowProps) {
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);

  return (
    <TableRow data-testid={`admin-user-row-${user.id}`}>
      <TableCell className="font-mono text-xs">{user.email}</TableCell>
      <TableCell>{user.name}</TableCell>
      <TableCell>
        <Select
          aria-label={`Role for ${user.email}`}
          value={user.role}
          disabled={isSelf}
          className="w-32"
          onChange={(e) => onPatch(user.id, { role: e.target.value as Role })}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
      </TableCell>
      <TableCell>
        <Select
          aria-label={`Team for ${user.email}`}
          value={teams.find((t) => t.name === user.team_name)?.id ?? ""}
          className="w-32"
          onChange={(e) => onPatch(user.id, { team_id: e.target.value || null })}
        >
          <option value="">No team</option>
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </Select>
      </TableCell>
      <TableCell>
        <ActiveDot active={user.is_active} />
      </TableCell>
      <TableCell className="text-right">
        <Button
          variant="outline"
          size="sm"
          disabled={isSelf}
          onClick={() => {
            if (user.is_active) {
              setConfirmDeactivate(true);
            } else {
              onPatch(user.id, { is_active: true });
            }
          }}
        >
          {user.is_active ? "Deactivate" : "Activate"}
        </Button>
        <Dialog open={confirmDeactivate} onOpenChange={setConfirmDeactivate}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Deactivate {user.name}?</DialogTitle>
              <DialogDescription>
                They will immediately lose access. You can reactivate them later.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setConfirmDeactivate(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  onPatch(user.id, { is_active: false });
                  setConfirmDeactivate(false);
                }}
              >
                Deactivate
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </TableCell>
    </TableRow>
  );
}

/** Admin → Users: roster with create, inline role/team edit, activate/deactivate. */
function UsersTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: me } = useMe();

  const usersQuery = useQuery({
    queryKey: queryKeys.adminUsers(),
    queryFn: () => api.get<ItemsResponse<AdminUser>>("/v1/admin/users"),
  });
  const teamsQuery = useQuery({
    queryKey: queryKeys.adminTeams(),
    queryFn: () => api.get<ItemsResponse<AdminTeam>>("/v1/admin/teams"),
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateUserRequest }) =>
      api.patch<AdminUser>(`/v1/admin/users/${id}`, body),
    onSuccess: () => {
      toast({ title: "User updated", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers() });
    },
    onError: (error) => {
      toast({
        title: "Failed to update user",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  const teams = teamsQuery.data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <AddUserDialog teams={teams} />
      </div>
      <QueryBoundary query={usersQuery}>
        {({ items }) =>
          items.length === 0 ? (
            <EmptyState title="No users" description="No users exist in this workspace yet." />
          ) : (
            <Table data-testid="admin-users-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Team</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    teams={teams}
                    isSelf={me?.id === user.id}
                    onPatch={(id, body) => patchMutation.mutate({ id, body })}
                  />
                ))}
              </TableBody>
            </Table>
          )
        }
      </QueryBoundary>
    </div>
  );
}

export { UsersTab };
