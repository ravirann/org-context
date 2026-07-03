/**
 * Coverage for TrendChartCard (src/components/dashboard/trend-chart-card.tsx):
 * loading, empty, and populated states across all three chart kinds, plus the
 * default valueFormatter path and a custom valueFormatter. Recharts renders
 * an SVG in jsdom on mount; tick/axis formatters (formatTick, the YAxis
 * tickFormatter, and the default valueFormatter) all run synchronously during
 * that render.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrendChartCard } from "@/components/dashboard/trend-chart-card";
import type { TrendPoint } from "@/lib/types";

const data: TrendPoint[] = [
  { date: "2026-06-01", value: 0.81 },
  { date: "2026-06-15", value: 0.84 },
  { date: "2026-06-29", value: 0.87 },
];

describe("TrendChartCard", () => {
  it("shows a skeleton while loading", () => {
    render(<TrendChartCard title="Eval scores" data={data} kind="line" color="red" loading />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("Eval scores")).toBeInTheDocument();
  });

  it("shows an empty message when there is no data", () => {
    render(<TrendChartCard title="Eval scores" data={[]} kind="line" color="red" />);
    expect(screen.getByText("No data for this period")).toBeInTheDocument();
  });

  it("renders a line chart with the default value formatter", () => {
    render(<TrendChartCard title="Eval scores" data={data} kind="line" color="var(--chart-1)" />);
    expect(screen.getByRole("img", { name: "Eval scores chart" })).toBeInTheDocument();
  });

  it("renders an area chart with a custom value formatter", () => {
    render(
      <TrendChartCard
        title="Freshness"
        data={data}
        kind="area"
        color="var(--chart-2)"
        valueFormatter={(v) => `${Math.round(v * 100)}%`}
      />,
    );
    expect(screen.getByRole("img", { name: "Freshness chart" })).toBeInTheDocument();
  });

  it("renders a bar chart", () => {
    render(
      <TrendChartCard
        title="Packets per day"
        data={[
          { date: "2026-06-27", value: 42 },
          { date: "2026-06-28", value: 55 },
        ]}
        kind="bar"
        color="var(--chart-3)"
      />,
    );
    expect(screen.getByRole("img", { name: "Packets per day chart" })).toBeInTheDocument();
  });

  it("renders with a non-ISO date on the point (formatTick fallback)", () => {
    render(
      <TrendChartCard
        title="Odd dates"
        data={[{ date: "not-a-date", value: 1 }]}
        kind="line"
        color="red"
      />,
    );
    expect(screen.getByRole("img", { name: "Odd dates chart" })).toBeInTheDocument();
  });
});
