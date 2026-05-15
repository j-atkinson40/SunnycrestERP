/**
 * typography-resolver — Tier 2 typography composition pipeline
 * (sub-arc C-2.2a).
 *
 * Mirrors backend TYPOGRAPHY_PRESETS (sub-arc B-5). v1 vocabulary is
 * weight + color only — family / line-height / size are
 * platform-canonical DESIGN_LANGUAGE §4 concerns and are NOT part of
 * the per-template authoring surface.
 *
 * Tier 1 cores are typography-free by design (locked decision in
 * B-5) — typography first appears at Tier 2 templates. The "custom"
 * preset means "no preset; use the explicit fields only."
 *
 * Two outputs:
 *
 *   - resolveTypographyHeadingStyle(view, tokens) — CSSProperties
 *     for the heading text node in the preview.
 *   - resolveTypographyBodyStyle(view, tokens) — CSSProperties for
 *     the body text node in the preview.
 *
 * Pure module — no React, no DOM.
 */
import type { CSSProperties } from "react"

export type TypographyPreset =
  | "card-text"
  | "frosted-text"
  | "headline"
  | "custom"

export interface TypographyView {
  preset: TypographyPreset | null
  heading_weight: number | null
  heading_color_token: string | null
  body_weight: number | null
  body_color_token: string | null
}

/** Frontend mirror of backend TYPOGRAPHY_PRESETS (sub-arc B-5). */
export const TYPOGRAPHY_PRESETS: Record<
  TypographyPreset,
  Partial<TypographyView>
> = {
  "card-text": {
    heading_weight: 500,
    heading_color_token: "content-strong",
    body_weight: 400,
    body_color_token: "content-base",
  },
  "frosted-text": {
    heading_weight: 600,
    heading_color_token: "content-strong",
    body_weight: 500,
    body_color_token: "content-base",
  },
  headline: {
    heading_weight: 700,
    heading_color_token: "content-strong",
    body_weight: 500,
    body_color_token: "content-base",
  },
  custom: {},
}

export function typographyViewFromBlob(
  blob: Record<string, unknown> | null | undefined,
): TypographyView {
  const b = blob ?? {}
  return {
    preset: (b.preset as TypographyPreset | null | undefined) ?? null,
    heading_weight: (b.heading_weight as number | null | undefined) ?? null,
    heading_color_token:
      (b.heading_color_token as string | null | undefined) ?? null,
    body_weight: (b.body_weight as number | null | undefined) ?? null,
    body_color_token:
      (b.body_color_token as string | null | undefined) ?? null,
  }
}

export function expandTypographyPreset(view: TypographyView): TypographyView {
  const preset = view.preset
  if (!preset || preset === "custom") return view
  const defaults = TYPOGRAPHY_PRESETS[preset]
  const merged: TypographyView = { ...view }
  for (const key of Object.keys(defaults) as (keyof TypographyView)[]) {
    if (merged[key] === null || merged[key] === undefined) {
      ;(merged as unknown as Record<string, unknown>)[key] = defaults[
        key
      ] as unknown
    }
  }
  return merged
}

export function resolveTypographyHeadingStyle(
  view: TypographyView,
  tokens: Record<string, string>,
): CSSProperties {
  return {
    fontFamily: "var(--font-plex-serif)",
    fontWeight: view.heading_weight ?? 500,
    color:
      (view.heading_color_token && tokens[view.heading_color_token]) ||
      "var(--content-strong)",
  }
}

export function resolveTypographyBodyStyle(
  view: TypographyView,
  tokens: Record<string, string>,
): CSSProperties {
  return {
    fontFamily: "var(--font-plex-sans)",
    fontWeight: view.body_weight ?? 400,
    color:
      (view.body_color_token && tokens[view.body_color_token]) ||
      "var(--content-base)",
  }
}
