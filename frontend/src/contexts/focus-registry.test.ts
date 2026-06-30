/**
 * Focus registry — vitest unit tests.
 *
 * Pattern B registry. Session 2 seeds 5 stub Focuses at module load;
 * tests verify register/lookup/replace semantics + that the 5 stubs
 * are present + type-union exhaustiveness (compile-time via
 * `satisfies`).
 */

import { beforeEach, describe, expect, it } from "vitest"

import {
  _resetRegistryForTests,
  getFocusConfig,
  listFocusConfigs,
  registerFocus,
  type CoreMode,
  type FocusConfig,
} from "./focus-registry"


describe("focus-registry — seeded stubs", () => {
  it("has all 5 canonical core modes registered as test focuses", () => {
    const configs = listFocusConfigs()
    const modes = new Set(configs.map((c) => c.mode))
    // All five canonical modes are present (at least one focus each).
    // Set, not exact list — real focuses (e.g. decision-triage, a second
    // triageQueue) register alongside the stubs. Matches the CoreMode union.
    for (const m of ["editCanvas", "kanban", "matrix", "singleRecord", "triageQueue"]) {
      expect(modes.has(m as (typeof configs)[number]["mode"])).toBe(true)
    }
  })

  it("each seeded stub has the expected id + mode pairing", () => {
    expect(getFocusConfig("test-kanban")?.mode).toBe("kanban")
    expect(getFocusConfig("test-single-record")?.mode).toBe("singleRecord")
    expect(getFocusConfig("test-edit-canvas")?.mode).toBe("editCanvas")
    expect(getFocusConfig("test-triage-queue")?.mode).toBe("triageQueue")
    expect(getFocusConfig("test-matrix")?.mode).toBe("matrix")
  })

  it("decision-triage focus binds to the workflow_review_triage queue (queueId as data)", () => {
    const decision = getFocusConfig("decision-triage")
    expect(decision?.mode).toBe("triageQueue")
    expect(decision?.displayName).toBe("Decision Triage")
    // The Decide-as-Focus binding lives in config, not hardcode (3a.1-B).
    expect(decision?.queueId).toBe("workflow_review_triage")
  })

  it("returns null for unknown focus ids", () => {
    expect(getFocusConfig("nonexistent")).toBeNull()
    expect(getFocusConfig("")).toBeNull()
  })
})


describe("focus-registry — register/replace semantics", () => {
  beforeEach(() => {
    // Full reset — then re-register a minimal stub for assertion.
    _resetRegistryForTests()
  })

  it("registerFocus() adds a new config retrievable by id", () => {
    registerFocus({
      id: "test-new",
      mode: "kanban",
      displayName: "Fresh stub",
    })
    expect(getFocusConfig("test-new")?.displayName).toBe("Fresh stub")
  })

  it("registering the same id replaces the prior config (idempotent)", () => {
    registerFocus({ id: "dup", mode: "kanban", displayName: "v1" })
    registerFocus({ id: "dup", mode: "matrix", displayName: "v2" })
    const config = getFocusConfig("dup")
    expect(config?.mode).toBe("matrix")
    expect(config?.displayName).toBe("v2")
    // listFocusConfigs returns only one entry for this id.
    expect(listFocusConfigs().filter((c) => c.id === "dup")).toHaveLength(1)
  })

  it("listFocusConfigs preserves insertion order", () => {
    registerFocus({ id: "first", mode: "kanban", displayName: "A" })
    registerFocus({ id: "second", mode: "matrix", displayName: "B" })
    registerFocus({ id: "third", mode: "triageQueue", displayName: "C" })
    const ids = listFocusConfigs().map((c) => c.id)
    expect(ids).toEqual(["first", "second", "third"])
  })
})


describe("focus-registry — type-union exhaustiveness (compile-time)", () => {
  it("CoreMode literal values match the 5 canonical modes", () => {
    // Compile-time check: each listed mode satisfies the CoreMode
    // type. If a mode is removed from the union, this array becomes
    // invalid and tsc fails the build — ensuring tests stay in sync
    // with the type definition.
    const allModes: CoreMode[] = [
      "kanban",
      "singleRecord",
      "editCanvas",
      "triageQueue",
      "matrix",
    ] satisfies CoreMode[]
    expect(allModes).toHaveLength(5)
  })

  it("FocusConfig requires id + mode + displayName", () => {
    // Compile-time check: this would fail tsc if any required field
    // were dropped from the FocusConfig interface.
    const config: FocusConfig = {
      id: "x",
      mode: "kanban",
      displayName: "y",
    }
    expect(config.id).toBe("x")
  })
})
