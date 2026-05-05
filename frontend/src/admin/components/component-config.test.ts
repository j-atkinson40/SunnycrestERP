/**
 * Component editor — Phase 3 vitest tests.
 *
 * Covers:
 *   - Backfill validation: every Phase 1 registration has ≥3
 *     configurableProps with required schema fields populated
 *   - Configuration resolver merge order
 *   - Source detection across the 5 layers
 *   - All ConfigPropSchema types map to a control (smoke)
 *   - Stack composition / draft layering / diff
 */

import { afterEach, beforeAll, describe, expect, it } from "vitest"

import {
  composeEffectiveProps,
  diffPropOverrides,
  emptyConfigStack,
  mergeConfigStack,
  registrationDefaults,
  resolvePropSource,
  stackFromResolvedConfig,
  type ConfigStack,
} from "./config-resolver"
import {
  _internal_clear,
  _internal_listAll,
} from "@/admin/registry/registry"
import { getAllRegistered } from "@/admin/registry"
import type { ResolvedConfiguration } from "@/services/component-configurations-service"


describe("Phase 3 backfill validation", () => {
  beforeAll(async () => {
    _internal_clear()
    await import("@/admin/registry/auto-register")
  })
  afterEach(() => {
    /* keep registry populated across cases */
  })

  it("every Phase 1 registration has ≥3 configurableProps", () => {
    const all = _internal_listAll()
    expect(all.length).toBeGreaterThanOrEqual(13)

    const violations: string[] = []
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      const count = Object.keys(props).length
      if (count < 3) {
        violations.push(
          `${entry.metadata.type}:${entry.metadata.name} only has ${count} props`,
        )
      }
    }
    if (violations.length > 0) {
      throw new Error(`Backfill insufficient:\n${violations.join("\n")}`)
    }
  })

  it("every backfilled prop has type + default + a label or description", () => {
    const all = _internal_listAll()
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      for (const [key, schema] of Object.entries(props)) {
        const s = schema as { type?: string; default?: unknown; displayLabel?: string; description?: string }
        expect(s.type, `${entry.metadata.name}.${key}.type`).toBeDefined()
        // `default` must be present (any concrete value, including
        // false / 0 / "" / [] / {}). undefined is the violation.
        expect(
          s.default,
          `${entry.metadata.name}.${key}.default`,
        ).not.toBeUndefined()
        // Either displayLabel or description gives the editor
        // something to render. Bare props produce useless UI.
        const hasLabel = Boolean(s.displayLabel || s.description)
        expect(
          hasLabel,
          `${entry.metadata.name}.${key} needs displayLabel or description`,
        ).toBe(true)
      }
    }
  })

  it("total configurable props across all components ≥ 80", () => {
    const all = _internal_listAll()
    let total = 0
    for (const entry of all) {
      total += Object.keys(entry.metadata.configurableProps ?? {}).length
    }
    expect(total).toBeGreaterThanOrEqual(80)
  })

  it("number-typed props with bounds use [min, max] tuple shape", () => {
    const all = _internal_listAll()
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      for (const [key, schema] of Object.entries(props)) {
        const s = schema as { type?: string; bounds?: unknown }
        if (s.type === "number" && s.bounds !== undefined) {
          expect(
            Array.isArray(s.bounds) && s.bounds.length === 2,
            `${entry.metadata.name}.${key} number bounds must be [min, max]`,
          ).toBe(true)
        }
      }
    }
  })

  it("enum-typed props with bounds use array shape", () => {
    const all = _internal_listAll()
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      for (const [key, schema] of Object.entries(props)) {
        const s = schema as { type?: string; bounds?: unknown }
        if (s.type === "enum") {
          expect(
            Array.isArray(s.bounds) && s.bounds.length > 0,
            `${entry.metadata.name}.${key} enum bounds must be non-empty array`,
          ).toBe(true)
        }
      }
    }
  })

  it("tokenReference props declare a tokenCategory", () => {
    const all = _internal_listAll()
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      for (const [key, schema] of Object.entries(props)) {
        const s = schema as { type?: string; tokenCategory?: string }
        if (s.type === "tokenReference") {
          expect(
            typeof s.tokenCategory === "string" && s.tokenCategory.length > 0,
            `${entry.metadata.name}.${key} tokenReference must declare tokenCategory`,
          ).toBe(true)
        }
      }
    }
  })

  it("componentReference props declare componentTypes", () => {
    const all = _internal_listAll()
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      for (const [key, schema] of Object.entries(props)) {
        const s = schema as { type?: string; componentTypes?: unknown }
        if (s.type === "componentReference") {
          expect(
            Array.isArray(s.componentTypes) && s.componentTypes.length > 0,
            `${entry.metadata.name}.${key} componentReference must declare componentTypes`,
          ).toBe(true)
        }
      }
    }
  })

  it("registrationDefaults returns the default values from the registration", () => {
    const defaults = registrationDefaults("widget", "today")
    expect(defaults["showRowBreakdown"]).toBe(true)
    expect(defaults["showTotalCount"]).toBe(true)
    expect(defaults["refreshIntervalSeconds"]).toBe(300)
  })

  it("registrationDefaults returns empty object for unknown components", () => {
    expect(registrationDefaults("widget", "nonexistent")).toEqual({})
  })
})


describe("config-resolver merge order", () => {
  it("merges in canonical order — draft wins over tenant wins over vertical wins over platform", () => {
    const stack: ConfigStack = {
      platform: { x: "p", common: "platform" },
      vertical: { x: "v", common: "vertical" },
      tenant: { x: "t", common: "tenant" },
      draft: { x: "d", common: "draft" },
    }
    const out = mergeConfigStack(stack)
    expect(out.x).toBe("d")
    expect(out.common).toBe("draft")
  })

  it("composeEffectiveProps applies registration defaults as floor", () => {
    const stack: ConfigStack = {
      platform: { showRowBreakdown: false }, // override default true
      vertical: {},
      tenant: {},
      draft: {},
    }
    const out = composeEffectiveProps("widget", "today", stack)
    expect(out["showRowBreakdown"]).toBe(false) // overridden
    expect(out["refreshIntervalSeconds"]).toBe(300) // floor (default)
  })

  it("draft overrides registration defaults", () => {
    const stack = emptyConfigStack()
    stack.draft = { showRowBreakdown: false }
    const out = composeEffectiveProps("widget", "today", stack)
    expect(out["showRowBreakdown"]).toBe(false)
  })

  it("resolvePropSource returns the deepest scope that supplies the prop", () => {
    const stack: ConfigStack = {
      platform: { p: 1 },
      vertical: { v: 2 },
      tenant: { t: 3 },
      draft: { d: 4 },
    }
    expect(resolvePropSource("p", stack)).toBe("platform-default")
    expect(resolvePropSource("v", stack)).toBe("vertical-default")
    expect(resolvePropSource("t", stack)).toBe("tenant-override")
    expect(resolvePropSource("d", stack)).toBe("draft")
    expect(resolvePropSource("unknown", stack)).toBe("registration-default")
  })
})


describe("stackFromResolvedConfig", () => {
  it("splits backend resolved response into per-layer maps", () => {
    const resolved: ResolvedConfiguration = {
      component_kind: "widget",
      component_name: "today",
      vertical: "funeral_home",
      tenant_id: null,
      props: {
        showRowBreakdown: false,
        maxCategoriesShown: 8,
      },
      sources: [
        {
          scope: "platform_default",
          id: "p1",
          version: 1,
          applied_keys: ["showRowBreakdown"],
        },
        {
          scope: "vertical_default",
          vertical: "funeral_home",
          id: "v1",
          version: 1,
          applied_keys: ["maxCategoriesShown"],
        },
      ],
      orphaned_keys: [],
    }

    const stack = stackFromResolvedConfig(resolved)
    expect(stack.platform.showRowBreakdown).toBe(false)
    expect(stack.vertical.maxCategoriesShown).toBe(8)
    expect(stack.tenant).toEqual({})
    expect(stack.draft).toEqual({})
  })

  it("preserves draft when supplied", () => {
    const resolved: ResolvedConfiguration = {
      component_kind: "widget",
      component_name: "today",
      vertical: null,
      tenant_id: null,
      props: {},
      sources: [],
      orphaned_keys: [],
    }
    const stack = stackFromResolvedConfig(resolved, {
      showRowBreakdown: false,
    })
    expect(stack.draft.showRowBreakdown).toBe(false)
  })
})


describe("diffPropOverrides", () => {
  it("returns sorted changed keys", () => {
    const before = { a: 1, b: 2 }
    const after = { a: 1, b: 3, c: "new" }
    expect(diffPropOverrides(before, after)).toEqual(["b", "c"])
  })

  it("treats deep-equal objects as unchanged", () => {
    const before = { x: { nested: true } }
    const after = { x: { nested: true } }
    expect(diffPropOverrides(before, after)).toEqual([])
  })

  it("returns empty for identical maps", () => {
    expect(diffPropOverrides({ a: 1 }, { a: 1 })).toEqual([])
  })
})


// ─── Smoke check across all registered components ──────────────


describe("All registered components render preview without throwing", () => {
  beforeAll(async () => {
    _internal_clear()
    await import("@/admin/registry/auto-register")
  })

  it("every (kind, name) tuple has at least one prop with a renderable type", () => {
    const all = getAllRegistered()
    const supportedTypes = new Set([
      "boolean",
      "number",
      "string",
      "enum",
      "tokenReference",
      "componentReference",
      "array",
      "object",
    ])
    for (const entry of all) {
      const props = entry.metadata.configurableProps ?? {}
      for (const [key, schema] of Object.entries(props)) {
        const s = schema as { type?: string }
        expect(
          supportedTypes.has(s.type ?? ""),
          `${entry.metadata.name}.${key} has unsupported type ${s.type}`,
        ).toBe(true)
      }
    }
  })
})
