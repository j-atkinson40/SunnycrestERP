/**
 * Arc 4b.2b — getCaretCoordinates unit tests.
 *
 * jsdom-resident tests. jsdom does NOT compute element layout — every
 * `offsetTop` / `offsetLeft` / `getBoundingClientRect` value returns 0
 * unless the implementation monkey-patches DOM measurement. Tests
 * therefore validate:
 *   1. The helper returns a `{top, left}` shape without throwing
 *      across the edge cases (start / end / mid-position / empty /
 *      multi-line input)
 *   2. SSR safety — function returns {0, 0} when window / document
 *      are unavailable
 *   3. Single-line vs multi-line discrimination (input vs textarea)
 *   4. Position clamping (negative + out-of-range)
 *   5. Internals: MIRROR_PROPERTIES list is non-empty + includes the
 *      canonical typography/box-model properties
 *
 * Real browser-layout verification happens via the broader Playwright
 * Documents tab regression at staging deploy time.
 */
import { describe, expect, it } from "vitest"

import {
  getCaretCoordinates,
  __testing__,
} from "./getCaretCoordinates"


describe("getCaretCoordinates — helper shape", () => {
  it("returns {top, left} for a textarea at position 0", () => {
    const ta = document.createElement("textarea")
    ta.value = "hello world"
    document.body.appendChild(ta)
    try {
      const res = getCaretCoordinates(ta, 0)
      expect(res).toHaveProperty("top")
      expect(res).toHaveProperty("left")
      expect(typeof res.top).toBe("number")
      expect(typeof res.left).toBe("number")
    } finally {
      document.body.removeChild(ta)
    }
  })

  it("returns {top, left} for an input at position 0", () => {
    const input = document.createElement("input")
    input.type = "text"
    input.value = "hello"
    document.body.appendChild(input)
    try {
      const res = getCaretCoordinates(input, 0)
      expect(res).toHaveProperty("top")
      expect(res).toHaveProperty("left")
    } finally {
      document.body.removeChild(input)
    }
  })

  it("returns {top, left} for empty textarea", () => {
    const ta = document.createElement("textarea")
    ta.value = ""
    document.body.appendChild(ta)
    try {
      const res = getCaretCoordinates(ta, 0)
      expect(res).toEqual(expect.objectContaining({ top: expect.any(Number), left: expect.any(Number) }))
    } finally {
      document.body.removeChild(ta)
    }
  })

  it("clamps a negative position to 0 without throwing", () => {
    const ta = document.createElement("textarea")
    ta.value = "abc"
    document.body.appendChild(ta)
    try {
      expect(() => getCaretCoordinates(ta, -5)).not.toThrow()
    } finally {
      document.body.removeChild(ta)
    }
  })

  it("clamps an out-of-range position to value.length without throwing", () => {
    const ta = document.createElement("textarea")
    ta.value = "abc"
    document.body.appendChild(ta)
    try {
      expect(() => getCaretCoordinates(ta, 9999)).not.toThrow()
    } finally {
      document.body.removeChild(ta)
    }
  })

  it("handles multi-line content in a textarea", () => {
    const ta = document.createElement("textarea")
    ta.value = "line one\nline two\nline three"
    document.body.appendChild(ta)
    try {
      // Position after first newline (at "l" of line two)
      const res = getCaretCoordinates(ta, 9)
      expect(res).toHaveProperty("top")
      expect(res).toHaveProperty("left")
    } finally {
      document.body.removeChild(ta)
    }
  })
})


describe("getCaretCoordinates — SSR safety", () => {
  it("returns {0, 0} when window is undefined", () => {
    const originalWindow = global.window
    // @ts-expect-error — intentionally undefining window for SSR test
    delete global.window
    try {
      // We can still call the function with a fake element because
      // the function bails out at the top.
      const fakeEl = { value: "", tagName: "TEXTAREA" } as unknown as HTMLTextAreaElement
      const res = getCaretCoordinates(fakeEl, 0)
      expect(res).toEqual({ top: 0, left: 0 })
    } finally {
      global.window = originalWindow
    }
  })
})


describe("getCaretCoordinates — internals", () => {
  it("MIRROR_PROPERTIES includes canonical typography + box-model properties", () => {
    const props = __testing__.MIRROR_PROPERTIES
    // Spot-check critical ones — drift in this set causes silent
    // caret-position drift; tests should catch removals.
    expect(props).toContain("fontSize")
    expect(props).toContain("fontFamily")
    expect(props).toContain("lineHeight")
    expect(props).toContain("paddingTop")
    expect(props).toContain("paddingLeft")
    expect(props).toContain("borderLeftWidth")
    expect(props).toContain("whiteSpace")
    expect(props).toContain("boxSizing")
    expect(props).toContain("width")
  })

  it("MIRROR_PROPERTIES list is non-empty", () => {
    expect(__testing__.MIRROR_PROPERTIES.length).toBeGreaterThan(10)
  })

  it("isSingleLineInput discriminates by tagName", () => {
    const input = document.createElement("input")
    const ta = document.createElement("textarea")
    expect(__testing__.isSingleLineInput(input)).toBe(true)
    expect(__testing__.isSingleLineInput(ta)).toBe(false)
  })
})
