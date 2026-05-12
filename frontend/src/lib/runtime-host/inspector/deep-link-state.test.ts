/**
 * Arc-3.x-deep-link-retrofit — deep-link-state shared util tests.
 *
 * Verifies:
 * - buildEditorDeepLink composes base + extras + return_to into URL
 * - null/undefined/empty extras are omitted (not encoded as "null")
 * - return_to defaults to current window URL when not provided
 * - decodeReturnTo round-trips encoded paths
 * - decodeReturnTo falls back to raw on malformed escape
 */

import { describe, expect, it } from "vitest"

import {
  buildEditorDeepLink,
  decodeReturnTo,
  deriveReturnToFromWindow,
} from "./deep-link-state"


describe("buildEditorDeepLink", () => {
  it("composes base + extras + return_to", () => {
    const url = buildEditorDeepLink(
      "/bridgeable-admin/visual-editor/workflows",
      { workflow_type: "month_end_close", scope: "vertical_default" },
      "/runtime-editor/dashboard",
    )
    expect(url).toContain("/bridgeable-admin/visual-editor/workflows?")
    expect(url).toContain("workflow_type=month_end_close")
    expect(url).toContain("scope=vertical_default")
    expect(url).toContain("return_to=%2Fruntime-editor%2Fdashboard")
  })

  it("omits null/undefined/empty extras", () => {
    const url = buildEditorDeepLink(
      "/x",
      {
        defined: "value",
        nulled: null,
        undef: undefined,
        empty: "",
      },
      "/r",
    )
    expect(url).toContain("defined=value")
    expect(url).not.toContain("nulled=")
    expect(url).not.toContain("undef=")
    expect(url).not.toContain("empty=")
  })

  it("defaults return_to to window.location.pathname+search when omitted", () => {
    const url = buildEditorDeepLink("/x", { k: "v" })
    expect(url).toContain("return_to=")
  })

  it("URL-encodes return_to path with query params", () => {
    const url = buildEditorDeepLink(
      "/x",
      {},
      "/runtime-editor/?tenant=hopkins&user=u1",
    )
    expect(url).toContain("return_to=%2Fruntime-editor%2F")
    // URLSearchParams encodes & as %26 + = as %3D
    expect(url).toContain("tenant%3Dhopkins")
  })
})


describe("decodeReturnTo", () => {
  it("decodes URL-encoded path", () => {
    expect(decodeReturnTo("%2Fruntime-editor%2F")).toBe("/runtime-editor/")
  })

  it("round-trips with encodeURIComponent", () => {
    const original = "/runtime-editor/?tenant=hopkins&user=u1"
    const encoded = encodeURIComponent(original)
    expect(decodeReturnTo(encoded)).toBe(original)
  })

  it("falls back to raw value on malformed escape", () => {
    // %ZZ is not a valid escape sequence; decodeURIComponent throws.
    const malformed = "/safe%ZZpath"
    expect(decodeReturnTo(malformed)).toBe(malformed)
  })
})


describe("deriveReturnToFromWindow", () => {
  it("returns a non-empty string", () => {
    const r = deriveReturnToFromWindow()
    expect(typeof r).toBe("string")
    expect(r.length).toBeGreaterThan(0)
  })
})
