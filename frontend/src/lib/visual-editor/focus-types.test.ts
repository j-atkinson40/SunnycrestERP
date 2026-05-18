import { describe, expect, it } from "vitest"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"

import {
  CORE_SLUG_TO_FOCUS_TYPE,
  FOCUS_TYPES,
  focusTypeForCore,
  focusTypeLabel,
} from "./focus-types"

function makeCore(slug: string): CoreRecord {
  return {
    id: "id-" + slug,
    core_slug: slug,
    display_name: slug,
    description: null,
    registered_component_kind: "focus-template",
    registered_component_name: "X",
    default_starting_column: 0,
    default_column_span: 12,
    default_row_index: 0,
    min_column_span: 1,
    max_column_span: 12,
    canvas_config: {},
    chrome: {},
    version: 1,
    is_active: true,
    created_at: "",
    updated_at: "",
  }
}

describe("focus-types", () => {
  it("exposes 5 canonical focus types", () => {
    expect(FOCUS_TYPES.map((ft) => ft.id)).toEqual([
      "decision",
      "coordination",
      "production",
      "triage",
      "scribe",
    ])
  })

  it("resolves a known slug via CORE_SLUG_TO_FOCUS_TYPE", () => {
    // Sub-arc F-1.1: scheduling-kanban reclassified production → decision
    // per James lock (kanban shape is canonical decision-family).
    expect(CORE_SLUG_TO_FOCUS_TYPE["scheduling-kanban-core"]).toBe("decision")
    expect(focusTypeForCore(makeCore("scheduling-kanban-core"))).toBe(
      "decision",
    )
    expect(CORE_SLUG_TO_FOCUS_TYPE["scheduling-kanban"]).toBe("decision")
    expect(focusTypeForCore(makeCore("scheduling-kanban"))).toBe("decision")
  })

  it("falls back to 'production' for unknown slugs", () => {
    expect(focusTypeForCore(makeCore("unknown-slug-xyz"))).toBe("production")
  })

  it("returns the canonical label for a focus type", () => {
    expect(focusTypeLabel("decision")).toBe("Decision")
    expect(focusTypeLabel("scribe")).toBe("Scribe")
  })

  it("returns 'Other' for an unknown focus type id", () => {
    // @ts-expect-error — testing runtime fallback for invalid input
    expect(focusTypeLabel("nonsense")).toBe("Other")
  })
})
