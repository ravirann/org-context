import type { HeatmapCell, HeatmapRow } from "@/lib/types";

/** A user-activity row rolled up to its team. */
export interface TeamRow {
  team_name: string;
  cells: HeatmapCell[];
  total: number;
  user_count: number;
}

export const NO_TEAM_LABEL = "No team";

/**
 * Aggregate user heatmap rows by team (client-side): cell values are summed
 * per day, rows are sorted by total desc (name asc as tiebreak). Users with
 * no team are grouped under "No team".
 */
export function aggregateByTeam(rows: HeatmapRow[]): TeamRow[] {
  const teams = new Map<
    string,
    { days: Map<string, number>; total: number; user_count: number }
  >();

  for (const row of rows) {
    const key = row.team_name ?? NO_TEAM_LABEL;
    let team = teams.get(key);
    if (!team) {
      team = { days: new Map(), total: 0, user_count: 0 };
      teams.set(key, team);
    }
    team.user_count += 1;
    team.total += row.total;
    for (const cell of row.cells) {
      team.days.set(cell.day, (team.days.get(cell.day) ?? 0) + cell.value);
    }
  }

  return [...teams.entries()]
    .map(([team_name, { days, total, user_count }]) => ({
      team_name,
      total,
      user_count,
      cells: [...days.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([day, value]) => ({ day, value })),
    }))
    .sort(
      (a, b) => b.total - a.total || a.team_name.localeCompare(b.team_name),
    );
}
