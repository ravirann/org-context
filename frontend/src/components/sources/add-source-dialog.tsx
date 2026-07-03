import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { SOURCE_TYPES } from "@/components/sources/source-badges";
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

/** "Add source" PageHeader action: type + name form posting to /v1/sources. */
function AddSourceDialog({ disabled = false }: { disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<string>("github");
  const [name, setName] = useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => api.post<Source>("/v1/sources", { type, name }),
    onSuccess: (source) => {
      toast({ title: "Source added", description: source.name, variant: "success" });
      void queryClient.invalidateQueries({ queryKey: queryKeys.sources() });
      setOpen(false);
      setName("");
    },
    onError: (error) => {
      toast({
        title:
          isApiError(error) && error.status === 403
            ? "Requires admin"
            : "Failed to add source",
        description: isApiError(error) ? error.detail : undefined,
        variant: "error",
      });
    },
  });

  return (
    <>
      <Button disabled={disabled} onClick={() => setOpen(true)}>
        <Plus aria-hidden="true" />
        Add source
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add source</DialogTitle>
            <DialogDescription>
              Connect a new knowledge source. Sync starts once it is enabled.
            </DialogDescription>
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
              Type
              <Select
                aria-label="Source type"
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                {SOURCE_TYPES.map((sourceType) => (
                  <option key={sourceType} value={sourceType}>
                    {sourceType}
                  </option>
                ))}
              </Select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium">
              Name
              <Input
                aria-label="Source name"
                placeholder="e.g. backend monorepo"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <DialogFooter>
              <Button
                variant="outline"
                type="button"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={name.trim() === "" || mutation.isPending}
              >
                {mutation.isPending ? <Spinner className="text-primary-foreground" /> : null}
                Create source
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

export { AddSourceDialog };
