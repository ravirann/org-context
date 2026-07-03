import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScoreBadge } from "@/components/ui/score-badge";
import { StatCard } from "@/components/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

describe("Button", () => {
  it("renders variants with distinct classes and handles clicks", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Save</Button>);

    const button = screen.getByRole("button", { name: "Save" });
    expect(button.className).toContain("bg-primary");
    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();

    rerender(<Button variant="destructive">Delete</Button>);
    expect(screen.getByRole("button", { name: "Delete" }).className).toContain(
      "bg-destructive",
    );

    rerender(<Button variant="outline">Cancel</Button>);
    expect(screen.getByRole("button", { name: "Cancel" }).className).toContain(
      "border",
    );

    rerender(
      <Button variant="ghost" size="icon" aria-label="Icon action" />,
    );
    expect(
      screen.getByRole("button", { name: "Icon action" }).className,
    ).toContain("h-8 w-8");
  });

  it("defaults to type=button and supports disabled", () => {
    render(<Button disabled>Nope</Button>);
    const button = screen.getByRole("button", { name: "Nope" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toBeDisabled();
  });
});

describe("Badge / ScoreBadge", () => {
  it("renders badge variants", () => {
    render(
      <>
        <Badge>default</Badge>
        <Badge variant="success">ok</Badge>
        <Badge variant="destructive">bad</Badge>
      </>,
    );
    expect(screen.getByText("ok").className).toContain("emerald");
    expect(screen.getByText("bad").className).toContain("destructive");
  });

  it("colors scores by band and handles null", () => {
    render(
      <>
        <ScoreBadge score={0.92} />
        <ScoreBadge score={0.61} />
        <ScoreBadge score={0.12} />
        <ScoreBadge score={null} />
      </>,
    );
    expect(screen.getByText("0.92").className).toContain("emerald");
    expect(screen.getByText("0.61").className).toContain("amber");
    expect(screen.getByText("0.12").className).toContain("red");
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("StatCard", () => {
  it("renders label, value and delta", () => {
    render(<StatCard label="Documents" value="1,234" delta={12} hint="vs last month" />);
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("+12")).toBeInTheDocument();
    expect(screen.getByText("vs last month")).toBeInTheDocument();
  });

  it("renders a skeleton when loading", () => {
    const { container } = render(<StatCard label="Docs" value="1" loading />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    expect(screen.queryByText("Docs")).not.toBeInTheDocument();
  });
});

describe("Dialog", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger>Open dialog</DialogTrigger>
        <DialogContent>
          <DialogTitle>Confirm action</DialogTitle>
          <button type="button">Inner action</button>
        </DialogContent>
      </Dialog>
    );
  }

  it("opens via trigger, closes on Escape", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open dialog" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Confirm action")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on close button and overlay click", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Open dialog" }));
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open dialog" }));
    await user.click(screen.getByTestId("dialog-overlay"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("switches panels on click and supports arrow keys", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">Tab A</TabsTrigger>
          <TabsTrigger value="b">Tab B</TabsTrigger>
        </TabsList>
        <TabsContent value="a">Panel A</TabsContent>
        <TabsContent value="b">Panel B</TabsContent>
      </Tabs>,
    );

    expect(screen.getByText("Panel A")).toBeInTheDocument();
    expect(screen.queryByText("Panel B")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Tab B" }));
    expect(screen.getByText("Panel B")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Tab B" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    screen.getByRole("tab", { name: "Tab B" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("Panel A")).toBeInTheDocument();
  });
});
