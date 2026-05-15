/**
 * substrate-resolver unit tests (sub-arc C-2.2a).
 */
import { describe, expect, it } from "vitest"

import {
  expandSubstratePreset,
  resolveSubstrateStyle,
  SUBSTRATE_PRESETS,
  substrateViewFromBlob,
} from "./substrate-resolver"

describe("substrate-resolver — view extraction", () => {
  it("handles empty/null blob safely", () => {
    expect(substrateViewFromBlob(null)).toEqual({
      preset: null,
      intensity: null,
      base_token: null,
      accent_token_1: null,
      accent_token_2: null,
    })
    expect(substrateViewFromBlob(undefined).preset).toBeNull()
    expect(substrateViewFromBlob({})).toEqual(substrateViewFromBlob(null))
  })

  it("extracts known fields from a blob", () => {
    const v = substrateViewFromBlob({
      preset: "morning-warm",
      intensity: 50,
      base_token: "surface-base",
    })
    expect(v.preset).toBe("morning-warm")
    expect(v.intensity).toBe(50)
    expect(v.base_token).toBe("surface-base")
  })
})

describe("substrate-resolver — expandSubstratePreset", () => {
  it("custom and null presets pass through", () => {
    const v1 = substrateViewFromBlob({ preset: "custom", intensity: 22 })
    expect(expandSubstratePreset(v1)).toEqual(v1)
    const v2 = substrateViewFromBlob({})
    expect(expandSubstratePreset(v2)).toEqual(v2)
  })

  it("known preset fills missing fields", () => {
    const v = substrateViewFromBlob({ preset: "morning-warm" })
    const expanded = expandSubstratePreset(v)
    expect(expanded.base_token).toBe(
      SUBSTRATE_PRESETS["morning-warm"].base_token,
    )
    expect(expanded.intensity).toBe(SUBSTRATE_PRESETS["morning-warm"].intensity)
  })

  it("explicit fields win over preset defaults", () => {
    const v = substrateViewFromBlob({
      preset: "morning-warm",
      intensity: 99,
    })
    expect(expandSubstratePreset(v).intensity).toBe(99)
  })
})

describe("substrate-resolver — resolveSubstrateStyle", () => {
  it("returns plain base when intensity is 0 / accents missing", () => {
    const v = substrateViewFromBlob({
      preset: "neutral",
      intensity: 0,
      base_token: "surface-base",
    })
    const style = resolveSubstrateStyle(v, { "surface-base": "#abc" })
    expect(style.background).toBe("#abc")
    expect(style.backgroundColor).toBeUndefined()
  })

  it("emits a gradient when intensity > 0 with accents", () => {
    const v = expandSubstratePreset(
      substrateViewFromBlob({ preset: "morning-warm" }),
    )
    const tokens = {
      "surface-base": "#fff",
      "accent-subtle": "#f1e6d2",
      "status-warning-muted": "#ffe9c8",
    }
    const style = resolveSubstrateStyle(v, tokens)
    expect(String(style.background)).toContain("linear-gradient")
    expect(style.backgroundColor).toBe("#fff")
    expect(style.backgroundBlendMode).toBe("soft-light")
  })

  it("clamps intensity to 0..100", () => {
    const v = substrateViewFromBlob({ intensity: 999 })
    const style = resolveSubstrateStyle(v, {})
    // unparsable accent + clamped intensity should still produce a
    // valid CSSProperties without exploding.
    expect(style.background).toBeDefined()
  })
})
