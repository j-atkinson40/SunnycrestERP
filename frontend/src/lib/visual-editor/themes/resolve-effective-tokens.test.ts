/**
 * resolveEffectiveTokens composition tests (sub-arc C-2.1).
 */
import { describe, expect, it } from "vitest"

import { BASE_TOKENS } from "./base-tokens"
import {
  resolveEffectiveTokens,
  normalizeTokenKey,
  baseOnly,
} from "./resolve-effective-tokens"

describe("resolveEffectiveTokens", () => {
  it("returns BASE_TOKENS for light mode when overrides empty", () => {
    const out = resolveEffectiveTokens("light", {})
    expect(out["surface-base"]).toBe(BASE_TOKENS.light["surface-base"])
    expect(out["accent"]).toBe(BASE_TOKENS.light["accent"])
  })

  it("returns BASE_TOKENS for dark mode when overrides empty", () => {
    const out = resolveEffectiveTokens("dark", {})
    expect(out["surface-base"]).toBe(BASE_TOKENS.dark["surface-base"])
  })

  it("merges overrides on top of BASE_TOKENS (light)", () => {
    const out = resolveEffectiveTokens("light", {
      "surface-base": "#ffffff",
      accent: "#000000",
    })
    expect(out["surface-base"]).toBe("#ffffff")
    expect(out["accent"]).toBe("#000000")
    // Untouched key still resolves from BASE_TOKENS.
    expect(out["surface-elevated"]).toBe(BASE_TOKENS.light["surface-elevated"])
  })

  it("strips leading -- from override keys", () => {
    const out = resolveEffectiveTokens("light", {
      "--surface-base": "#abcdef",
    })
    expect(out["surface-base"]).toBe("#abcdef")
    // The raw `--surface-base` key should NOT also be present.
    expect(out["--surface-base"]).toBeUndefined()
  })

  it("handles null overrides", () => {
    const out = resolveEffectiveTokens("light", null)
    expect(out["surface-base"]).toBe(BASE_TOKENS.light["surface-base"])
  })

  it("ignores null + undefined override values", () => {
    const out = resolveEffectiveTokens("light", {
      "surface-base": null as unknown as string,
      accent: undefined as unknown as string,
    })
    expect(out["surface-base"]).toBe(BASE_TOKENS.light["surface-base"])
    expect(out["accent"]).toBe(BASE_TOKENS.light["accent"])
  })

  it("normalizeTokenKey strips leading --", () => {
    expect(normalizeTokenKey("--surface-base")).toBe("surface-base")
    expect(normalizeTokenKey("surface-base")).toBe("surface-base")
  })

  it("baseOnly returns a fresh copy of BASE_TOKENS[mode]", () => {
    const out = baseOnly("light")
    expect(out["surface-base"]).toBe(BASE_TOKENS.light["surface-base"])
    out["surface-base"] = "mutated"
    // Mutation should not affect BASE_TOKENS.
    expect(BASE_TOKENS.light["surface-base"]).not.toBe("mutated")
  })

  it("unknown mode falls back to light", () => {
    const out = resolveEffectiveTokens("nonsense", {})
    expect(out["surface-base"]).toBe(BASE_TOKENS.light["surface-base"])
  })
})
