/**
 * DispatchMonitor — time-based default-day selection.
 *
 * `pickDefaultDayIndex` is the pure function driving the Smart
 * Stack's single-day default in Phase 3.2. Before 1pm tenant-local →
 * Today (index 0). At/after 1pm → Tomorrow (index 1). The 1pm pivot
 * matches the auto-finalize cron: once the day is locked for
 * tomorrow, the dispatcher's eye has shifted to tomorrow's plan.
 */

import { describe, expect, it } from "vitest"

import {
  TIME_BASED_DEFAULT_PIVOT_HOUR,
  pickDefaultDayIndex,
} from "./monitor"


describe("pickDefaultDayIndex — time-based Smart Stack default", () => {
  it("pivot hour is 13 (1pm tenant-local)", () => {
    expect(TIME_BASED_DEFAULT_PIVOT_HOUR).toBe(13)
  })

  it("before 1pm → Today (index 0)", () => {
    expect(pickDefaultDayIndex(0)).toBe(0)   // midnight
    expect(pickDefaultDayIndex(6)).toBe(0)   // morning
    expect(pickDefaultDayIndex(12)).toBe(0)  // noon
  })

  it("at 1pm → Tomorrow (index 1) — boundary is inclusive on the later side", () => {
    expect(pickDefaultDayIndex(13)).toBe(1)
  })

  it("after 1pm → Tomorrow (index 1)", () => {
    expect(pickDefaultDayIndex(14)).toBe(1)
    expect(pickDefaultDayIndex(17)).toBe(1)  // 5pm
    expect(pickDefaultDayIndex(23)).toBe(1)  // 11pm
  })
})
