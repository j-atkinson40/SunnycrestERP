/**
 * Theme resolver — Phase 2 of the Admin Visual Editor.
 *
 * Frontend-side inheritance walker + DOM applier. Used by the
 * editor's live preview to render with overrides without
 * round-tripping the backend on every keystroke.
 *
 * The backend resolver (`platform_themes.theme_service.resolve_theme`)
 * is the canonical source for "what does the merged token map look
 * like for tenant X?" — the frontend resolver is a local mirror
 * for the editor's draft state, where the operator hasn't saved
 * yet and we don't want backend round-trips slowing down the
 * preview.
 *
 * The two resolvers must agree on merge semantics. If they drift,
 * the test suite catches it via integration assertions.
 */

import { TOKEN_CATALOG } from "./token-catalog"
import type { ThemeMode, ResolvedTheme } from "@/bridgeable-admin/services/themes-service"


export type TokenOverrideMap = Record<string, string>


/** A resolution stack — ordered platform → vertical → tenant.
 * Each layer supplies an override map. Merging in order produces
 * the final effective theme. */
export interface ThemeStack {
  platform: TokenOverrideMap
  vertical: TokenOverrideMap
  tenant: TokenOverrideMap
  /** Operator's unsaved draft on top of all server-resolved layers. */
  draft: TokenOverrideMap
}


export function emptyStack(): ThemeStack {
  return { platform: {}, vertical: {}, tenant: {}, draft: {} }
}


/** Merge in canonical order: platform → vertical → tenant → draft.
 * Last-wins per key. Returns a fresh object — never mutates inputs. */
export function mergeStack(stack: ThemeStack): TokenOverrideMap {
  return {
    ...stack.platform,
    ...stack.vertical,
    ...stack.tenant,
    ...stack.draft,
  }
}


/** Walk the catalog and produce a complete `{token-name: value}`
 * map using the platform built-in defaults for the given mode.
 * This is the floor underneath all override layers — even if the
 * backend has no rows yet, the editor preview still renders
 * correctly because it has the catalog defaults to fall back on. */
export function catalogDefaultsForMode(mode: ThemeMode): TokenOverrideMap {
  const out: TokenOverrideMap = {}
  for (const t of TOKEN_CATALOG) {
    const v = t.defaults[mode]
    if (v && v !== "(computed)" && v !== "(composition)" && v !== "(none)") {
      out[t.name] = v
    }
  }
  return out
}


/** Compose the catalog defaults with the override stack to produce
 * the final effective token map. Catalog defaults are the "floor"
 * (always present); the stack provides overrides on top.
 *
 * Returns a complete map: every catalog token has a value, with
 * stack overrides applied where present. */
export function composeEffective(
  mode: ThemeMode,
  stack: ThemeStack,
): TokenOverrideMap {
  return {
    ...catalogDefaultsForMode(mode),
    ...mergeStack(stack),
  }
}


/** Inheritance source for a single token — the editor uses this
 * to render the "overridden at X" indicator below each token
 * control. */
export type TokenSource =
  | "catalog-default"
  | "platform-default"
  | "vertical-default"
  | "tenant-override"
  | "draft"


export function resolveTokenSource(
  tokenName: string,
  stack: ThemeStack,
): TokenSource {
  if (tokenName in stack.draft) return "draft"
  if (tokenName in stack.tenant) return "tenant-override"
  if (tokenName in stack.vertical) return "vertical-default"
  if (tokenName in stack.platform) return "platform-default"
  return "catalog-default"
}


/** Apply an effective token map to a target DOM element via CSS
 * custom properties. Defaults to `document.documentElement` (the
 * `<html>` element). The editor's live preview supplies its own
 * isolated wrapper element so the editor UI itself stays
 * unaffected by the operator's draft. */
export function applyThemeToElement(
  effective: TokenOverrideMap,
  target: HTMLElement | null = null,
): void {
  const el = target ?? (typeof document !== "undefined" ? document.documentElement : null)
  if (!el) return
  for (const [name, value] of Object.entries(effective)) {
    el.style.setProperty(`--${name}`, String(value))
  }
}


/** Diff two override maps — returns the keys whose values differ.
 * Used by the editor to highlight changed tokens since last save. */
export function diffOverrides(
  before: TokenOverrideMap,
  after: TokenOverrideMap,
): string[] {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)])
  const changed: string[] = []
  for (const k of keys) {
    if (before[k] !== after[k]) changed.push(k)
  }
  return changed.sort()
}


/** Build a ThemeStack from a backend `ResolvedTheme` response.
 * Splits the merged `tokens` map back into per-layer override
 * maps using the `sources` array's `applied_keys`. */
export function stackFromResolved(
  resolved: ResolvedTheme,
  draft: TokenOverrideMap = {},
): ThemeStack {
  const out = emptyStack()
  out.draft = { ...draft }

  // Walk sources in order; each source's applied_keys are pulled
  // from `resolved.tokens` (the merged map) into the appropriate
  // layer. Sources are emitted in inheritance order by the backend.
  for (const src of resolved.sources) {
    const layer: TokenOverrideMap = {}
    for (const k of src.applied_keys) {
      if (k in resolved.tokens) layer[k] = String(resolved.tokens[k])
    }
    if (src.scope === "platform_default") out.platform = layer
    else if (src.scope === "vertical_default") out.vertical = layer
    else if (src.scope === "tenant_override") out.tenant = layer
  }

  return out
}


// ─── Color-space utilities (oklch parse/format) ─────────────────


export interface OklchValue {
  l: number // 0..1
  c: number // 0..~0.4 in practice
  h: number // 0..360
  alpha: number // 0..1
}


/** Parse an `oklch(L C H)` or `oklch(L C H / a)` CSS string into
 * its components. Accepts both literal alpha (0..1) and percentage
 * notation. Returns null if not a recognizable oklch literal —
 * caller falls back to displaying the raw string. */
export function parseOklch(value: string): OklchValue | null {
  if (!value || typeof value !== "string") return null
  const trimmed = value.trim()
  const match = trimmed.match(
    /^oklch\(\s*([0-9.]+%?)\s+([0-9.]+%?)\s+([0-9.]+)\s*(?:\/\s*([0-9.]+%?))?\s*\)$/i,
  )
  if (!match) return null

  const parseNum = (s: string): number => {
    if (s.endsWith("%")) return Number(s.slice(0, -1)) / 100
    return Number(s)
  }

  const l = parseNum(match[1])
  const c = parseNum(match[2])
  const h = Number(match[3])
  const alpha = match[4] !== undefined ? parseNum(match[4]) : 1

  if (
    !Number.isFinite(l) ||
    !Number.isFinite(c) ||
    !Number.isFinite(h) ||
    !Number.isFinite(alpha)
  ) {
    return null
  }
  return { l, c, h, alpha }
}


/** Format an OklchValue back to canonical `oklch(L C H / a)` notation.
 * Preserves the alpha clause only when alpha < 1. */
export function formatOklch(v: OklchValue): string {
  const l = +v.l.toFixed(4)
  const c = +v.c.toFixed(4)
  const h = +v.h.toFixed(2)
  if (v.alpha >= 1 - 1e-6) return `oklch(${l} ${c} ${h})`
  const a = +v.alpha.toFixed(3)
  return `oklch(${l} ${c} ${h} / ${a})`
}


/** Convert oklch → sRGB for swatch rendering. Per Ottosson 2020.
 * Returns `[r, g, b]` channel values in 0..255 (clamped to gamut).
 * Out-of-gamut values are simple-clipped — adequate for the
 * swatch preview the editor uses; production-grade gamut mapping
 * would chroma-reduce instead, but that's a Phase 3+ concern. */
export function oklchToSrgb(v: OklchValue): [number, number, number] {
  const L = v.l
  const a = v.c * Math.cos((v.h * Math.PI) / 180)
  const b = v.c * Math.sin((v.h * Math.PI) / 180)

  // Oklab → linear LMS (Ottosson 2020 inverse matrix step 1)
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b
  const s_ = L - 0.0894841775 * a - 1.291485548 * b

  // Cube to get LMS
  const lc = l_ ** 3
  const mc = m_ ** 3
  const sc = s_ ** 3

  // LMS → linear sRGB
  let r = +4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc
  let g = -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc
  let bl = -0.0041960863 * lc - 0.7034186147 * mc + 1.707614701 * sc

  // Linear → gamma-encoded sRGB
  const enc = (u: number): number => {
    if (u <= 0) return 0
    if (u >= 1) return 1
    return u <= 0.0031308 ? 12.92 * u : 1.055 * Math.pow(u, 1 / 2.4) - 0.055
  }
  r = enc(r)
  g = enc(g)
  bl = enc(bl)

  return [
    Math.max(0, Math.min(255, Math.round(r * 255))),
    Math.max(0, Math.min(255, Math.round(g * 255))),
    Math.max(0, Math.min(255, Math.round(bl * 255))),
  ]
}


/** Render an oklch value as an `rgb(...)` or `rgba(...)` string
 * suitable for direct CSS use (swatch backgrounds). */
export function oklchToCssRgb(v: OklchValue): string {
  const [r, g, b] = oklchToSrgb(v)
  if (v.alpha >= 1 - 1e-6) return `rgb(${r}, ${g}, ${b})`
  return `rgba(${r}, ${g}, ${b}, ${+v.alpha.toFixed(3)})`
}
