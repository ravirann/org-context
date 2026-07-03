import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import NotFoundPage from "@/pages/not-found";

import { renderWithProviders } from "../utils";

describe("NotFoundPage", () => {
  it("renders the 404 content with navigation actions", () => {
    renderWithProviders(<NotFoundPage />, { route: "/definitely-not-a-page" });

    expect(screen.getByTestId("page-not-found")).toBeInTheDocument();
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("This page does not exist")).toBeInTheDocument();
    expect(screen.getByText(/The link may be stale/)).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /Back to dashboard/ })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: /Search the explorer/ })).toHaveAttribute(
      "href",
      "/explorer",
    );
  });

  it("keeps the page heading contract", () => {
    renderWithProviders(<NotFoundPage />);

    expect(
      screen.getByRole("heading", { name: "Page not found" }),
    ).toBeInTheDocument();
    expect(document.title).toContain("Not Found");
  });
});
