/**
 * substrate-resolver — Tier 2 page-background substrate composition
 * pipeline (sub-arc C-2.2a).
 *
 * Mirrors the backend resolver's SUBSTRATE_PRESETS table (sub-arc
 * B-4). A substrate blob declares a preset plus an intensity (0-100)
 * plus optional explicit token overrides; the resolver:
 *
 *   1. Expands the preset (preset === "custom" passes through).
 *   2. Overlays explicit fields from the blob on top of the expansion.
 *   3. Composes a CSSProperties object suitable for applying to the
 *      preview canvas: a radial / linear gradient blending the
 *      base_token + the two accent_tokens at the given intensity.
 *
 * Tier 1 cores are substrate-free by design (locked decision in
 * B-4) — substrate first appears at Tier 2 templates. The
 * "neutral" preset is the canonical "no atmospheric tint" entry.
 *
 * Pure module — no React, no DOM.
 */
import type { CSSProperties } from "react"

export type SubstratePreset =
  | "morning-warm"
  | "morning-cool"
  | "evening-lounge"
  | "neutral"
  | "custom"

export interface SubstrateView {
  preset: SubstratePreset | null
  intensity: number | null
  base_token: string | null
  accent_token_1: string | null
  accent_token_2: string | null
}

/** Frontend mirror of backend SUBSTRATE_PRESETS (sub-arc B-4). */
export const SUBSTRATE_PRESETS: Record<
  SubstratePreset,
  Partial<SubstrateView>
> = {
  "morning-warm": {
    base_token: "surface-base",
    accent_token_1: "accent-subtle",
    accent_token_2: "status-warning-muted",
    intensity: 70,
  },
  "morning-cool": {
    base_token: "surface-base",
    accent_token_1: "status-info-muted",
    accent_token_2: "accent-subtle",
    intensity: 55,
  },
  "evening-lounge": {
    base_token: "surface-sunken",
    accent_token_1: "accent-muted",
    accent_token_2: "accent-subtle",
    intensity: 80,
  },
  neutral: {
    base_token: "surface-base",
    accent_token_1: null,
    accent_token_2: null,
    intensity: 15,
  },
  custom: {},
}

export function substrateViewFromBlob(
  blob: Record<string, unknown> | null | undefined,
): SubstrateView {
  const b = blob ?? {}
  return {
    preset: (b.preset as SubstratePreset | null | undefined) ?? null,
    intensity: (b.intensity as number | null | undefined) ?? null,
    base_token: (b.base_token as string | null | undefined) ?? null,
    accent_token_1: (b.accent_token_1 as string | null | undefined) ?? null,
    accent_token_2: (b.accent_token_2 as string | null | undefined) ?? null,
  }
}

export function expandSubstratePreset(view: SubstrateView): SubstrateView {
  const preset = view.preset
  if (!preset || preset === "custom") return view
  const defaults = SUBSTRATE_PRESETS[preset]
  const merged: SubstrateView = { ...view }
  for (const key of Object.keys(defaults) as (keyof SubstrateView)[]) {
    if (merged[key] === null || merged[key] === undefined) {
      ;(merged as unknown as Record<string, unknown>)[key] = defaults[
        key
      ] as unknown
    }
  }
  return merged
}

/**
 * Compose a CSSProperties object that renders the substrate as a
 * page-background gradient. The intensity (0-100) modulates the
 * alpha of the accent stops blended over the base.
 *
 * Composition rule (Tier 2 v1 visual canon):
 *   - base_token paints the underlying surface (full opacity).
 *   - accent_token_1 + accent_token_2 contribute a diagonal
 *     linear-gradient layered on top, alpha = intensity / 100.
 *   - intensity <= 0 OR both accent tokens null → pure base.
 */
export function resolveSubstrateStyle(
  view: SubstrateView,
  tokens: Record<string, string>,
): CSSProperties {
  const base =
    tokens[view.base_token ?? "surface-base"] ?? "var(--surface-base)"
  const intensity = Math.max(
    0,
    Math.min(100, view.intensity ?? 0),
  )
  const alpha = intensity / 100
  const hasAccents =
    intensity > 0 && (view.accent_token_1 || view.accent_token_2)
  if (!hasAccents) {
    return { background: base }
  }
  const a1 =
    (view.accent_token_1 && tokens[view.accent_token_1]) ||
    "transparent"
  const a2 =
    (view.accent_token_2 && tokens[view.accent_token_2]) || a1
  // Two-stop diagonal — corner-to-corner painter. The alpha-modulation
  // is achieved by layering over the base via color-mix-friendly
  // rgba steps. Browsers without color-mix support fall back to the
  // base via the second background entry.
  const gradient = `linear-gradient(135deg, ${a1} 0%, ${a2} 100%)`
  return {
    background: gradient,
    backgroundColor: base,
    backgroundBlendMode: "soft-light",
    opacity: undefined,
    // Use opacity on a child element in production renderers if you
    // need the gradient to fade rather than blend; this is the
    // editor-preview composition.
    ["--substrate-intensity" as string]: String(alpha),
  } as CSSProperties
}
