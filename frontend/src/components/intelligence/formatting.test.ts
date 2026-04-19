/**
 * Unit tests for the Intelligence formatting helpers.
 *
 * These are pure functions that render currency / latency / percentages /
 * relative time across the admin UI. Small, stable, high-leverage — exactly
 * the kind of code a regression in would be hard to catch by eye (e.g. a
 * change that stringifies differently at cost boundaries).
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  formatAbsoluteTime,
  formatCost,
  formatLatency,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  formatTotalCost,
} from "./formatting";

describe("formatCost", () => {
  it("returns em-dash for null / undefined / empty string", () => {
    expect(formatCost(null)).toBe("—");
    expect(formatCost(undefined)).toBe("—");
    expect(formatCost("")).toBe("—");
  });

  it("returns em-dash for non-finite", () => {
    expect(formatCost(NaN)).toBe("—");
    expect(formatCost(Infinity)).toBe("—");
    expect(formatCost("not a number")).toBe("—");
  });

  it("returns $0 for zero", () => {
    expect(formatCost(0)).toBe("$0");
    expect(formatCost("0")).toBe("$0");
  });

  it("uses digits precision for values below $0.01", () => {
    expect(formatCost(0.0001)).toBe("$0.0001");
    expect(formatCost(0.003, 4)).toBe("$0.0030");
    expect(formatCost(0.0005, 6)).toBe("$0.000500");
  });

  it("uses 2-decimal precision for values $0.01 and above", () => {
    expect(formatCost(0.01)).toBe("$0.01");
    expect(formatCost(1)).toBe("$1.00");
    expect(formatCost(1234.5)).toBe("$1234.50");
  });

  it("accepts string Decimal-formatted numbers (the API serialization)", () => {
    expect(formatCost("0.0025")).toBe("$0.0025");
    expect(formatCost("12.50")).toBe("$12.50");
  });
});

describe("formatTotalCost", () => {
  it("returns em-dash for null / undefined / non-finite", () => {
    expect(formatTotalCost(null)).toBe("—");
    expect(formatTotalCost(undefined)).toBe("—");
    expect(formatTotalCost("bogus")).toBe("—");
  });

  it("thousands-separates values over $100", () => {
    expect(formatTotalCost(1234)).toBe("$1,234");
    expect(formatTotalCost(1_500_000)).toBe("$1,500,000");
  });

  it("uses 2-decimal precision for values $1–$99", () => {
    expect(formatTotalCost(42.7)).toBe("$42.70");
    expect(formatTotalCost(1)).toBe("$1.00");
  });

  it("uses 4-decimal precision for sub-$1 values", () => {
    expect(formatTotalCost(0.5)).toBe("$0.5000");
    expect(formatTotalCost(0.0001)).toBe("$0.0001");
  });
});

describe("formatLatency", () => {
  it("returns em-dash for null / undefined", () => {
    expect(formatLatency(null)).toBe("—");
    expect(formatLatency(undefined)).toBe("—");
  });

  it("uses ms below 1 second", () => {
    expect(formatLatency(0)).toBe("0ms");
    expect(formatLatency(42)).toBe("42ms");
    expect(formatLatency(999)).toBe("999ms");
  });

  it("rounds fractional ms to integer", () => {
    expect(formatLatency(42.6)).toBe("43ms");
  });

  it("uses seconds with 2 decimals for >= 1 second", () => {
    expect(formatLatency(1000)).toBe("1.00s");
    expect(formatLatency(1234)).toBe("1.23s");
    expect(formatLatency(60_000)).toBe("60.00s");
  });
});

describe("formatNumber", () => {
  it("returns em-dash for null / undefined", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
  });

  it("formats integers with en-US thousand separators", () => {
    expect(formatNumber(1000)).toBe("1,000");
    expect(formatNumber(1_234_567)).toBe("1,234,567");
    expect(formatNumber(0)).toBe("0");
  });
});

describe("formatPercent", () => {
  it("returns em-dash for null / undefined", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(undefined)).toBe("—");
  });

  it("scales fraction to percent with default 1 digit", () => {
    expect(formatPercent(0)).toBe("0.0%");
    expect(formatPercent(0.5)).toBe("50.0%");
    expect(formatPercent(1)).toBe("100.0%");
    expect(formatPercent(0.0567)).toBe("5.7%");
  });

  it("respects the digits parameter", () => {
    expect(formatPercent(0.12345, 2)).toBe("12.35%");
    expect(formatPercent(0.5, 0)).toBe("50%");
  });
});

describe("formatRelativeTime", () => {
  // Freeze time so relative assertions are deterministic across runs.
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-19T12:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows seconds for under 1 minute", () => {
    expect(formatRelativeTime("2026-04-19T11:59:30Z")).toBe("30s ago");
  });

  it("shows minutes for under 1 hour", () => {
    expect(formatRelativeTime("2026-04-19T11:45:00Z")).toBe("15m ago");
  });

  it("shows hours for under 1 day", () => {
    expect(formatRelativeTime("2026-04-19T06:00:00Z")).toBe("6h ago");
  });

  it("shows days for under 1 week", () => {
    expect(formatRelativeTime("2026-04-16T12:00:00Z")).toBe("3d ago");
  });

  it("falls back to locale date for ≥ 1 week", () => {
    const result = formatRelativeTime("2026-04-10T12:00:00Z");
    // Locale-specific format — just assert it's NOT a relative phrase
    expect(result).not.toMatch(/ago$/);
  });
});

describe("formatAbsoluteTime", () => {
  it("returns a locale-formatted string (non-empty)", () => {
    const result = formatAbsoluteTime("2026-04-19T12:34:56Z");
    // Locale renders differently across machines — assert it has parts
    expect(result.length).toBeGreaterThan(5);
    expect(result).toMatch(/2026/);
  });
});
