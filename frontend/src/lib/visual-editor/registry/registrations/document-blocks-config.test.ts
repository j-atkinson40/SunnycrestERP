/**
 * Arc 4b.1a — Documents block-kind config schemas test.
 *
 * Locks the canonical-kind enumeration + extended-vocabulary
 * placement (which complex shapes route through which Arc 4b.1a
 * dispatcher). Regression guards prevent silent vocabulary drift.
 */
import { describe, expect, it } from "vitest"

import {
  BLOCK_KIND_CONFIG_SCHEMAS,
  BODY_SECTION_BLOCK_SCHEMA,
  CONDITIONAL_WRAPPER_BLOCK_SCHEMA,
  HEADER_BLOCK_SCHEMA,
  LINE_ITEMS_BLOCK_SCHEMA,
  SIGNATURE_BLOCK_SCHEMA,
  TOTALS_BLOCK_SCHEMA,
  getBlockKindConfigSchema,
  getCanonicalFieldsForKind,
} from "./document-blocks-config"


describe("Arc 4b.1a — document-blocks-config", () => {
  it("registers exactly the 6 canonical block kinds", () => {
    expect(Object.keys(BLOCK_KIND_CONFIG_SCHEMAS).sort()).toEqual([
      "body_section",
      "conditional_wrapper",
      "header",
      "line_items",
      "signature",
      "totals",
    ])
  })

  it("header schema dispatches through canonical primitives only (no extended vocabulary)", () => {
    const types = Object.values(HEADER_BLOCK_SCHEMA).map((s) => s.type)
    // All 6 fields should be canonical primitives — header is a
    // "simple kind" per Arc 4b.1a's per-block dispatch split.
    types.forEach((t) => {
      expect(["boolean", "string", "enum"]).toContain(t)
    })
  })

  it("body_section schema dispatches through canonical primitives only", () => {
    const types = Object.values(BODY_SECTION_BLOCK_SCHEMA).map((s) => s.type)
    types.forEach((t) => {
      expect(["string"]).toContain(t)
    })
  })

  it("line_items.columns routes through tableOfColumns", () => {
    expect(LINE_ITEMS_BLOCK_SCHEMA.columns.type).toBe("tableOfColumns")
  })

  it("totals.rows routes through tableOfRows", () => {
    expect(TOTALS_BLOCK_SCHEMA.rows.type).toBe("tableOfRows")
  })

  it("signature.parties routes through listOfParties; signature.show_dates is canonical boolean", () => {
    expect(SIGNATURE_BLOCK_SCHEMA.parties.type).toBe("listOfParties")
    expect(SIGNATURE_BLOCK_SCHEMA.show_dates.type).toBe("boolean")
  })

  it("conditional_wrapper synthetic __condition__ routes through conditionalRule", () => {
    expect(CONDITIONAL_WRAPPER_BLOCK_SCHEMA.__condition__.type).toBe(
      "conditionalRule",
    )
  })

  it("getBlockKindConfigSchema returns null for unknown kind (forward-compat fallback)", () => {
    expect(getBlockKindConfigSchema("future_unknown_kind")).toBeNull()
  })

  it("getBlockKindConfigSchema returns schema for known kind", () => {
    const schema = getBlockKindConfigSchema("header")
    expect(schema).toBeTruthy()
    expect(schema).toHaveProperty("title")
    expect(schema).toHaveProperty("show_logo")
  })

  it("getCanonicalFieldsForKind returns field names per kind", () => {
    expect(getCanonicalFieldsForKind("header")).toEqual([
      "show_logo",
      "logo_position",
      "title",
      "subtitle",
      "accent_color",
      "show_date",
    ])
    expect(getCanonicalFieldsForKind("totals")).toEqual(["rows"])
    expect(getCanonicalFieldsForKind("signature")).toEqual([
      "parties",
      "show_dates",
    ])
  })

  it("getCanonicalFieldsForKind returns empty list for unknown kind", () => {
    expect(getCanonicalFieldsForKind("future_unknown_kind")).toEqual([])
  })

  it("every schema entry carries a displayLabel (UX completeness)", () => {
    for (const [kind, schema] of Object.entries(BLOCK_KIND_CONFIG_SCHEMAS)) {
      for (const [fieldKey, propSchema] of Object.entries(schema)) {
        expect(
          propSchema.displayLabel,
          `${kind}.${fieldKey} missing displayLabel`,
        ).toBeTruthy()
      }
    }
  })

  it("every Arc 4b.1a extended-vocabulary entry has typed default matching its shape", () => {
    expect(Array.isArray(LINE_ITEMS_BLOCK_SCHEMA.columns.default)).toBe(true)
    expect(Array.isArray(TOTALS_BLOCK_SCHEMA.rows.default)).toBe(true)
    expect(Array.isArray(SIGNATURE_BLOCK_SCHEMA.parties.default)).toBe(true)
    expect(typeof CONDITIONAL_WRAPPER_BLOCK_SCHEMA.__condition__.default).toBe(
      "object",
    )
  })

  it("conditional_wrapper.label is canonical string (NOT routed through extended vocabulary)", () => {
    expect(CONDITIONAL_WRAPPER_BLOCK_SCHEMA.label.type).toBe("string")
  })
})
