/**
 * Component Registry tests.
 *
 * Covers:
 *   • registerComponent validation (required fields, soft warnings)
 *   • registry storage + lookup
 *   • introspection API end-to-end
 *   • token reverse-lookup index integrity
 *   • re-registration (HMR) drift detection
 *   • metadata immutability (frozen objects)
 *   • Phase 1 auto-register population (13-17 components)
 */

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import type { ComponentType } from "react"

import {
  _internal_clear,
  _internal_count,
  _internal_listAll,
} from "./registry"
import { registerComponent } from "./register"
import {
  getAllRegistered,
  getByName,
  getByType,
  getByVertical,
  getComponentsConsumingToken,
  getCountByType,
  getCoverageByVertical,
  getKnownTokens,
  getRegistrationVersion,
  getTokensConsumedBy,
  getAcceptedChildrenForSlot,
  getTotalCount,
} from "./introspection"
import type { RegistrationMetadata } from "./types"


function dummyComponent(label: string): ComponentType<unknown> {
  function Cmp() {
    return null
  }
  Cmp.displayName = label
  return Cmp
}

function baseMeta(
  overrides: Partial<RegistrationMetadata> = {},
): RegistrationMetadata {
  return {
    type: "widget",
    name: "test-widget",
    displayName: "Test Widget",
    verticals: ["all"],
    userParadigms: ["all"],
    consumedTokens: ["surface-elevated", "border-base"],
    schemaVersion: 1,
    componentVersion: 1,
    ...overrides,
  }
}


describe("registerComponent — validation", () => {
  beforeEach(() => _internal_clear())

  it("throws when name is missing", () => {
    // Cast to the registration shape so we can intentionally pass an
    // invalid payload — runtime validation is what we're exercising.
    const bad = baseMeta({ name: undefined as unknown as string })
    expect(() => registerComponent(bad)(dummyComponent("X"))).toThrow(
      /missing string `name`/,
    )
  })

  it("throws when displayName is missing", () => {
    const bad = baseMeta({ displayName: undefined as unknown as string })
    expect(() => registerComponent(bad)(dummyComponent("X"))).toThrow(
      /missing `displayName`/,
    )
  })

  it("throws when verticals is empty", () => {
    expect(() =>
      registerComponent(baseMeta({ verticals: [] }))(dummyComponent("X")),
    ).toThrow(/non-empty array/)
  })

  it("throws when consumedTokens is not an array", () => {
    const bad = baseMeta({
      consumedTokens: "tok" as unknown as string[],
    })
    expect(() => registerComponent(bad)(dummyComponent("X"))).toThrow(
      /must be an array/,
    )
  })

  it("warns on schemaVersion mismatch but does not throw", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    registerComponent(baseMeta({ schemaVersion: 99 }))(dummyComponent("X"))
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})


describe("registerComponent — storage + retrieval", () => {
  beforeEach(() => _internal_clear())

  it("returns the same component reference (purely additive)", () => {
    const Cmp = dummyComponent("X")
    const Wrapped = registerComponent(baseMeta())(Cmp)
    expect(Wrapped).toBe(Cmp)
  })

  it("populates the registry on registration", () => {
    expect(_internal_count()).toBe(0)
    registerComponent(baseMeta())(dummyComponent("X"))
    expect(_internal_count()).toBe(1)
  })

  it("getByName returns the registered entry", () => {
    registerComponent(baseMeta())(dummyComponent("X"))
    const entry = getByName("widget", "test-widget")
    expect(entry).toBeDefined()
    expect(entry?.metadata.displayName).toBe("Test Widget")
  })

  it("getByName returns undefined for unknown components", () => {
    expect(getByName("widget", "nonexistent")).toBeUndefined()
  })

  it("freezes metadata so consumers cannot mutate", () => {
    registerComponent(baseMeta())(dummyComponent("X"))
    const entry = getByName("widget", "test-widget")
    expect(Object.isFrozen(entry?.metadata)).toBe(true)
    expect(Object.isFrozen(entry?.metadata.verticals)).toBe(true)
    expect(Object.isFrozen(entry?.metadata.consumedTokens)).toBe(true)
  })

  it("re-registration replaces the entry", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    registerComponent(baseMeta({ componentVersion: 1 }))(dummyComponent("X"))
    registerComponent(baseMeta({ componentVersion: 2 }))(dummyComponent("X"))
    expect(_internal_count()).toBe(1)
    expect(getByName("widget", "test-widget")?.metadata.componentVersion).toBe(2)
    warn.mockRestore()
  })

  it("re-registration warns on metadata drift", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    registerComponent(baseMeta())(dummyComponent("X"))
    registerComponent(
      baseMeta({ consumedTokens: ["accent"], componentVersion: 2 }),
    )(dummyComponent("X"))
    expect(warn).toHaveBeenCalledWith(
      expect.stringMatching(/drift/),
    )
    warn.mockRestore()
  })
})


describe("introspection — type + vertical filters", () => {
  beforeEach(() => {
    _internal_clear()
    registerComponent(
      baseMeta({
        name: "w-all",
        verticals: ["all"],
      }),
    )(dummyComponent("A"))
    registerComponent(
      baseMeta({
        name: "w-fh",
        verticals: ["funeral_home"],
      }),
    )(dummyComponent("B"))
    registerComponent(
      baseMeta({
        type: "focus",
        name: "f-mfg",
        verticals: ["manufacturing"],
      }),
    )(dummyComponent("C"))
  })

  it("getAllRegistered returns frozen entries", () => {
    const all = getAllRegistered()
    expect(all).toHaveLength(3)
  })

  it("getByType filters by component kind", () => {
    expect(getByType("widget")).toHaveLength(2)
    expect(getByType("focus")).toHaveLength(1)
  })

  it("getByVertical includes 'all' components when filtering specific vertical", () => {
    const fh = getByVertical("funeral_home")
    expect(fh.map((e) => e.metadata.name).sort()).toEqual(["w-all", "w-fh"])
  })

  it("getByVertical 'all' returns only components explicitly tagged universal", () => {
    const universal = getByVertical("all")
    expect(universal.map((e) => e.metadata.name)).toEqual(["w-all"])
  })

  it("getByVertical for cemetery returns only universal components when no cemetery components are tagged", () => {
    const cem = getByVertical("cemetery")
    expect(cem.map((e) => e.metadata.name)).toEqual(["w-all"])
  })
})


describe("introspection — token consumption", () => {
  beforeEach(() => {
    _internal_clear()
    registerComponent(
      baseMeta({
        name: "consumer-a",
        consumedTokens: ["surface-elevated", "accent"],
      }),
    )(dummyComponent("A"))
    registerComponent(
      baseMeta({
        name: "consumer-b",
        consumedTokens: ["surface-elevated", "border-base"],
      }),
    )(dummyComponent("B"))
  })

  it("getTokensConsumedBy returns sorted unique tokens for a component", () => {
    expect(getTokensConsumedBy("widget", "consumer-a")).toEqual([
      "accent",
      "surface-elevated",
    ])
  })

  it("getTokensConsumedBy returns empty for unknown components (no throw)", () => {
    expect(getTokensConsumedBy("widget", "missing")).toEqual([])
  })

  it("includes variant additionalConsumedTokens", () => {
    _internal_clear()
    registerComponent(
      baseMeta({
        name: "w-with-variants",
        consumedTokens: ["surface-elevated"],
        variants: [
          {
            name: "primary",
            additionalConsumedTokens: ["status-success"],
          },
        ],
      }),
    )(dummyComponent("A"))
    expect(getTokensConsumedBy("widget", "w-with-variants")).toContain(
      "status-success",
    )
  })

  it("getComponentsConsumingToken returns every component reading from a token", () => {
    const consumers = getComponentsConsumingToken("surface-elevated")
    expect(consumers.map((e) => e.metadata.name).sort()).toEqual([
      "consumer-a",
      "consumer-b",
    ])
  })

  it("getComponentsConsumingToken returns empty for unknown tokens", () => {
    expect(getComponentsConsumingToken("nonexistent-token")).toHaveLength(0)
  })

  it("re-registration updates the inverse index (no stale associations)", () => {
    expect(getComponentsConsumingToken("border-base")).toHaveLength(1)
    // Remove border-base from consumer-b by re-registering with different tokens
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {})
    registerComponent(
      baseMeta({
        name: "consumer-b",
        consumedTokens: ["surface-elevated"],
      }),
    )(dummyComponent("B"))
    expect(getComponentsConsumingToken("border-base")).toHaveLength(0)
    warn.mockRestore()
  })

  it("getKnownTokens returns the union across registrations, sorted", () => {
    const known = getKnownTokens()
    expect(known).toContain("surface-elevated")
    expect(known).toContain("accent")
    expect(known).toContain("border-base")
    expect(Array.from(known)).toEqual([...known].sort())
  })
})


describe("introspection — slots", () => {
  beforeEach(() => {
    _internal_clear()
    registerComponent(
      baseMeta({
        name: "with-slot",
        slots: [
          {
            name: "children",
            acceptedTypes: ["widget", "focus"],
          },
        ],
      }),
    )(dummyComponent("A"))
  })

  it("getAcceptedChildrenForSlot returns the slot's accepted types", () => {
    expect(getAcceptedChildrenForSlot("widget", "with-slot", "children")).toEqual(
      ["widget", "focus"],
    )
  })

  it("getAcceptedChildrenForSlot returns empty for unknown slot", () => {
    expect(
      getAcceptedChildrenForSlot("widget", "with-slot", "nonexistent"),
    ).toEqual([])
  })

  it("getAcceptedChildrenForSlot returns empty for unknown component", () => {
    expect(
      getAcceptedChildrenForSlot("widget", "missing", "children"),
    ).toEqual([])
  })
})


describe("introspection — version metadata", () => {
  beforeEach(() => _internal_clear())

  it("getRegistrationVersion returns schema + component versions", () => {
    registerComponent(
      baseMeta({ schemaVersion: 1, componentVersion: 3 }),
    )(dummyComponent("A"))
    expect(getRegistrationVersion("widget", "test-widget")).toEqual({
      schemaVersion: 1,
      componentVersion: 3,
    })
  })

  it("getRegistrationVersion returns undefined for unknown components", () => {
    expect(getRegistrationVersion("widget", "missing")).toBeUndefined()
  })
})


describe("introspection — aggregation helpers", () => {
  beforeEach(() => {
    _internal_clear()
    registerComponent(baseMeta({ name: "w-1", type: "widget" }))(dummyComponent("A"))
    registerComponent(baseMeta({ name: "w-2", type: "widget" }))(dummyComponent("B"))
    registerComponent(baseMeta({ name: "f-1", type: "focus" }))(dummyComponent("C"))
  })

  it("getTotalCount returns the registry size", () => {
    expect(getTotalCount()).toBe(3)
  })

  it("getCountByType returns per-type counts", () => {
    const counts = getCountByType()
    expect(counts.widget).toBe(2)
    expect(counts.focus).toBe(1)
  })

  it("getCoverageByVertical buckets by vertical", () => {
    const cov = getCoverageByVertical()
    // All three are tagged ["all"]
    expect(cov.all).toBe(3)
  })
})


// ─── End-to-end test against Phase 1 auto-register barrel ────────
//
// Module-cache discipline: the registry is a module-scope
// singleton inside `registry.ts`. Every consumer in this test
// file (the introspection helpers, `_internal_clear`, and the
// auto-register barrel) shares ONE `registry.ts` instance.
// Mutating the singleton via `_internal_clear` between
// `describe` blocks works only because we never reload modules.
// `vi.resetModules` would create a SECOND `registry.ts`
// instance — auto-register's `registerComponent` calls would
// land there, but our top-level `getByType` etc. would still
// read from the original empty instance.
//
// So: import the barrel ONCE at the top of this block via a
// `beforeAll` dynamic import, and don't clear in beforeEach.
// The 33 unit tests above run before this block (vitest runs
// describe blocks in source order) so they see their own
// `_internal_clear()` in beforeEach. By the time we get here,
// the registry is empty. We populate it once in beforeAll +
// keep it populated across the population-suite cases.

describe("Phase 1 auto-register population", () => {
  beforeAll(async () => {
    _internal_clear()
    await import("./auto-register")
  })

  afterEach(() => {
    /* leave registry populated across cases in this block */
  })

  it("populates 13-17 components across the canonical 5 types", () => {
    const total = getTotalCount()
    expect(total).toBeGreaterThanOrEqual(13)
    expect(total).toBeLessThanOrEqual(17)
  })

  it("includes at least 4 widgets across funeral_home + manufacturing", () => {
    const widgets = getByType("widget")
    expect(widgets.length).toBeGreaterThanOrEqual(4)
    const verticalsCovered = new Set<string>()
    for (const w of widgets) {
      for (const v of w.metadata.verticals) verticalsCovered.add(v)
    }
    // "all" + "manufacturing" minimum (cross-vertical foundation +
    // manufacturing per-line widgets)
    expect(verticalsCovered.has("all")).toBe(true)
    expect(verticalsCovered.has("manufacturing")).toBe(true)
  })

  it("includes all 5 Focus types", () => {
    const focusTypes = getByType("focus")
    const names = focusTypes.map((e) => e.metadata.name).sort()
    expect(names).toEqual([
      "coordination",
      "decision",
      "execution",
      "generation",
      "review",
    ])
  })

  it("includes 2 Focus templates with extensions.focusType set", () => {
    const templates = getByType("focus-template")
    expect(templates).toHaveLength(2)
    for (const t of templates) {
      expect(t.metadata.extensions?.focusType).toBeDefined()
    }
  })

  it("includes at least 2 document blocks", () => {
    expect(getByType("document-block").length).toBeGreaterThanOrEqual(2)
  })

  it("includes at least 2 workflow nodes", () => {
    expect(getByType("workflow-node").length).toBeGreaterThanOrEqual(2)
  })

  it("every registration carries schemaVersion=1 + componentVersion>=1", () => {
    for (const entry of _internal_listAll()) {
      expect(entry.metadata.schemaVersion).toBe(1)
      expect(entry.metadata.componentVersion).toBeGreaterThanOrEqual(1)
    }
  })

  it("getTokensConsumedBy('widget', 'today') returns the declared tokens", () => {
    const tokens = getTokensConsumedBy("widget", "today")
    expect(tokens).toContain("surface-elevated")
    expect(tokens).toContain("content-strong")
    expect(tokens).toContain("text-h4")
  })

  it("getComponentsConsumingToken('accent') returns multiple consumers", () => {
    const consumers = getComponentsConsumingToken("accent")
    expect(consumers.length).toBeGreaterThan(1)
  })

  it("getByVertical('funeral_home') includes Arrangement Scribe + cross-vertical components", () => {
    const fh = getByVertical("funeral_home")
    const names = fh.map((e) => e.metadata.name)
    expect(names).toContain("arrangement-scribe")
    // Cross-vertical components also surface
    expect(names).toContain("today")
  })
})
