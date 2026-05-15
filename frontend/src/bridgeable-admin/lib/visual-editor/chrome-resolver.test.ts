/**
 * chrome-resolver unit tests (sub-arc C-2.2a).
 *
 * Pure-function coverage of the shared chrome composition pipeline.
 */
import { describe, expect, it } from "vitest"

import {
  chromeViewFromDraft,
  cornerToPx,
  blurToPx,
  elevationToBoxShadow,
  expandPreset,
  mergeChromeWithOverrides,
  PRESETS,
  resolveChromeStyle,
} from "./chrome-resolver"

describe("chrome-resolver — slider scrubs", () => {
  it("elevationToBoxShadow buckets correctly", () => {
    expect(elevationToBoxShadow(null)).toBe("none")
    expect(elevationToBoxShadow(0)).toBe("none")
    expect(elevationToBoxShadow(25)).toBe("none")
    expect(elevationToBoxShadow(40)).toContain("rgba")
    expect(elevationToBoxShadow(60)).toContain("rgba")
    expect(elevationToBoxShadow(90)).toContain("rgba")
  })

  it("cornerToPx + blurToPx bucket into 0 / 8 / 14 / 24", () => {
    for (const fn of [cornerToPx, blurToPx]) {
      expect(fn(null)).toBe(0)
      expect(fn(0)).toBe(0)
      expect(fn(25)).toBe(0)
      expect(fn(40)).toBe(8)
      expect(fn(60)).toBe(14)
      expect(fn(90)).toBe(24)
    }
  })
})

describe("chrome-resolver — expandPreset", () => {
  it("custom preset passes through untouched", () => {
    const v = chromeViewFromDraft({ preset: "custom", elevation: 50 })
    expect(expandPreset(v)).toEqual(v)
  })

  it("null preset passes through untouched", () => {
    const v = chromeViewFromDraft({})
    expect(expandPreset(v)).toEqual(v)
  })

  it("known preset fills missing fields from PRESETS defaults", () => {
    const v = chromeViewFromDraft({ preset: "card" })
    const expanded = expandPreset(v)
    expect(expanded.background_token).toBe(PRESETS.card.background_token)
    expect(expanded.elevation).toBe(PRESETS.card.elevation)
    expect(expanded.corner_radius).toBe(PRESETS.card.corner_radius)
  })

  it("explicit fields win over preset defaults", () => {
    const v = chromeViewFromDraft({ preset: "card", elevation: 99 })
    expect(expandPreset(v).elevation).toBe(99)
  })

  it("floating preset uses border-accent (not the retired border-brass)", () => {
    expect(PRESETS.floating.border_token).toBe("border-accent")
  })
})

describe("chrome-resolver — mergeChromeWithOverrides", () => {
  it("overrides win when present", () => {
    const core = { preset: "card", elevation: 37 }
    const overrides = { elevation: 88 }
    const merged = mergeChromeWithOverrides(core, overrides)
    expect(merged.elevation).toBe(88)
    expect(merged.preset).toBe("card")
  })

  it("null overrides preserve core values", () => {
    const core = { preset: "card", elevation: 37 }
    const overrides = { elevation: null }
    const merged = mergeChromeWithOverrides(core, overrides)
    expect(merged.elevation).toBe(37)
  })

  it("handles null/undefined inputs safely", () => {
    const merged = mergeChromeWithOverrides(null, undefined)
    expect(merged.preset).toBeNull()
    expect(merged.elevation).toBeNull()
  })
})

describe("chrome-resolver — resolveChromeStyle", () => {
  it("emits a CSSProperties object with all expected keys", () => {
    const view = chromeViewFromDraft({
      preset: "card",
      elevation: 60,
      corner_radius: 60,
      backdrop_blur: 0,
      background_token: "surface-elevated",
    })
    const tokens = { "surface-elevated": "#fff" }
    const style = resolveChromeStyle(view, tokens)
    expect(style.background).toBe("#fff")
    expect(style.borderRadius).toBe(14)
    expect(style.boxShadow).toContain("rgba")
    expect(style.transition).toContain("ease-out")
    // backdrop filter absent when blur <= 25
    expect(style.backdropFilter).toBeUndefined()
  })

  it("applies blur when backdrop_blur > 25", () => {
    const view = chromeViewFromDraft({
      preset: "frosted",
      backdrop_blur: 60,
    })
    const style = resolveChromeStyle(view, {})
    expect(style.backdropFilter).toBe("blur(14px)")
    expect(style.WebkitBackdropFilter).toBe("blur(14px)")
  })

  it("falls back to var(--surface-elevated) when token missing", () => {
    const view = chromeViewFromDraft({ background_token: "nope" })
    const style = resolveChromeStyle(view, {})
    expect(style.background).toBe("var(--surface-elevated)")
  })
})
