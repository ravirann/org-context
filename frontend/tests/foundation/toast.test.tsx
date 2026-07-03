import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { Toaster, useToastStore } from "@/components/ui/toast";

describe("Toast", () => {
  beforeEach(() => {
    // Drain any toasts left over from a previous test.
    const { toasts, dismiss } = useToastStore.getState();
    toasts.forEach((t) => dismiss(t.id));
  });

  it("shows a toast with variant styling and auto-registers a status role", () => {
    render(<Toaster />);
    act(() => {
      useToastStore.getState().toast({
        title: "Saved",
        description: "Settings updated",
        variant: "success",
        duration: 0,
      });
    });

    const toast = screen.getByRole("status");
    expect(toast).toHaveTextContent("Saved");
    expect(toast).toHaveTextContent("Settings updated");
    expect(toast.className).toContain("emerald");
  });

  it("uses role=alert for errors", () => {
    render(<Toaster />);
    act(() => {
      useToastStore.getState().toast({
        title: "Failed",
        variant: "error",
        duration: 0,
      });
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Failed");
  });

  it("dismisses via the close button", async () => {
    const user = userEvent.setup();
    render(<Toaster />);
    act(() => {
      useToastStore.getState().toast({ title: "Info note", duration: 0 });
    });

    expect(screen.getByText("Info note")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByText("Info note")).not.toBeInTheDocument();
  });

  it("stacks multiple toasts and dismiss() removes only the target", () => {
    render(<Toaster />);
    let firstId = "";
    act(() => {
      firstId = useToastStore.getState().toast({ title: "One", duration: 0 });
      useToastStore.getState().toast({ title: "Two", duration: 0 });
    });

    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();

    act(() => {
      useToastStore.getState().dismiss(firstId);
    });
    expect(screen.queryByText("One")).not.toBeInTheDocument();
    expect(screen.getByText("Two")).toBeInTheDocument();
  });
});
