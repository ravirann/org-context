import { useMemo } from "react";

import type { HeatmapCell } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Dense CSS-grid activity heatmap: sticky left label column, one square cell
 * per day, 5-step intensity scale built from the --chart-2 palette var.
 */

export interface HeatmapGridRow {
  id: string;
  name: string;
  subtext?: string | null;
  cells: HeatmapCell[];
  total: number;
}

/** 0 (no activity) … 4 (max) intensity step for a cell. */
export function intensityStep(value: number, max: number): 0 | 1 | 2 | 3 | 4 {
  if (value <= 0 || max <= 0) return 0;
  const step = Math.ceil((value / max) * 4);
  return Math.min(4, Math.max(1, step)) as 1 | 2 | 3 | 4;
}

const STEP_BACKGROUND: Record<number, string> = {
  0: "var(--muted)",
  1: "color-mix(in oklab, var(--chart-2) 30%, var(--muted))",
  2: "color-mix(in oklab, var(--chart-2) 55%, var(--muted))",
  3: "color-mix(in oklab, var(--chart-2) 80%, var(--muted))",
  4: "var(--chart-2)",
};

/** "2026-07-01" -> "7/1" (tiny header label). */
function shortDay(day: string): string {
  const [, month, date] = day.split("-");
  return `${Number(month)}/${Number(date)}`;
}

interface HeatmapGridProps {
  rows: HeatmapGridRow[];
  days: string[];
  onCellClick?: (row: HeatmapGridRow, cell: HeatmapCell) => void;
  "data-testid"?: string;
}

export function HeatmapGrid({
  rows,
  days,
  onCellClick,
  "data-testid": testId,
}: HeatmapGridProps) {
  const max = useMemo(
    () =>
      rows.reduce(
        (m, row) => row.cells.reduce((mm, c) => Math.max(mm, c.value), m),
        0,
      ),
    [rows],
  );

  // Label every Nth day so headers stay readable on long ranges.
  const labelEvery = Math.max(1, Math.ceil(days.length / 12));

  return (
    <div data-testid={testId} className="overflow-x-auto rounded-lg border">
      <div
        role="grid"
        aria-rowcount={rows.length + 1}
        className="grid w-max min-w-full gap-px bg-border/40 p-px"
        style={{
          gridTemplateColumns: `minmax(11rem, 14rem) repeat(${days.length}, 1.125rem) 3.5rem`,
        }}
      >
        {/* header row */}
        <div
          role="columnheader"
          className="sticky left-0 z-10 bg-background px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
        >
          User / day
        </div>
        {days.map((day, i) => (
          <div
            key={day}
            role="columnheader"
            title={day}
            className="flex items-end justify-center bg-background pb-0.5 text-[9px] leading-none text-muted-foreground"
          >
            {i % labelEvery === 0 ? shortDay(day) : ""}
          </div>
        ))}
        <div
          role="columnheader"
          className="bg-background px-1 py-1 text-right text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
        >
          Total
        </div>

        {/* data rows */}
        {rows.map((row) => {
          const byDay = new Map(row.cells.map((c) => [c.day, c.value]));
          return (
            <RowCells
              key={row.id}
              row={row}
              days={days}
              byDay={byDay}
              max={max}
              onCellClick={onCellClick}
            />
          );
        })}
      </div>
    </div>
  );
}

interface RowCellsProps {
  row: HeatmapGridRow;
  days: string[];
  byDay: Map<string, number>;
  max: number;
  onCellClick?: (row: HeatmapGridRow, cell: HeatmapCell) => void;
}

function RowCells({ row, days, byDay, max, onCellClick }: RowCellsProps) {
  return (
    <>
      <div
        role="rowheader"
        className="sticky left-0 z-10 flex min-w-0 flex-col justify-center bg-background px-2 py-0.5"
      >
        <span className="truncate text-xs font-medium">{row.name}</span>
        {row.subtext ? (
          <span className="truncate text-[10px] text-muted-foreground">
            {row.subtext}
          </span>
        ) : null}
      </div>
      {days.map((day) => {
        const value = byDay.get(day) ?? 0;
        const step = intensityStep(value, max);
        const label = `${row.name} · ${day}: ${value}`;
        return (
          <button
            key={day}
            type="button"
            role="gridcell"
            title={label}
            aria-label={label}
            data-testid={`hm-cell-${row.id}-${day}`}
            data-intensity={step}
            disabled={!onCellClick}
            onClick={() => onCellClick?.(row, { day, value })}
            className={cn(
              "m-px size-4 rounded-[3px] transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              onCellClick && "cursor-pointer hover:scale-110",
            )}
            style={{ background: STEP_BACKGROUND[step] }}
          />
        );
      })}
      <div
        role="gridcell"
        className="flex items-center justify-end bg-background px-1 text-xs tabular-nums text-muted-foreground"
      >
        {row.total}
      </div>
    </>
  );
}
