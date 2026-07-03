import { describe, expect, it } from "vitest";

import {
  cn,
  formatDate,
  formatDateTime,
  formatNumber,
  scoreColor,
  timeAgo,
} from "@/lib/utils";

describe("cn", () => {
  it("merges conditional classes", () => {
    const includeB = Boolean(process.env.NEVER_SET);
    expect(cn("a", includeB && "b", "c")).toBe("a c");
  });

  it("resolves tailwind conflicts (last wins)", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-red-500", "text-emerald-500")).toBe("text-emerald-500");
  });
});

describe("formatDate / formatDateTime", () => {
  it("formats ISO dates", () => {
    expect(formatDate("2026-07-01T10:00:00Z")).toMatch(/Jul 1, 2026/);
    expect(formatDateTime("2026-07-01T10:00:00Z")).toContain("2026");
  });

  it("returns em dash for nullish or invalid input", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("not-a-date")).toBe("—");
    expect(formatDateTime(null)).toBe("—");
  });
});

describe("formatNumber", () => {
  it("formats standard and compact numbers", () => {
    expect(formatNumber(1234)).toBe("1,234");
    expect(formatNumber(12345)).toBe("12.3K");
    expect(formatNumber(0)).toBe("0");
  });

  it("handles nullish", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
  });
});

describe("timeAgo", () => {
  const now = new Date("2026-07-03T12:00:00Z").getTime();

  it("covers all buckets", () => {
    expect(timeAgo("2026-07-03T11:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-07-03T11:55:00Z", now)).toBe("5m ago");
    expect(timeAgo("2026-07-03T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-07-01T12:00:00Z", now)).toBe("2d ago");
    expect(timeAgo("2026-05-01T12:00:00Z", now)).toBe("2mo ago");
    expect(timeAgo("2024-07-01T12:00:00Z", now)).toBe("2y ago");
  });

  it("handles nullish and invalid", () => {
    expect(timeAgo(null, now)).toBe("—");
    expect(timeAgo("garbage", now)).toBe("—");
  });
});

describe("scoreColor", () => {
  it("maps score bands to semantic classes", () => {
    expect(scoreColor(0.95)).toContain("emerald");
    expect(scoreColor(0.8)).toContain("emerald");
    expect(scoreColor(0.6)).toContain("amber");
    expect(scoreColor(0.2)).toContain("red");
  });
});
