/**
 * chrome-resolver — shared chrome composition pipeline (C-2.2a).
 *
 * Extracts the chrome-preset expansion + slider-to-CSS mapping logic
 * that previously lived twice (Tier1CoresEditor's local helpers + the
 * C-1 ChromePrimitivesDemoPage). Both Tier 1 and Tier 2 editors
 * compose their preview surface against the same canonical pipeline,
 * so authoring quality is consistent across the internal demo and
 * production surfaces.
 *
 * Three exports:
 *
 *   - PRESETS — chrome preset → partial chrome blob (frontend mirror
 *     of backend chrome PRESETS, sub-arc C-1).
 *   - expandPreset(chrome) — fills missing fields from the preset's
 *     defaults (preset === "custom" passes through).
 *   - resolveChromeStyle(chrome, tokens) — composes a CSSProperties
 *     object: background / borderRadius / boxShadow / padding /
 *     border / backdropFilter. Slider scrubs (elevation, corner,
 *     blur) bucket into 4 discrete tiers (0 / 8 / 14 / 24 px or
 *     equivalent shadow strength) — verbatim from C-1 / C-2.1
 *     visual canon.
 *
 * The resolver is pure (no React, no DOM). Consumers pass a
 * themeTokens map keyed on token-name-without-leading-dashes (the
 * shape BASE_TOKENS / platform_themes resolver returns).
 */
import type { CSSProperties } from "react"

export type PresetSlug =
  | "card"
  | "modal"
  | "dropdown"
  | "toast"
  | "floating"
  | "frosted"
  | "custom"

export interface ChromeView {
  preset: PresetSlug | null
  elevation: number | null
  corner_radius: number | null
  backdrop_blur: number | null
  background_token: string | null
  border_token: string | null
  padding_token: string | null
}

/** Frontend mirror of backend chrome PRESETS (sub-arc C-1 canon). */
export const PRESETS: Record<PresetSlug, Partial<ChromeView>> = {
  card: {
    background_token: "surface-elevated",
    elevation: 37,
    corner_radius: 37,
    padding_token: "space-6",
  },
  modal: {
    background_token: "surface-raised",
    elevation: 62,
    corner_radius: 62,
    padding_token: "space-6",
  },
  dropdown: {
    background_token: "surface-raised",
    elevation: 62,
    corner_radius: 37,
    padding_token: "space-2",
    border_token: "border-subtle",
  },
  toast: {
    background_token: "surface-raised",
    elevation: 87,
    corner_radius: 37,
    padding_token: "space-4",
  },
  floating: {
    background_token: "surface-raised",
    elevation: 87,
    corner_radius: 62,
    padding_token: "space-4",
    // Note: legacy `border-brass` retired in DESIGN_LANGUAGE Aesthetic
    // Arc Session 2 in favor of the canonical `border-accent` token.
    border_token: "border-accent",
  },
  frosted: {
    background_token: "surface-frosted",
    elevation: 50,
    corner_radius: 62,
    padding_token: "space-6",
    backdrop_blur: 60,
    border_token: "border-subtle",
  },
  custom: {},
}

/** Padding token → applied pixel value. */
export const PADDING_PX: Record<string, number> = {
  "space-2": 8,
  "space-4": 16,
  "space-6": 24,
  "space-8": 32,
}

export function expandPreset(chrome: ChromeView): ChromeView {
  const preset = chrome.preset
  if (!preset || preset === "custom") return chrome
  const defaults = PRESETS[preset]
  const merged: ChromeView = { ...chrome }
  for (const key of Object.keys(defaults) as (keyof ChromeView)[]) {
    if (chrome[key] === null || chrome[key] === undefined) {
      ;(merged as unknown as Record<string, unknown>)[key] = defaults[
        key
      ] as unknown
    }
  }
  return merged
}

export function elevationToBoxShadow(v: number | null): string {
  if (v === null || v <= 25) return "none"
  if (v <= 50) return "0 2px 6px rgba(48, 32, 16, 0.10)"
  if (v <= 75) return "0 8px 24px rgba(48, 32, 16, 0.14)"
  return "0 16px 48px rgba(48, 32, 16, 0.20)"
}

export function cornerToPx(v: number | null): number {
  if (v === null || v <= 25) return 0
  if (v <= 50) return 8
  if (v <= 75) return 14
  return 24
}

export function blurToPx(v: number | null): number {
  if (v === null || v <= 25) return 0
  if (v <= 50) return 8
  if (v <= 75) return 14
  return 24
}

/** Coerce a draft-shaped Record into a strictly-typed ChromeView. */
export function chromeViewFromDraft(
  draft: Record<string, unknown> | null | undefined,
): ChromeView {
  const d = draft ?? {}
  return {
    preset: (d.preset as PresetSlug | null | undefined) ?? null,
    elevation: (d.elevation as number | null | undefined) ?? null,
    corner_radius: (d.corner_radius as number | null | undefined) ?? null,
    backdrop_blur: (d.backdrop_blur as number | null | undefined) ?? null,
    background_token:
      (d.background_token as string | null | undefined) ?? null,
    border_token: (d.border_token as string | null | undefined) ?? null,
    padding_token: (d.padding_token as string | null | undefined) ?? null,
  }
}

/**
 * Merge a Tier 1 core's chrome with a Tier 2 template's chrome
 * overrides. Field-presence cascade: any non-null/undefined field on
 * the overrides wins over the core's value. Null entries on the
 * overrides are treated as "inherit" (preserve the core's value),
 * matching the backend resolver's field-presence semantics.
 */
export function mergeChromeWithOverrides(
  coreChrome: Record<string, unknown> | null | undefined,
  overrides: Record<string, unknown> | null | undefined,
): ChromeView {
  const core = chromeViewFromDraft(coreChrome)
  const ov = chromeViewFromDraft(overrides)
  const merged: ChromeView = { ...core }
  for (const key of Object.keys(merged) as (keyof ChromeView)[]) {
    const v = ov[key]
    if (v !== null && v !== undefined) {
      ;(merged as unknown as Record<string, unknown>)[key] = v
    }
  }
  return merged
}

/**
 * Compose a CSSProperties object from a resolved chrome view + a
 * theme tokens map (token-name → resolved CSS value).
 */
export function resolveChromeStyle(
  view: ChromeView,
  tokens: Record<string, string>,
): CSSProperties {
  const blur = blurToPx(view.backdrop_blur ?? null)
  const blurActive = (view.backdrop_blur ?? 0) > 25
  return {
    background:
      tokens[view.background_token ?? "surface-elevated"] ??
      "var(--surface-elevated)",
    borderRadius: cornerToPx(view.corner_radius ?? null),
    boxShadow: elevationToBoxShadow(view.elevation ?? null),
    padding: PADDING_PX[view.padding_token ?? "space-6"] ?? 24,
    border: view.border_token
      ? `1px solid ${tokens[view.border_token] ?? "var(--border-subtle)"}`
      : "1px solid transparent",
    backdropFilter: blurActive ? `blur(${blur}px)` : undefined,
    WebkitBackdropFilter: blurActive ? `blur(${blur}px)` : undefined,
    transition: "all 200ms ease-out",
  }
}
