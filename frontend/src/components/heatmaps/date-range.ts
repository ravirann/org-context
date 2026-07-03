/** Date-range preset helpers for the heatmap controls. */

export const RANGE_PRESETS = [14, 30, 60, 90] as const;

export type RangePreset = (typeof RANGE_PRESETS)[number];

/** ISO date (YYYY-MM-DD) `daysAgo` days before `now` (UTC). */
export function isoDaysAgo(daysAgo: number, now: Date = new Date()): string {
  const date = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000);
  return date.toISOString().slice(0, 10);
}

/** `{from, to}` ISO date params for a preset of N days ending today. */
export function dateRange(
  days: number,
  now: Date = new Date(),
): { from: string; to: string } {
  return { from: isoDaysAgo(days, now), to: isoDaysAgo(0, now) };
}
