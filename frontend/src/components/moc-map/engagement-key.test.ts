/**
 * Reframe R-1 — THE KEYSPACE NO-CROSS-WIRE PIN (landmine #1).
 *
 * `task:<id>` in the engagement keyspace means AUTOMATION ponders — the
 * data already written says so (recency suggestions, dismissals). The
 * reframe's NEW entity (code `moc_job`, displayed "Task") must NEVER take
 * this prefix: when job ponders arrive (R-2) they use `job:<id>`. This pin
 * fails the build if anyone "cleans up" the prefix to match the display
 * name.
 */
import { describe, expect, it } from "vitest"

import { engagementKey } from "./useMapOverlays"

describe("the engagement keyspace (Reframe landmine #1)", () => {
  it("a plain overlay id is an AUTOMATION ponder — task: prefix, unchanged", () => {
    expect(engagementKey("abc-123", "manufacturing")).toBe("task:abc-123")
  })

  it("area + onboarding keys unchanged", () => {
    expect(engagementKey("area:Accounting", "manufacturing"))
      .toBe("area:manufacturing:Accounting")
    expect(engagementKey("onboarding:welcome-map", null))
      .toBe("onboarding:welcome-map")
  })

  it("job ponders (R-2) must NOT collide — the job: prefix is reserved", () => {
    // The pin's shape: whatever R-2 adds, a job overlay id must produce a
    // key that is NOT in the task: space. Today the convention reserves
    // the literal prefix; this assertion documents it.
    expect(engagementKey("job:xyz", "manufacturing")).not.toMatch(/^task:job:/)
  })
})
