import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { EvalRun } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const BAR_COLORS = ["var(--chart-3)", "var(--chart-1)"];

interface ComparisonDatum {
  name: string;
  value: number;
}

/**
 * Two-bar comparison (baseline vs context engine) used for avg score and
 * total token usage on the evals page.
 */
function ComparisonBarChart({
  data,
  domainMax,
}: {
  data: ComparisonDatum[];
  domainMax?: number;
}) {
  return (
    <div className="h-36 w-full" data-testid="comparison-bar-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            axisLine={false}
            tickLine={false}
            domain={domainMax !== undefined ? [0, domainMax] : undefined}
          />
          <ChartTooltip
            cursor={{ fill: "var(--muted)", opacity: 0.4 }}
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={56}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={BAR_COLORS[index % BAR_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Avg-score trend line across historical eval runs (oldest → newest). */
function ScoreTrendChart({ runs }: { runs: EvalRun[] }) {
  const data = runs
    .filter((run) => run.summary !== null)
    .map((run) => ({
      date: formatDate(run.started_at),
      score: run.summary?.avg_score ?? 0,
    }))
    .reverse();

  return (
    <div className="h-48 w-full" data-testid="score-trend-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            axisLine={false}
            tickLine={false}
          />
          <ChartTooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={{ r: 2.5, fill: "var(--chart-1)" }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export { ComparisonBarChart, ScoreTrendChart };
