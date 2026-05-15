/**
 * BASE_TOKENS — shared substrate of platform-default token values.
 *
 * Sub-arc C-2.1 plumbing decision (Q7 lean option b): tokens.css is
 * the canonical platform-default source; platform_themes carries
 * vertical/tenant overrides only. The C-2 editor composes:
 *
 *   effective_tokens = { ...BASE_TOKENS[mode], ...resolved_overrides_from_platform_themes }
 *
 * This module mirrors the most-used token families from tokens.css
 * — surface / content / border / accent / status. A drift-gate
 * vitest test (`base-tokens.test.ts`) parses tokens.css at test
 * time and asserts the mirror tracks the source. Drift = test
 * failure.
 *
 * Replaces C-1's `FALLBACK_TOKENS` constant in
 * ChromePrimitivesDemoPage. Single source of truth for both the
 * demo page and the C-2.1 production editor.
 *
 * Token names WITHOUT leading `--` prefix (e.g. `surface-base`).
 * The chrome inspector's TokenSwatchPicker, theme resolver, and
 * cascade preview all consume this shape.
 */

export type BaseTokenMode = "light" | "dark"

export interface BaseTokenMap {
  // Surfaces (DL §3)
  "surface-base": string
  "surface-elevated": string
  "surface-raised": string
  "surface-sunken": string
  "surface-frosted": string
  // Content (DL §3)
  "content-strong": string
  "content-base": string
  "content-muted": string
  "content-subtle": string
  "content-on-accent": string
  // Borders (DL §3)
  "border-subtle": string
  "border-base": string
  "border-strong": string
  "border-accent": string
  // Accent (DL §3)
  accent: string
  "accent-hover": string
  "accent-muted": string
  "accent-subtle": string
  // Status (DL §3)
  "status-error": string
  "status-error-muted": string
  "status-warning": string
  "status-warning-muted": string
  "status-success": string
  "status-success-muted": string
  "status-info": string
  "status-info-muted": string
  // Shadow colors
  "shadow-color-subtle": string
  "shadow-color-base": string
  "shadow-color-strong": string
}

export const BASE_TOKENS: Record<BaseTokenMode, BaseTokenMap> = {
  light: {
    // Surfaces
    "surface-base": "oklch(0.94 0.030 82)",
    "surface-elevated": "oklch(0.965 0.014 82)",
    "surface-raised": "oklch(0.985 0.010 82)",
    "surface-sunken": "oklch(0.91 0.020 82)",
    "surface-frosted": "oklch(0.965 0.014 82 / 0.60)",
    // Content
    "content-strong": "oklch(0.22 0.015 70)",
    "content-base": "oklch(0.30 0.015 70)",
    "content-muted": "oklch(0.48 0.014 70)",
    "content-subtle": "oklch(0.62 0.012 70)",
    "content-on-accent": "oklch(0.98 0.006 82)",
    // Borders
    "border-subtle": "oklch(0.88 0.012 80 / 0.6)",
    "border-base": "oklch(0.82 0.015 78 / 0.8)",
    "border-strong": "oklch(0.70 0.020 76)",
    "border-accent": "rgba(156, 86, 64, 0.70)",
    // Accent
    accent: "oklch(0.46 0.10 39)",
    "accent-hover": "oklch(0.54 0.10 39)",
    "accent-muted": "rgba(156, 86, 64, 0.20)",
    "accent-subtle": "rgba(156, 86, 64, 0.10)",
    // Status
    "status-error": "oklch(0.55 0.18 25)",
    "status-error-muted": "oklch(0.92 0.04 25)",
    "status-warning": "oklch(0.70 0.14 65)",
    "status-warning-muted": "oklch(0.94 0.04 65)",
    "status-success": "oklch(0.58 0.12 135)",
    "status-success-muted": "oklch(0.93 0.04 135)",
    "status-info": "oklch(0.55 0.08 225)",
    "status-info-muted": "oklch(0.93 0.03 225)",
    // Shadows
    "shadow-color-subtle": "oklch(0.40 0.045 78 / 0.06)",
    "shadow-color-base": "oklch(0.40 0.045 78 / 0.10)",
    "shadow-color-strong": "oklch(0.37 0.050 75 / 0.16)",
  },
  dark: {
    // Surfaces (dark anchors per DL §3 dark-mode table)
    "surface-base": "oklch(0.17 0.012 65)",
    "surface-elevated": "oklch(0.20 0.014 65)",
    "surface-raised": "oklch(0.23 0.014 65)",
    "surface-sunken": "oklch(0.14 0.010 65)",
    "surface-frosted": "oklch(0.20 0.014 65 / 0.55)",
    // Content
    "content-strong": "oklch(0.96 0.008 82)",
    "content-base": "oklch(0.88 0.010 82)",
    "content-muted": "oklch(0.68 0.012 80)",
    "content-subtle": "oklch(0.52 0.012 78)",
    "content-on-accent": "oklch(0.18 0.012 65)",
    // Borders
    "border-subtle": "oklch(0.32 0.014 78 / 0.7)",
    "border-base": "oklch(0.42 0.016 76 / 0.85)",
    "border-strong": "oklch(0.55 0.020 74)",
    "border-accent": "rgba(180, 106, 77, 0.70)",
    // Accent
    accent: "oklch(0.46 0.10 39)",
    "accent-hover": "oklch(0.54 0.10 39)",
    "accent-muted": "rgba(180, 106, 77, 0.22)",
    "accent-subtle": "rgba(180, 106, 77, 0.12)",
    // Status
    "status-error": "oklch(0.62 0.18 25)",
    "status-error-muted": "oklch(0.22 0.07 25)",
    "status-warning": "oklch(0.74 0.14 65)",
    "status-warning-muted": "oklch(0.24 0.06 65)",
    "status-success": "oklch(0.64 0.12 135)",
    "status-success-muted": "oklch(0.22 0.05 135)",
    "status-info": "oklch(0.62 0.08 225)",
    "status-info-muted": "oklch(0.22 0.04 225)",
    // Shadows
    "shadow-color-subtle": "oklch(0.04 0.012 65 / 0.35)",
    "shadow-color-base": "oklch(0.04 0.012 65 / 0.45)",
    "shadow-color-strong": "oklch(0.04 0.012 65 / 0.60)",
  },
}

/**
 * Token keys exported for iteration / catalog cross-referencing.
 * Order is stable for snapshot-style tests.
 */
export const BASE_TOKEN_KEYS: ReadonlyArray<keyof BaseTokenMap> = Object.keys(
  BASE_TOKENS.light,
) as ReadonlyArray<keyof BaseTokenMap>

/**
 * Convenience accessor — returns the token map for a given mode.
 * Defensive: unknown mode → light defaults.
 */
export function baseTokensForMode(mode: string): BaseTokenMap {
  return BASE_TOKENS[(mode as BaseTokenMode) in BASE_TOKENS ? (mode as BaseTokenMode) : "light"]
}

export default BASE_TOKENS
