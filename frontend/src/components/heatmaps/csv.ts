import type { TeamRow } from "@/components/heatmaps/aggregate";
import type { ContextDebtRow, HeatmapRow, OwnershipRow } from "@/lib/types";

/** CSV cell value; null/undefined render as empty. */
export type CsvValue = string | number | boolean | null | undefined;

function escapeCsvField(value: CsvValue): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (/[",\n\r]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

/** Build an RFC-4180-ish CSV string ("\n" line endings, trailing newline). */
export function toCsv(headers: string[], rows: CsvValue[][]): string {
  const lines = [headers, ...rows].map((row) =>
    row.map(escapeCsvField).join(","),
  );
  return `${lines.join("\n")}\n`;
}

/** User-activity grid → CSV (one column per day). */
export function userHeatmapCsv(rows: HeatmapRow[], days: string[]): string {
  return toCsv(
    ["user", "team", ...days, "total"],
    rows.map((row) => {
      const byDay = new Map(row.cells.map((c) => [c.day, c.value]));
      return [
        row.user_name,
        row.team_name,
        ...days.map((day) => byDay.get(day) ?? 0),
        row.total,
      ];
    }),
  );
}

/** Team-activity grid → CSV (one column per day). */
export function teamHeatmapCsv(rows: TeamRow[], days: string[]): string {
  return toCsv(
    ["team", "users", ...days, "total"],
    rows.map((row) => {
      const byDay = new Map(row.cells.map((c) => [c.day, c.value]));
      return [
        row.team_name,
        row.user_count,
        ...days.map((day) => byDay.get(day) ?? 0),
        row.total,
      ];
    }),
  );
}

export function ownershipCsv(rows: OwnershipRow[]): string {
  return toCsv(
    ["key", "owner_team", "doc_count", "owners", "coverage_score", "last_activity_at"],
    rows.map((row) => [
      row.key,
      row.owner_team,
      row.doc_count,
      row.owner_user_names.join("; "),
      row.coverage_score,
      row.last_activity_at,
    ]),
  );
}

export function debtCsv(rows: ContextDebtRow[]): string {
  return toCsv(
    [
      "key",
      "repo",
      "service",
      "team",
      "stale_count",
      "conflict_count",
      "rejected_count",
      "failed_runs",
      "missing_owner",
      "debt_score",
    ],
    rows.map((row) => [
      row.key,
      row.repo,
      row.service,
      row.team_name,
      row.stale_count,
      row.conflict_count,
      row.rejected_count,
      row.failed_runs,
      row.missing_owner,
      row.debt_score,
    ]),
  );
}

/** Trigger a client-side download of a CSV string. */
export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
