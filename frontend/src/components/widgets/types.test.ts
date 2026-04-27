/**
 * Widget Library Phase W-1 — type + helper tests.
 *
 * Covers the unified-contract types declared in `types.ts`:
 *   • Vertical / WidgetSurface / VariantId / VariantDensity enum-narrowing
 *   • findVariant() — variant lookup by id
 *   • defaultVariant() — resolves to declared default
 *   • isWidgetAvailableForVertical() — Section 12.4 vertical-axis predicate
 *
 * Section 12.3 contract invariants enforced by these tests:
 *   • Every widget definition has at least one variant
 *   • default_variant_id references a declared variant
 *   • Cross-vertical widgets ("*") visible in all verticals
 *   • Vertical-specific widgets visible only in declared verticals
 */

import { describe, it, expect } from "vitest"

import {
  defaultVariant,
  findVariant,
  isWidgetAvailableForVertical,
  type Vertical,
  type WidgetDefinition,
  type WidgetVariant,
} from "./types"


function buildVariant(variant_id: WidgetVariant["variant_id"]): WidgetVariant {
  return {
    variant_id,
    density: variant_id === "glance"
      ? "minimal"
      : variant_id === "brief"
      ? "focused"
      : variant_id === "detail"
      ? "rich"
      : "deep",
    grid_size: { cols: 1, rows: 1 },
    canvas_size: { width: 200, height: 200 },
    supported_surfaces: ["dashboard_grid"],
  }
}


function buildDefinition(overrides: Partial<WidgetDefinition> = {}): WidgetDefinition {
  return {
    widget_id: "test_widget",
    title: "Test",
    description: "Test widget",
    icon: "Box",
    category: "ops",
    default_size: "1x1",
    supported_sizes: ["1x1"],
    default_enabled: true,
    default_position: 1,
    required_extension: null,
    required_vertical: ["*"],
    variants: [buildVariant("brief")],
    default_variant_id: "brief",
    supported_surfaces: ["dashboard_grid"],
    default_surfaces: ["dashboard_grid"],
    intelligence_keywords: [],
    is_available: true,
    unavailable_reason: null,
    ...overrides,
  }
}


describe("findVariant", () => {
  it("resolves a variant by its variant_id", () => {
    const def = buildDefinition({
      variants: [buildVariant("glance"), buildVariant("brief"), buildVariant("detail")],
    })
    const v = findVariant(def, "brief")
    expect(v).not.toBeNull()
    expect(v?.variant_id).toBe("brief")
  })

  it("returns null for an unknown variant_id", () => {
    const def = buildDefinition()
    const v = findVariant(def, "deep") // not declared on this definition
    expect(v).toBeNull()
  })
})


describe("defaultVariant", () => {
  it("returns the variant matching default_variant_id", () => {
    const def = buildDefinition({
      variants: [buildVariant("glance"), buildVariant("brief"), buildVariant("detail")],
      default_variant_id: "detail",
    })
    expect(defaultVariant(def).variant_id).toBe("detail")
  })

  it("falls back to first variant when default_variant_id mismatches", () => {
    // Defensive — definition shape malformed, but helper returns
    // a variant rather than throwing. Backend test
    // test_default_variant_id_references_a_declared_variant catches
    // malformed definitions in CI.
    const def = buildDefinition({
      variants: [buildVariant("glance"), buildVariant("brief")],
      default_variant_id: "deep" as WidgetVariant["variant_id"],
    })
    expect(defaultVariant(def).variant_id).toBe("glance")
  })
})


describe("isWidgetAvailableForVertical", () => {
  const verticals: Vertical[] = ["manufacturing", "funeral_home", "cemetery", "crematory"]

  it("cross-vertical (\"*\") widget is available in all verticals", () => {
    const def = buildDefinition({ required_vertical: ["*"] })
    for (const v of verticals) {
      expect(isWidgetAvailableForVertical(def, v)).toBe(true)
    }
  })

  it("cross-vertical widget is also available when tenantVertical is null", () => {
    const def = buildDefinition({ required_vertical: ["*"] })
    expect(isWidgetAvailableForVertical(def, null)).toBe(true)
  })

  it("single-vertical widget is available only in declared vertical", () => {
    const def = buildDefinition({ required_vertical: ["funeral_home"] })
    expect(isWidgetAvailableForVertical(def, "funeral_home")).toBe(true)
    expect(isWidgetAvailableForVertical(def, "manufacturing")).toBe(false)
    expect(isWidgetAvailableForVertical(def, "cemetery")).toBe(false)
    expect(isWidgetAvailableForVertical(def, "crematory")).toBe(false)
  })

  it("multi-vertical widget is available in any declared vertical", () => {
    const def = buildDefinition({ required_vertical: ["funeral_home", "cemetery"] })
    expect(isWidgetAvailableForVertical(def, "funeral_home")).toBe(true)
    expect(isWidgetAvailableForVertical(def, "cemetery")).toBe(true)
    expect(isWidgetAvailableForVertical(def, "manufacturing")).toBe(false)
    expect(isWidgetAvailableForVertical(def, "crematory")).toBe(false)
  })

  it("single-vertical widget is NOT available when tenantVertical is null", () => {
    const def = buildDefinition({ required_vertical: ["funeral_home"] })
    expect(isWidgetAvailableForVertical(def, null)).toBe(false)
  })
})


describe("Phase W-1 contract invariants — frontend type defaults", () => {
  it("default builder produces a valid definition", () => {
    const def = buildDefinition()
    // Section 12.3 invariants:
    // • Every WidgetDefinition has at least one variant
    expect(def.variants.length).toBeGreaterThanOrEqual(1)
    // • default_variant_id references a variant that exists in variants[]
    expect(findVariant(def, def.default_variant_id)).not.toBeNull()
    // • default_surfaces ⊆ supported_surfaces
    const supported = new Set(def.supported_surfaces)
    for (const s of def.default_surfaces) {
      expect(supported.has(s)).toBe(true)
    }
    // • required_vertical either "*" or non-empty array of valid Verticals
    expect(def.required_vertical.length).toBeGreaterThanOrEqual(1)
  })

  it("AncillaryPoolPin-shape definition (Section 12.10 reference)", () => {
    // Sanity-check the expected reference-implementation shape.
    const def = buildDefinition({
      widget_id: "scheduling.ancillary-pool",
      variants: [
        buildVariant("glance"),
        buildVariant("brief"),
        buildVariant("detail"),
      ],
      default_variant_id: "detail",
      required_vertical: ["funeral_home"],
      supported_surfaces: ["focus_canvas", "focus_stack", "spaces_pin", "dashboard_grid"],
      default_surfaces: ["focus_canvas"],
    })
    expect(def.variants.map((v) => v.variant_id)).toEqual(["glance", "brief", "detail"])
    expect(def.default_variant_id).toBe("detail")
    expect(isWidgetAvailableForVertical(def, "funeral_home")).toBe(true)
    expect(isWidgetAvailableForVertical(def, "manufacturing")).toBe(false)
  })
})
