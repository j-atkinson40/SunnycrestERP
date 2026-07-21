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
  // Accent (DL §5 — chrome)
  accent: string
  "accent-hover": string
  "accent-active": string
  "accent-disabled": string
  "accent-muted": string
  "accent-subtle": string
  // Signature (DL §6 — rationed steel)
  "signature-steel": string
  "signature-steel-ring": string
  // Edge specular (DL §3)
  "edge-specular": string
  // Status (DL §7 — functional color)
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
    // Surfaces (Braun light — calibrated to approved console/Braun directions (eyeballed; open to photo-dial);
    // MUST byte-match tokens.css :root)
    "surface-base": "oklch(0.94 0.003 250)",
    "surface-elevated": "oklch(0.98 0.002 250)",
    "surface-raised": "oklch(1 0 0)",
    "surface-sunken": "oklch(0.92 0.003 250)",
    "surface-frosted": "oklch(0.98 0.002 250 / 0.60)",
    // Content
    "content-strong": "oklch(0.17 0.004 260)",
    "content-base": "oklch(0.22 0.004 260)",
    "content-muted": "oklch(0.52 0.006 258)",
    "content-subtle": "oklch(0.63 0.006 258)",
    "content-on-accent": "oklch(0.98 0.002 250)",
    // Borders
    "border-subtle": "oklch(0 0 0 / 0.08)",
    "border-base": "oklch(0 0 0 / 0.14)",
    "border-strong": "oklch(0.60 0.010 255)",
    "border-accent": "rgba(23, 24, 26, 0.70)",
    // Accent (chrome — ink in light mode)
    accent: "oklch(0.22 0.004 260)",
    "accent-hover": "oklch(0.30 0.005 260)",
    "accent-active": "oklch(0.16 0.004 260)",
    "accent-disabled": "oklch(0.80 0.004 250)",
    "accent-muted": "rgba(23, 24, 26, 0.12)",
    "accent-subtle": "rgba(23, 24, 26, 0.06)",
    // Signature steel (rationed)
    "signature-steel": "oklch(0.50 0.13 258)",
    "signature-steel-ring": "oklch(0.50 0.13 258 / 0.5)",
    // Edge specular
    "edge-specular": "oklch(1 0 0 / 0.65)",
    // Status (functional)
    "status-error": "oklch(0.55 0.13 37)",
    "status-error-muted": "oklch(0.94 0.03 37)",
    "status-warning": "oklch(0.63 0.11 78)",
    "status-warning-muted": "oklch(0.95 0.04 78)",
    "status-success": "oklch(0.56 0.11 156)",
    "status-success-muted": "oklch(0.94 0.04 156)",
    "status-info": "oklch(0.45 0.008 255)",
    "status-info-muted": "oklch(0.94 0.004 255)",
    // Shadows
    "shadow-color-subtle": "oklch(0.20 0.010 255 / 0.06)",
    "shadow-color-base": "oklch(0.20 0.010 255 / 0.10)",
    "shadow-color-strong": "oklch(0.18 0.010 255 / 0.16)",
  },
  dark: {
    // Surfaces (DL §3 — the hero mode, hue anchor 255)
    "surface-base": "oklch(0.13 0.004 255)",
    "surface-elevated": "oklch(0.21 0.006 255)",
    "surface-raised": "oklch(0.25 0.007 255)",
    "surface-sunken": "oklch(0.16 0.005 255)",
    "surface-frosted": "oklch(0.21 0.006 255 / 0.55)",
    // Content (DL §4)
    "content-strong": "oklch(0.97 0.003 260)",
    "content-base": "oklch(0.95 0.003 260)",
    "content-muted": "oklch(0.63 0.010 255)",
    "content-subtle": "oklch(0.52 0.008 255)",
    "content-on-accent": "oklch(0.13 0.004 255)",
    // Borders (§9 hairlines)
    "border-subtle": "oklch(1 0 0 / 0.05)",
    "border-base": "oklch(1 0 0 / 0.09)",
    "border-strong": "oklch(0.48 0.010 255)",
    "border-accent": "rgba(238, 241, 246, 0.70)",
    // Accent (chrome)
    accent: "oklch(0.94 0.006 255)",
    "accent-hover": "oklch(0.97 0.004 255)",
    "accent-active": "oklch(0.87 0.007 255)",
    "accent-disabled": "oklch(0.32 0.005 255)",
    "accent-muted": "rgba(238, 241, 246, 0.16)",
    "accent-subtle": "rgba(238, 241, 246, 0.08)",
    // Signature steel (console-calibrated)
    "signature-steel": "oklch(0.68 0.10 256)",
    "signature-steel-ring": "oklch(0.68 0.10 256 / 0.5)",
    // Edge specular (console-calibrated: 5.5%)
    "edge-specular": "oklch(1 0 0 / 0.055)",
    // Status (DL §7)
    "status-error": "oklch(0.68 0.14 38)",
    "status-error-muted": "oklch(0.26 0.05 38)",
    "status-warning": "oklch(0.76 0.13 75)",
    "status-warning-muted": "oklch(0.27 0.05 75)",
    "status-success": "oklch(0.79 0.14 158)",
    "status-success-muted": "oklch(0.25 0.05 158)",
    "status-info": "oklch(0.78 0.006 255)",
    "status-info-muted": "oklch(0.26 0.006 255)",
    // Shadows
    "shadow-color-subtle": "oklch(0.05 0.005 255 / 0.25)",
    "shadow-color-base": "oklch(0.05 0.005 255 / 0.35)",
    "shadow-color-strong": "oklch(0.03 0.005 255 / 0.50)",
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
