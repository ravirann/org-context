/**
 * Behavioral coverage for RulesTab (src/components/admin/rules-tab.tsx):
 * every section's save handler, the PII pattern add/remove flow, and the
 * feature-flag checkbox toggle.
 */
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RulesTab } from "@/components/admin/rules-tab";

import { settingsFixture } from "../fixtures-admin";
import { mockFetchRoutes, renderWithProviders } from "../utils";

function patchBody(fetchMock: ReturnType<typeof mockFetchRoutes>) {
  const call = fetchMock.mock.calls.find(
    ([, init]) => (init as RequestInit | undefined)?.method === "PATCH",
  );
  return call ? JSON.parse(String((call[1] as RequestInit).body)) : null;
}

describe("RulesTab", () => {
  it("saves authority rules with edited rank and freshness window", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/settings": settingsFixture,
      "PATCH /v1/settings": settingsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<RulesTab />);

    await screen.findByTestId("rules-authority");

    const adrRank = screen.getByRole("spinbutton", { name: "Rank for adr" });
    await user.clear(adrRank);
    await user.type(adrRank, "120");

    const windowField = screen.getByLabelText("Freshness window (days)");
    await user.clear(windowField);
    await user.type(windowField, "60");

    await user.click(screen.getByRole("button", { name: "Save authority rules" }));

    await waitFor(() => {
      const body = patchBody(fetchMock);
      expect(body).toEqual({
        authority_rules: { source_type_ranks: { adr: 120, confluence: 60, slack: 20 } },
        freshness_window_days: 60,
      });
    });
  });

  it("saves eval thresholds", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/settings": settingsFixture,
      "PATCH /v1/settings": settingsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<RulesTab />);
    await screen.findByTestId("rules-evals");

    const minScore = screen.getByLabelText("Min score");
    await user.clear(minScore);
    await user.type(minScore, "0.75");
    const delta = screen.getByLabelText("Regression delta");
    await user.clear(delta);
    await user.type(delta, "0.1");

    await user.click(screen.getByRole("button", { name: "Save eval thresholds" }));

    await waitFor(() => {
      expect(patchBody(fetchMock)).toEqual({
        eval_thresholds: { min_score: 0.75, regression_delta: 0.1 },
      });
    });
  });

  it("saves retention settings", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/settings": settingsFixture,
      "PATCH /v1/settings": settingsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<RulesTab />);
    await screen.findByTestId("rules-retention");

    const auditDays = screen.getByLabelText("Audit log days");
    await user.clear(auditDays);
    await user.type(auditDays, "400");
    const packetDays = screen.getByLabelText("Packet days");
    await user.clear(packetDays);
    await user.type(packetDays, "120");

    await user.click(screen.getByRole("button", { name: "Save retention" }));

    await waitFor(() => {
      expect(patchBody(fetchMock)).toEqual({
        retention: { audit_days: 400, packet_days: 120 },
      });
    });
  });

  it("toggles PII redaction, adds and removes a pattern, then saves", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/settings": settingsFixture,
      "PATCH /v1/settings": settingsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<RulesTab />);
    await screen.findByTestId("rules-pii");

    // Existing pattern is shown; toggle enabled off.
    const enabledCheckbox = screen.getByRole("checkbox", { name: "Redaction enabled" });
    expect(enabledCheckbox).toBeChecked();
    await user.click(enabledCheckbox);
    expect(enabledCheckbox).not.toBeChecked();

    // Add a new pattern via the input + Add button.
    const newPatternInput = screen.getByLabelText("New PII pattern");
    await user.type(newPatternInput, "\\bemail@\\S+\\b");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("\\bemail@\\S+\\b")).toBeInTheDocument();

    // Adding a duplicate or blank pattern is a no-op.
    await user.click(screen.getByRole("button", { name: "Add" }));
    await user.type(newPatternInput, "   ");
    await user.click(screen.getByRole("button", { name: "Add" }));

    // Remove the original seeded pattern.
    const originalPattern = settingsFixture.pii_redaction.patterns[0];
    await user.click(screen.getByRole("button", { name: `Remove pattern ${originalPattern}` }));
    expect(screen.queryByText(originalPattern)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save pii redaction" }));

    await waitFor(() => {
      const body = patchBody(fetchMock);
      expect(body).toEqual({
        pii_redaction: { enabled: false, patterns: ["\\bemail@\\S+\\b"] },
      });
    });
  });

  it("adds a pattern via Enter key and shows 'no patterns' when list is emptied", async () => {
    mockFetchRoutes({
      "GET /v1/settings": settingsFixture,
      "PATCH /v1/settings": settingsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<RulesTab />);
    await screen.findByTestId("rules-pii");

    const originalPattern = settingsFixture.pii_redaction.patterns[0];
    await user.click(screen.getByRole("button", { name: `Remove pattern ${originalPattern}` }));
    expect(screen.getByText("No patterns configured.")).toBeInTheDocument();

    const newPatternInput = screen.getByLabelText("New PII pattern");
    fireEvent.change(newPatternInput, { target: { value: "\\d{4}" } });
    fireEvent.keyDown(newPatternInput, { key: "Enter" });
    expect(screen.getByText("\\d{4}")).toBeInTheDocument();
    expect(screen.queryByText("No patterns configured.")).not.toBeInTheDocument();
  });

  it("toggles a feature flag and saves", async () => {
    const fetchMock = mockFetchRoutes({
      "GET /v1/settings": settingsFixture,
      "PATCH /v1/settings": settingsFixture,
    });
    const user = userEvent.setup();
    renderWithProviders(<RulesTab />);
    await screen.findByTestId("rules-flags");

    const graphV2 = screen.getByRole("checkbox", { name: "Toggle graph_v2" });
    expect(graphV2).toBeChecked();
    await user.click(graphV2);
    expect(graphV2).not.toBeChecked();

    const autoResolve = screen.getByRole("checkbox", {
      name: "Toggle conflict_auto_resolve",
    });
    await user.click(autoResolve);
    expect(autoResolve).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Save feature flags" }));

    await waitFor(() => {
      expect(patchBody(fetchMock)).toEqual({
        feature_flags: { conflict_auto_resolve: true, graph_v2: false },
      });
    });
  });

  it("shows 'no feature flags defined' when the flags object is empty", async () => {
    mockFetchRoutes({
      "GET /v1/settings": { ...settingsFixture, feature_flags: {} },
    });
    renderWithProviders(<RulesTab />);
    await screen.findByTestId("rules-flags");
    expect(screen.getByText("No feature flags defined.")).toBeInTheDocument();
  });
});
