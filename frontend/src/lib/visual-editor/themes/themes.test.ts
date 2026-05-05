/**
 * Theme editor — Phase 2 vitest tests.
 *
 * Covers:
 *   - Token catalog completeness (every CSS variable in
 *     tokens.css has a catalog entry)
 *   - Theme resolver inheritance (platform → vertical → tenant
 *     → draft) and mode independence
 *   - OKLCH parse/format round-trip
 *   - oklch → sRGB conversion
 *   - applyThemeToElement writes correct CSS variables
 *   - diffOverrides + stackFromResolved correctness
 */

import { readFileSync } from "node:fs"
import { resolve } from "node:path"

import { describe, expect, it } from "vitest"

import {
  TOKEN_CATALOG,
  getTokenByName,
  getTokensByCategory,
  isColorToken,
} from "./token-catalog"
import {
  applyThemeToElement,
  catalogDefaultsForMode,
  composeEffective,
  diffOverrides,
  emptyStack,
  formatOklch,
  mergeStack,
  oklchToSrgb,
  parseOklch,
  resolveTokenSource,
  stackFromResolved,
  type ThemeStack,
} from "./theme-resolver"
import type { ResolvedTheme } from "@/bridgeable-admin/services/themes-service"


// ─── Catalog completeness ──────────────────────────────────────


describe("token-catalog completeness", () => {
  it("has at least 60 tokens", () => {
    expect(TOKEN_CATALOG.length).toBeGreaterThanOrEqual(60)
  })

  it("includes every CSS variable defined in tokens.css", () => {
    // Parse `tokens.css` at test time and assert every `--name`
    // appears in the catalog. This catches drift when someone adds
    // a token to tokens.css without registering it here.
    const tokensCssPath = resolve(
      __dirname,
      "../../../styles/tokens.css",
    )
    const css = readFileSync(tokensCssPath, "utf-8")

    const matches = css.matchAll(/(?:^|\s)(--[a-z][a-z0-9-]*)\s*:/g)
    const cssTokenNames = new Set<string>()
    for (const m of matches) {
      cssTokenNames.add(m[1].slice(2)) // strip leading --
    }

    const catalogNames = new Set(TOKEN_CATALOG.map((t) => t.name))
    const missing = [...cssTokenNames].filter((n) => !catalogNames.has(n))

    if (missing.length > 0) {
      throw new Error(
        `Catalog missing entries for tokens.css variables: ${missing.join(", ")}`,
      )
    }
  })

  it("every entry has both light and dark default values", () => {
    for (const t of TOKEN_CATALOG) {
      expect(t.defaults).toBeDefined()
      expect(typeof t.defaults.light).toBe("string")
      expect(typeof t.defaults.dark).toBe("string")
    }
  })

  it("getTokenByName returns the entry", () => {
    expect(getTokenByName("accent")?.displayName).toContain("Accent")
    expect(getTokenByName("nonexistent")).toBeUndefined()
  })

  it("getTokensByCategory groups correctly", () => {
    const surfaces = getTokensByCategory("surface")
    expect(surfaces.length).toBeGreaterThanOrEqual(4)
    expect(surfaces.every((t) => t.category === "surface")).toBe(true)
  })

  it("isColorToken classifies oklch + rgba as colors", () => {
    expect(isColorToken({ name: "x", category: "accent", displayName: "x", valueType: "oklch", defaults: { light: "", dark: "" } })).toBe(true)
    expect(isColorToken({ name: "x", category: "accent", displayName: "x", valueType: "rgba", defaults: { light: "", dark: "" } })).toBe(true)
    expect(isColorToken({ name: "x", category: "accent", displayName: "x", valueType: "rem", defaults: { light: "", dark: "" } })).toBe(false)
  })
})


// ─── OKLCH parse/format ────────────────────────────────────────


describe("parseOklch", () => {
  it("parses bare oklch(L C H)", () => {
    expect(parseOklch("oklch(0.46 0.10 39)")).toEqual({
      l: 0.46,
      c: 0.1,
      h: 39,
      alpha: 1,
    })
  })

  it("parses oklch with alpha", () => {
    expect(parseOklch("oklch(0.46 0.10 39 / 0.5)")).toEqual({
      l: 0.46,
      c: 0.1,
      h: 39,
      alpha: 0.5,
    })
  })

  it("parses percentage alpha", () => {
    expect(parseOklch("oklch(0.5 0.1 100 / 60%)")).toEqual({
      l: 0.5,
      c: 0.1,
      h: 100,
      alpha: 0.6,
    })
  })

  it("returns null for non-oklch strings", () => {
    expect(parseOklch("rgba(0, 0, 0, 0)")).toBeNull()
    expect(parseOklch("blue")).toBeNull()
    expect(parseOklch("")).toBeNull()
  })

  it("round-trips with formatOklch", () => {
    const original = "oklch(0.46 0.1 39)"
    const parsed = parseOklch(original)
    expect(parsed).not.toBeNull()
    if (parsed) expect(formatOklch(parsed)).toBe(original)
  })

  it("formatOklch emits alpha clause only when alpha < 1", () => {
    expect(formatOklch({ l: 0.5, c: 0.1, h: 30, alpha: 1 })).toBe(
      "oklch(0.5 0.1 30)",
    )
    expect(formatOklch({ l: 0.5, c: 0.1, h: 30, alpha: 0.5 })).toBe(
      "oklch(0.5 0.1 30 / 0.5)",
    )
  })
})


// ─── oklch → sRGB ──────────────────────────────────────────────


describe("oklchToSrgb", () => {
  it("converts a terracotta oklch into a structurally-correct warm sRGB", () => {
    // oklch(0.46 0.10 39) is the canonical platform accent —
    // a deepened terracotta. Ottosson conversion produces an
    // exact value in the brick-red range; CLAUDE.md's shorthand
    // "#9C5640" is approximate, so we assert structural
    // properties (warm-family, R > G > B) instead of an exact
    // RGB match.
    const [r, g, b] = oklchToSrgb({ l: 0.46, c: 0.1, h: 39, alpha: 1 })
    expect(r).toBeGreaterThan(g)
    expect(g).toBeGreaterThan(b)
    expect(r).toBeGreaterThan(80) // warm — clearly red-shifted
    expect(b).toBeLessThan(80) // not blue
  })

  it("clamps out-of-gamut values to 0..255", () => {
    const [r, g, b] = oklchToSrgb({ l: 1.0, c: 0.4, h: 0, alpha: 1 })
    expect(r).toBeGreaterThanOrEqual(0)
    expect(r).toBeLessThanOrEqual(255)
    expect(g).toBeGreaterThanOrEqual(0)
    expect(g).toBeLessThanOrEqual(255)
    expect(b).toBeGreaterThanOrEqual(0)
    expect(b).toBeLessThanOrEqual(255)
  })

  it("white at L=1, C=0 maps to (255, 255, 255)", () => {
    const [r, g, b] = oklchToSrgb({ l: 1, c: 0, h: 0, alpha: 1 })
    expect(r).toBe(255)
    expect(g).toBe(255)
    expect(b).toBe(255)
  })

  it("black at L=0 maps to (0, 0, 0)", () => {
    const [r, g, b] = oklchToSrgb({ l: 0, c: 0, h: 0, alpha: 1 })
    expect(r).toBe(0)
    expect(g).toBe(0)
    expect(b).toBe(0)
  })
})


// ─── Theme resolver ────────────────────────────────────────────


describe("catalogDefaultsForMode", () => {
  it("emits a complete map for light mode", () => {
    const m = catalogDefaultsForMode("light")
    expect(m["accent"]).toBe("oklch(0.46 0.10 39)")
    expect(m["surface-base"]).toBe("oklch(0.94 0.030 82)")
  })

  it("emits a different map for dark mode", () => {
    const m = catalogDefaultsForMode("dark")
    // Dark surface differs from light
    expect(m["surface-base"]).toBe("oklch(0.16 0.010 59)")
    // Accent is same in both modes per Aesthetic Arc Session 2
    expect(m["accent"]).toBe("oklch(0.46 0.10 39)")
  })

  it("light and dark are independent — editing one doesn't affect the other", () => {
    const light = catalogDefaultsForMode("light")
    const dark = catalogDefaultsForMode("dark")
    light["surface-base"] = "modified"
    expect(dark["surface-base"]).toBe("oklch(0.16 0.010 59)")
  })
})


describe("mergeStack", () => {
  it("merges in canonical order — draft wins over tenant wins over vertical wins over platform", () => {
    const stack: ThemeStack = {
      platform: { x: "platform" },
      vertical: { x: "vertical", y: "vertical-only" },
      tenant: { x: "tenant" },
      draft: { x: "draft" },
    }
    const out = mergeStack(stack)
    expect(out.x).toBe("draft")
    expect(out.y).toBe("vertical-only")
  })

  it("empty stack merges to empty map", () => {
    expect(mergeStack(emptyStack())).toEqual({})
  })
})


describe("composeEffective", () => {
  it("falls back to catalog defaults when stack is empty", () => {
    const out = composeEffective("light", emptyStack())
    expect(out["accent"]).toBe("oklch(0.46 0.10 39)")
  })

  it("stack overrides override catalog defaults", () => {
    const stack = emptyStack()
    stack.platform = { accent: "oklch(0.55 0.10 39)" }
    const out = composeEffective("light", stack)
    expect(out["accent"]).toBe("oklch(0.55 0.10 39)")
  })

  it("draft overrides everything", () => {
    const stack: ThemeStack = {
      platform: { accent: "platform" },
      vertical: { accent: "vertical" },
      tenant: { accent: "tenant" },
      draft: { accent: "draft" },
    }
    const out = composeEffective("light", stack)
    expect(out["accent"]).toBe("draft")
  })
})


describe("resolveTokenSource", () => {
  it("returns each layer correctly", () => {
    const stack: ThemeStack = {
      platform: { p: "1" },
      vertical: { v: "1" },
      tenant: { t: "1" },
      draft: { d: "1" },
    }
    expect(resolveTokenSource("p", stack)).toBe("platform-default")
    expect(resolveTokenSource("v", stack)).toBe("vertical-default")
    expect(resolveTokenSource("t", stack)).toBe("tenant-override")
    expect(resolveTokenSource("d", stack)).toBe("draft")
    expect(resolveTokenSource("nothing", stack)).toBe("catalog-default")
  })
})


describe("stackFromResolved", () => {
  it("splits backend resolved response into layers", () => {
    const resolved: ResolvedTheme = {
      mode: "light",
      vertical: "funeral_home",
      tenant_id: "t1",
      tokens: {
        accent: "oklch(0.55 0.10 39)",
        "surface-base": "oklch(0.94 0.030 82)",
      },
      sources: [
        {
          scope: "platform_default",
          id: "p1",
          version: 1,
          applied_keys: ["surface-base"],
        },
        {
          scope: "vertical_default",
          id: "v1",
          version: 2,
          applied_keys: ["accent"],
        },
      ],
    }
    const stack = stackFromResolved(resolved)
    expect(stack.platform["surface-base"]).toBe("oklch(0.94 0.030 82)")
    expect(stack.vertical["accent"]).toBe("oklch(0.55 0.10 39)")
    expect(stack.tenant).toEqual({})
    expect(stack.draft).toEqual({})
  })

  it("preserves draft when supplied", () => {
    const resolved: ResolvedTheme = {
      mode: "light",
      vertical: null,
      tenant_id: null,
      tokens: {},
      sources: [],
    }
    const stack = stackFromResolved(resolved, { accent: "drafted" })
    expect(stack.draft).toEqual({ accent: "drafted" })
  })
})


describe("diffOverrides", () => {
  it("returns sorted changed keys", () => {
    const before = { a: "1", b: "2" }
    const after = { a: "1", b: "3", c: "new" }
    expect(diffOverrides(before, after)).toEqual(["b", "c"])
  })

  it("returns empty for identical maps", () => {
    expect(diffOverrides({ a: "1" }, { a: "1" })).toEqual([])
  })
})


// ─── applyThemeToElement (DOM) ─────────────────────────────────


describe("applyThemeToElement", () => {
  it("writes CSS custom properties to the target", () => {
    const el = document.createElement("div")
    applyThemeToElement({ accent: "oklch(0.5 0.1 39)", radius: "8px" }, el)
    expect(el.style.getPropertyValue("--accent")).toBe("oklch(0.5 0.1 39)")
    expect(el.style.getPropertyValue("--radius")).toBe("8px")
  })

  it("is a no-op when target is null and document is unavailable", () => {
    // jsdom always has document, so we just verify it doesn't throw.
    expect(() => applyThemeToElement({})).not.toThrow()
  })
})


// ─── Inheritance edge cases ────────────────────────────────────


describe("inheritance edge cases", () => {
  it("tenant override on a vertical with no vertical default still falls back to platform", () => {
    // Simulates the prompt's edge-case requirement.
    const resolved: ResolvedTheme = {
      mode: "light",
      vertical: "cemetery",
      tenant_id: "t1",
      tokens: {
        "surface-base": "oklch(0.94 0.030 82)", // from platform
        accent: "oklch(0.70 0.05 250)", // tenant override (blue, not warm)
      },
      sources: [
        {
          scope: "platform_default",
          id: "p1",
          version: 1,
          applied_keys: ["surface-base"],
        },
        // NB: no vertical_default source for cemetery
        {
          scope: "tenant_override",
          tenant_id: "t1",
          id: "t1-row",
          version: 1,
          applied_keys: ["accent"],
        },
      ],
    }
    const stack = stackFromResolved(resolved)
    expect(stack.platform["surface-base"]).toBeDefined()
    expect(stack.vertical).toEqual({})
    expect(stack.tenant["accent"]).toBe("oklch(0.70 0.05 250)")
    const out = mergeStack(stack)
    expect(out["surface-base"]).toBe("oklch(0.94 0.030 82)")
    expect(out["accent"]).toBe("oklch(0.70 0.05 250)")
  })
})
