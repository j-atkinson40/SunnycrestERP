/**
 * Widget palette taxonomy tests — sub-arc F-3.
 */
import { describe, expect, it } from "vitest"

import {
  WIDGET_CATEGORIES,
  WIDGET_CATEGORY_LABELS,
  WIDGET_SLUG_TO_CATEGORY,
  widgetCategoryFor,
  widgetCategoryLabel,
} from "./widget-palette"

describe("widget-palette taxonomy", () => {
  it("declares three categories", () => {
    expect(WIDGET_CATEGORIES).toEqual(["ancillaries", "map", "information"])
  })

  it("maps known widget slugs to expected categories", () => {
    expect(widgetCategoryFor("day-strip-widget")).toBe("information")
    expect(widgetCategoryFor("today-pin-widget")).toBe("information")
    expect(widgetCategoryFor("map-placeholder-widget")).toBe("map")
  })

  it("falls back to ancillaries for unknown slugs", () => {
    expect(widgetCategoryFor("unknown-widget")).toBe("ancillaries")
    expect(widgetCategoryFor("foo")).toBe("ancillaries")
  })

  it("labels every category", () => {
    for (const cat of WIDGET_CATEGORIES) {
      expect(WIDGET_CATEGORY_LABELS[cat]).toBeTruthy()
      expect(widgetCategoryLabel(cat)).toBe(WIDGET_CATEGORY_LABELS[cat])
    }
  })

  it("WIDGET_SLUG_TO_CATEGORY entries reference valid categories", () => {
    for (const [, cat] of Object.entries(WIDGET_SLUG_TO_CATEGORY)) {
      expect(WIDGET_CATEGORIES).toContain(cat)
    }
  })
})
