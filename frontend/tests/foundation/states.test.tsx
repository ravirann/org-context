import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PermissionDenied } from "@/components/ui/permission-denied";

describe("EmptyState", () => {
  it("renders title, description and action", () => {
    render(
      <EmptyState
        title="No packets yet"
        description="Compile your first context packet."
        action={<button type="button">Compile</button>}
      />,
    );
    expect(screen.getByText("No packets yet")).toBeInTheDocument();
    expect(
      screen.getByText("Compile your first context packet."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compile" })).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("renders as an alert with a working retry button", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState message="Boom happened" onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByText("Boom happened")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("omits the retry button when no handler is given", () => {
    render(<ErrorState />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });
});

describe("PermissionDenied", () => {
  it("shows the role hint when a role is provided", () => {
    render(<PermissionDenied role="viewer" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Permission denied");
    expect(screen.getByRole("alert")).toHaveTextContent("viewer");
  });

  it("supports a custom message", () => {
    render(<PermissionDenied message="Admins only." />);
    expect(screen.getByText("Admins only.")).toBeInTheDocument();
  });
});
