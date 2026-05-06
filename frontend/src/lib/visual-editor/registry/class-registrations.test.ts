/**
 * Class registrations + class-layer resolver tests (May 2026).
 *
 * Verifies:
 *   - Each of the 9 v1 classes has a well-formed registration
 *     (displayName, description, configurableProps with at least
 *     one entry; each prop has type + default).
 *   - getEffectiveComponentClasses returns [type] when no explicit
 *     componentClasses is declared on a registration.
 *   - The frontend ConfigStack resolver correctly maps a backend
 *     class_default source into the classLayer slot, and
 *     resolvePropSource returns "class-default" for class-sourced
 *     props that aren't overridden by deeper scopes.
 */
import { describe, expect, it } from "vitest"

import {
  CLASS_REGISTRATIONS,
  getAllClassNames,
  getClassRegistration,
  getClassProp,
  getEffectiveComponentClasses,
  type RegistryEntry,
} from "./index"
import {
  emptyConfigStack,
  mergeConfigStack,
  resolvePropSource,
  stackFromResolvedConfig,
} from "@/lib/visual-editor/components/config-resolver"


describe("CLASS_REGISTRATIONS", () => {
  it("ships all 9 v1 classes", () => {
    const names = getAllClassNames()
    expect(names).toEqual(
      expect.arrayContaining([
        "widget",
        "entity-card",
        "focus",
        "focus-template",
        "document-block",
        "workflow-node",
        "button",
        "form-input",
        "surface-card",
      ]),
    )
    expect(names.length).toBe(9)
  })

  it("each class declaration is well-formed", () => {
    for (const className of getAllClassNames()) {
      const reg = CLASS_REGISTRATIONS[className]
      expect(reg).toBeDefined()
      expect(reg.className).toBe(className)
      expect(reg.displayName.length).toBeGreaterThan(0)
      expect(reg.description.length).toBeGreaterThan(0)
      const propEntries = Object.entries(reg.configurableProps)
      expect(propEntries.length).toBeGreaterThanOrEqual(3)
      for (const [propName, prop] of propEntries) {
        expect(propName.length).toBeGreaterThan(0)
        expect(prop.type).toBeDefined()
        expect(prop).toHaveProperty("default")
      }
    }
  })

  it("widget class declares core shared props", () => {
    expect(getClassProp("widget", "shadowToken")).toBeDefined()
    expect(getClassProp("widget", "density")).toBeDefined()
    expect(getClassProp("widget", "hoverElevation")).toBeDefined()
  })

  it("entity-card class declares accentTreatment", () => {
    const prop = getClassProp("entity-card", "accentTreatment")
    expect(prop?.type).toBe("enum")
    expect(prop?.bounds).toContain("left-bar")
  })

  it("getClassRegistration returns undefined for unknown class", () => {
    expect(getClassRegistration("not-a-real-class")).toBeUndefined()
  })
})


describe("getEffectiveComponentClasses", () => {
  function mockEntry(
    type: string,
    name: string,
    componentClasses?: string[],
  ): RegistryEntry {
    // Cast to any-shape to avoid coupling the test to private
    // RegistryEntry.component field semantics — getEffective only
    // reads metadata.type + metadata.componentClasses.
    return {
      component: (() => null) as unknown,
      metadata: {
        type: type as RegistryEntry["metadata"]["type"],
        name,
        displayName: name,
        verticals: ["all"],
        userParadigms: [],
        consumedTokens: [],
        schemaVersion: 1,
        componentVersion: 1,
        ...(componentClasses ? { componentClasses } : {}),
      },
      registeredAt: new Date().toISOString(),
    } as unknown as RegistryEntry
  }

  it("returns [type] when no explicit declaration", () => {
    const e = mockEntry("widget", "today")
    expect(getEffectiveComponentClasses(e)).toEqual(["widget"])
  })

  it("returns the explicit declaration when present", () => {
    const e = mockEntry("widget", "today", ["widget", "data-display"])
    expect(getEffectiveComponentClasses(e)).toEqual(["widget", "data-display"])
  })

  it("treats empty arrays as undeclared (falls back to [type])", () => {
    const e = mockEntry("widget", "today", [])
    expect(getEffectiveComponentClasses(e)).toEqual(["widget"])
  })
})


describe("config-resolver class-layer integration", () => {
  it("emptyConfigStack includes classLayer + classNames slots", () => {
    const s = emptyConfigStack()
    expect(s).toHaveProperty("classLayer")
    expect(s).toHaveProperty("classNames")
    expect(s.classLayer).toEqual({})
    expect(s.classNames).toEqual([])
  })

  it("stackFromResolvedConfig maps class_default sources into classLayer", () => {
    // ResolvedConfiguration shape from the backend with both a
    // class_default source AND a per-component platform_default.
    const resolved = {
      component_kind: "widget",
      component_name: "today",
      vertical: null,
      tenant_id: null,
      props: {
        density: "compact", // class-sourced
        showRowBreakdown: false, // platform-sourced
      },
      sources: [
        {
          scope: "class_default",
          component_class: "widget",
          id: "class-1",
          version: 1,
          applied_keys: ["density"],
        },
        {
          scope: "platform_default",
          id: "platform-1",
          version: 1,
          applied_keys: ["showRowBreakdown"],
        },
      ],
      orphaned_keys: [],
    } as Parameters<typeof stackFromResolvedConfig>[0]

    const stack = stackFromResolvedConfig(resolved)
    expect(stack.classLayer).toEqual({ density: "compact" })
    expect(stack.classNames).toEqual(["widget"])
    expect(stack.platform).toEqual({ showRowBreakdown: false })
  })

  it("resolvePropSource returns 'class-default' for class-only props", () => {
    const stack = emptyConfigStack()
    stack.classLayer = { density: "compact" }
    stack.classNames = ["widget"]
    expect(resolvePropSource("density", stack)).toBe("class-default")
  })

  it("platform overrides class at matching keys (per-component scope wins)", () => {
    const stack = emptyConfigStack()
    stack.classLayer = { density: "compact" }
    stack.platform = { density: "spacious" }
    expect(resolvePropSource("density", stack)).toBe("platform-default")
    const merged = mergeConfigStack(stack)
    expect(merged.density).toBe("spacious")
  })

  it("class layer merges before platform/vertical/tenant in mergeConfigStack", () => {
    const stack = emptyConfigStack()
    stack.classLayer = { a: 1, b: 2 }
    stack.platform = { b: 20 }
    stack.tenant = { a: 100 }
    const merged = mergeConfigStack(stack)
    // a: class=1 → tenant=100 → tenant wins
    expect(merged.a).toBe(100)
    // b: class=2 → platform=20 → platform wins
    expect(merged.b).toBe(20)
  })
})
