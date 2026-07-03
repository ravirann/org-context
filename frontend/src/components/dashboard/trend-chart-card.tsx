import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { TrendPoint } from "@/lib/types";

type ChartKind = "line" | "area" | "bar";

interface TrendChartCardProps {
  title: string;
  data: TrendPoint[];
  kind: ChartKind;
  /** CSS color, e.g. "var(--chart-1)". */
  color: string;
  /** Formats tooltip / axis values (e.g. score 0..1 vs counts). */
  valueFormatter?: (value: number) => string;
  loading?: boolean;
}

function formatTick(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
}

const AXIS_TICK = { fontSize: 10, fill: "var(--muted-foreground)" } as const;

/** Small-multiple trend chart in a Card (~180px tall) for the dashboard. */
function TrendChartCard({
  title,
  data,
  kind,
  color,
  valueFormatter = (v) => String(v),
  loading = false,
}: TrendChartCardProps) {
  const tooltipFormatter = (value: number | string) =>
    valueFormatter(typeof value === "number" ? value : Number(value));

  const commonAxes = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
      <XAxis
        dataKey="date"
        tickFormatter={formatTick}
        tick={AXIS_TICK}
        tickLine={false}
        axisLine={{ stroke: "var(--border)" }}
        minTickGap={24}
      />
      <YAxis
        tick={AXIS_TICK}
        tickFormatter={(v: number) => valueFormatter(v)}
        tickLine={false}
        axisLine={false}
        width={36}
      />
      <Tooltip
        formatter={tooltipFormatter}
        labelFormatter={(label) => formatTick(String(label))}
        contentStyle={{
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          fontSize: 12,
          color: "var(--foreground)",
        }}
      />
    </>
  );

  let chart: React.ReactElement;
  if (kind === "line") {
    chart = (
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        {commonAxes}
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.75}
          dot={false}
          activeDot={{ r: 3 }}
          isAnimationActive={false}
        />
      </LineChart>
    );
  } else if (kind === "area") {
    chart = (
      <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        {commonAxes}
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.75}
          fill={color}
          fillOpacity={0.15}
          isAnimationActive={false}
        />
      </AreaChart>
    );
  } else {
    chart = (
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        {commonAxes}
        <Bar dataKey="value" fill={color} radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-[180px] w-full" />
        ) : data.length === 0 ? (
          <div className="flex h-[180px] items-center justify-center text-xs text-muted-foreground">
            No data for this period
          </div>
        ) : (
          <div className="h-[180px] w-full" aria-label={`${title} chart`} role="img">
            <ResponsiveContainer width="100%" height="100%">
              {chart}
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export { TrendChartCard };
