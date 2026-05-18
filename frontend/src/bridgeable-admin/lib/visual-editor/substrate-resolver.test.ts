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
    // E-1: morning-warm defaults to intensity 100 (canonical mockup).
    expect(expanded.intensity).toBe(100)
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

  it("morning-warm at intensity 100 emits canonical four-layer composition", () => {
    // Sub-arc E-1: morning-warm is the canonical mockup substrate.
    // Three radial gradients (warm cream / pink / cool blue) over a
    // linear-gradient base. Radial alphas at full intensity are
    // 0.55 / 0.40 / 0.45 — values are mockup-canonical.
    const v = expandSubstratePreset(
      substrateViewFromBlob({ preset: "morning-warm", intensity: 100 }),
    )
    const tokens = {
      "surface-base": "#f0dfd0",
      "surface-elevated": "#f7ebe0",
    }
    const style = resolveSubstrateStyle(v, tokens)
    const bg = String(style.background)
    // Three radial layers in order
    expect(bg).toContain("radial-gradient(ellipse at 15% 10%")
    expect(bg).toContain("radial-gradient(ellipse at 85% 15%")
    expect(bg).toContain("radial-gradient(ellipse at 50% 90%")
    // Canonical hardcoded radial colors
    expect(bg).toContain("rgba(252, 220, 180,")
    expect(bg).toContain("rgba(220, 170, 200,")
    expect(bg).toContain("rgba(180, 200, 220,")
    // Canonical alphas at intensity 100
    expect(bg).toContain("0.550")
    expect(bg).toContain("0.400")
    expect(bg).toContain("0.450")
    // Linear base, top token then bottom token
    expect(bg).toContain("linear-gradient(180deg, #f7ebe0 0%, #f0dfd0 100%)")
    // No legacy soft-light blend / backgroundColor on morning-warm
    expect(style.backgroundBlendMode).toBeUndefined()
    expect(style.backgroundColor).toBeUndefined()
  })

  it("morning-warm at intensity 50 scales radial alphas proportionally", () => {
    const v = expandSubstratePreset(
      substrateViewFromBlob({ preset: "morning-warm", intensity: 50 }),
    )
    const tokens = {
      "surface-base": "#f0dfd0",
      "surface-elevated": "#f7ebe0",
    }
    const style = resolveSubstrateStyle(v, tokens)
    const bg = String(style.background)
    // Alphas scale to half: 0.275 / 0.200 / 0.225
    expect(bg).toContain("0.275")
    expect(bg).toContain("0.200")
    expect(bg).toContain("0.225")
  })

  it("morning-warm at intensity 0 zeroes the radial layers", () => {
    const v = expandSubstratePreset(
      substrateViewFromBlob({ preset: "morning-warm", intensity: 0 }),
    )
    const tokens = {
      "surface-base": "#f0dfd0",
      "surface-elevated": "#f7ebe0",
    }
    const style = resolveSubstrateStyle(v, tokens)
    const bg = String(style.background)
    // Radial alphas all zero (still 4-layer composition)
    expect(bg).toContain("rgba(252, 220, 180, 0.000)")
    expect(bg).toContain("rgba(220, 170, 200, 0.000)")
    expect(bg).toContain("rgba(180, 200, 220, 0.000)")
    // Linear base still rendered
    expect(bg).toContain("linear-gradient(180deg, #f7ebe0 0%, #f0dfd0 100%)")
  })

  it("morning-warm base_token / accent_token_1 bind to linear-gradient stops", () => {
    const v = expandSubstratePreset(
      substrateViewFromBlob({
        preset: "morning-warm",
        intensity: 100,
        base_token: "custom-bottom",
        accent_token_1: "custom-top",
      }),
    )
    const tokens = {
      "custom-bottom": "#aaaaaa",
      "custom-top": "#bbbbbb",
    }
    const style = resolveSubstrateStyle(v, tokens)
    const bg = String(style.background)
    // accent_token_1 → top stop; base_token → bottom stop
    expect(bg).toContain("linear-gradient(180deg, #bbbbbb 0%, #aaaaaa 100%)")
  })

  it("morning-cool preserves legacy two-stop composition (regression)", () => {
    const v = expandSubstratePreset(
      substrateViewFromBlob({ preset: "morning-cool" }),
    )
    const tokens = {
      "surface-base": "#fff",
      "status-info-muted": "#dcecff",
      "accent-brass-subtle": "#f1e6d2",
    }
    const style = resolveSubstrateStyle(v, tokens)
    expect(String(style.background)).toContain("linear-gradient(135deg")
    expect(style.backgroundColor).toBe("#fff")
    expect(style.backgroundBlendMode).toBe("soft-light")
  })

  it("evening-lounge + neutral preserve legacy composition (regression)", () => {
    const tokens = {
      "surface-base": "#fff",
      "surface-sunken": "#eee",
      "accent-brass-muted": "#ccc",
      "accent-brass-subtle": "#ddd",
    }
    const evening = resolveSubstrateStyle(
      expandSubstratePreset(
        substrateViewFromBlob({ preset: "evening-lounge" }),
      ),
      tokens,
    )
    expect(String(evening.background)).toContain("linear-gradient(135deg")
    expect(evening.backgroundBlendMode).toBe("soft-light")

    const neutral = resolveSubstrateStyle(
      expandSubstratePreset(substrateViewFromBlob({ preset: "neutral" })),
      tokens,
    )
    // neutral has null accents → plain base
    expect(neutral.background).toBe("#fff")
    expect(neutral.backgroundBlendMode).toBeUndefined()
  })

  it("clamps intensity to 0..100", () => {
    const v = substrateViewFromBlob({ intensity: 999 })
    const style = resolveSubstrateStyle(v, {})
    // unparsable accent + clamped intensity should still produce a
    // valid CSSProperties without exploding.
    expect(style.background).toBeDefined()
  })
})
