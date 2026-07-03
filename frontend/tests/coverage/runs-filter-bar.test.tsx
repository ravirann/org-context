/**
 * Direct behavioral coverage for RunsFilterBar
 * (src/components/runs/runs-filter-bar.tsx): every onChange field, status
 * toggle buttons (on/off), and the Clear button which only renders once a
 * filter is active.
 */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { RunsFilterBar, type RunFilters } from "@/components/runs/runs-filter-bar";

import { renderWithProviders } from "../utils";

const EMPTY_FILTERS: RunFilters = {
  agent: "",
  repo: "",
  service: "",
  user_id: "",
  status: "",
  from: "",
  to: "",
};

function Harness({ initial = EMPTY_FILTERS }: { initial?: RunFilters }) {
  const [filters, setFilters] = useState<RunFilters>(initial);
  const onChange = (key: keyof RunFilters, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }));
  const onClear = () => setFilters(EMPTY_FILTERS);
  return <RunsFilterBar filters={filters} onChange={onChange} onClear={onClear} />;
}

describe("RunsFilterBar", () => {
  it("has no Clear button and no active status when filters are empty", () => {
    renderWithProviders(<Harness />);
    expect(screen.queryByRole("button", { name: /Clear/ })).not.toBeInTheDocument();
    for (const status of ["running", "succeeded", "failed"]) {
      expect(screen.getByRole("button", { name: status })).toHaveAttribute(
        "aria-pressed",
        "false",
      );
    }
  });

  it("toggles a status filter on and off", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    const failedButton = screen.getByRole("button", { name: "failed" });
    await user.click(failedButton);
    expect(failedButton).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Clear/ })).toBeInTheDocument();

    await user.click(failedButton);
    expect(failedButton).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("button", { name: /Clear/ })).not.toBeInTheDocument();
  });

  it("updates every text filter field", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    await user.type(screen.getByRole("textbox", { name: "Filter by agent" }), "claude-code");
    expect(screen.getByRole("textbox", { name: "Filter by agent" })).toHaveValue("claude-code");

    await user.type(screen.getByRole("textbox", { name: "Filter by repo" }), "org/payments");
    expect(screen.getByRole("textbox", { name: "Filter by repo" })).toHaveValue("org/payments");

    await user.type(screen.getByRole("textbox", { name: "Filter by service" }), "payments-api");
    expect(screen.getByRole("textbox", { name: "Filter by service" })).toHaveValue(
      "payments-api",
    );

    await user.type(screen.getByRole("textbox", { name: "Filter by user id" }), "u-42");
    expect(screen.getByRole("textbox", { name: "Filter by user id" })).toHaveValue("u-42");

    expect(screen.getByRole("button", { name: /Clear/ })).toBeInTheDocument();
  });

  it("updates the from/to date fields", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);

    const fromInput = screen.getByLabelText("From date");
    const toInput = screen.getByLabelText("To date");
    await user.type(fromInput, "2026-06-01");
    await user.type(toInput, "2026-06-30");

    expect(fromInput).toHaveValue("2026-06-01");
    expect(toInput).toHaveValue("2026-06-30");
  });

  it("clears all filters via the Clear button", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <Harness initial={{ ...EMPTY_FILTERS, agent: "claude-code", status: "failed" }} />,
    );

    expect(screen.getByRole("button", { name: /Clear/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Clear/ }));

    expect(screen.getByRole("textbox", { name: "Filter by agent" })).toHaveValue("");
    expect(screen.getByRole("button", { name: "failed" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.queryByRole("button", { name: /Clear/ })).not.toBeInTheDocument();
  });

  it("calls onChange directly with expected key/value pairs", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <RunsFilterBar filters={EMPTY_FILTERS} onChange={onChange} onClear={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "running" }));
    expect(onChange).toHaveBeenCalledWith("status", "running");

    await user.type(screen.getByRole("textbox", { name: "Filter by agent" }), "x");
    expect(onChange).toHaveBeenCalledWith("agent", "x");
  });
});
