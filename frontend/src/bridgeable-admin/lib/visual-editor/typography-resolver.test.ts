/**
 * typography-resolver unit tests (sub-arc C-2.2a).
 */
import { describe, expect, it } from "vitest"

import {
  expandTypographyPreset,
  resolveTypographyBodyStyle,
  resolveTypographyHeadingStyle,
  TYPOGRAPHY_PRESETS,
  typographyViewFromBlob,
} from "./typography-resolver"

describe("typography-resolver — view extraction", () => {
  it("handles empty/null blob safely", () => {
    const v = typographyViewFromBlob(null)
    expect(v.preset).toBeNull()
    expect(v.heading_weight).toBeNull()
  })

  it("extracts known fields", () => {
    const v = typographyViewFromBlob({
      preset: "headline",
      heading_weight: 700,
      heading_color_token: "content-strong",
    })
    expect(v.preset).toBe("headline")
    expect(v.heading_weight).toBe(700)
  })
})

describe("typography-resolver — expandTypographyPreset", () => {
  it("custom + null presets pass through", () => {
    const v1 = typographyViewFromBlob({ preset: "custom" })
    expect(expandTypographyPreset(v1)).toEqual(v1)
    const v2 = typographyViewFromBlob({})
    expect(expandTypographyPreset(v2)).toEqual(v2)
  })

  it("known preset fills missing fields", () => {
    const v = typographyViewFromBlob({ preset: "headline" })
    const expanded = expandTypographyPreset(v)
    expect(expanded.heading_weight).toBe(
      TYPOGRAPHY_PRESETS.headline.heading_weight,
    )
    expect(expanded.body_color_token).toBe(
      TYPOGRAPHY_PRESETS.headline.body_color_token,
    )
  })

  it("explicit fields win over preset defaults", () => {
    const v = typographyViewFromBlob({
      preset: "headline",
      heading_weight: 300,
    })
    expect(expandTypographyPreset(v).heading_weight).toBe(300)
  })
})

describe("typography-resolver — style resolvers", () => {
  it("emits heading + body CSSProperties with weight + color", () => {
    const v = expandTypographyPreset(
      typographyViewFromBlob({ preset: "card-text" }),
    )
    const tokens = {
      "content-strong": "#111",
      "content-base": "#333",
    }
    const heading = resolveTypographyHeadingStyle(v, tokens)
    expect(heading.fontWeight).toBe(500)
    expect(heading.color).toBe("#111")
    expect(heading.fontFamily).toContain("plex-serif")
    const body = resolveTypographyBodyStyle(v, tokens)
    expect(body.fontWeight).toBe(400)
    expect(body.color).toBe("#333")
    expect(body.fontFamily).toContain("plex-sans")
  })

  it("falls back to CSS vars when token lookup misses", () => {
    const v = typographyViewFromBlob({ heading_color_token: "missing" })
    const style = resolveTypographyHeadingStyle(v, {})
    expect(style.color).toBe("var(--content-strong)")
  })
})
