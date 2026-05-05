/**
 * Token catalog — Phase 2 of the Admin Visual Editor.
 *
 * Programmatic descriptor of every token in `tokens.css`. Editor
 * controls are dispatched per `valueType` + `category`. The catalog
 * is the source of truth for "what tokens exist" + "what their
 * platform defaults are" (in both light and dark mode); the
 * registry tracks "which components consume which tokens" — used
 * together by the editor.
 *
 * **Add new tokens here when adding to `tokens.css`** — the
 * vitest catalog-completeness test parses the CSS file at test
 * time and asserts every `--token-name` is represented here, so
 * drift is caught fast.
 *
 * Inheritance discipline (DESIGN_LANGUAGE.md §2): some tokens are
 * derived from others (e.g., `--shadow-level-1` references
 * `--shadow-color-base`). The `derivedFrom` field lets the editor
 * warn the operator that overriding the underlying token will
 * propagate to the derived token automatically.
 */


export type TokenCategory =
  | "surface"
  | "content"
  | "border"
  | "shadow-color"
  | "shadow-elevation"
  | "shadow-special"
  | "accent"
  | "status"
  | "focus-ring"
  | "typography-family"
  | "typography-size"
  | "radius"
  | "motion-duration"
  | "motion-easing"
  | "max-width"
  | "z-index"
  | "transform"


export type TokenValueType =
  | "oklch"
  | "oklch-with-alpha"
  | "rgba"
  | "alpha"
  | "rem"
  | "px"
  | "ms"
  | "cubic-bezier"
  | "font-family"
  | "shadow-composition"
  | "transform"
  | "integer"


export interface TokenModeDefaults {
  light: string
  dark: string
}


export interface TokenEntry {
  /** CSS variable name without leading `--`. */
  name: string
  category: TokenCategory
  subcategory?: string
  displayName: string
  description?: string
  valueType: TokenValueType
  defaults: TokenModeDefaults
  /** For numeric values: optional [min, max] in source units. For
   * enum-like values (cubic-bezier, font-family): array of allowed
   * values. */
  bounds?: unknown
  /** Other token names this token references in its value. The
   * editor uses this to warn that overriding the upstream token
   * will propagate. */
  derivedFrom?: string[]
  /** When false, the editor renders read-only with an explanation
   * (used for tokens that are computed compositions of other
   * tokens — operators should override the upstream tokens
   * instead). */
  editable?: boolean
}


// ─── Helpers for the test parser ────────────────────────────────


/** Categorize a value-type into a coarse "color" bucket the editor
 * picker layer uses. */
export function isColorToken(t: TokenEntry): boolean {
  return (
    t.valueType === "oklch" ||
    t.valueType === "oklch-with-alpha" ||
    t.valueType === "rgba"
  )
}


// ─── Catalog ────────────────────────────────────────────────────


export const TOKEN_CATALOG: TokenEntry[] = [
  // ── Surface family ──────────────────────────────────────────
  {
    name: "surface-base",
    category: "surface",
    displayName: "Surface — Base",
    description:
      "Page background. Light mode is warm cream; dark mode is warm charcoal — Mediterranean garden morning vs cocktail lounge evening. Lifts step ~0.025 light / ~0.06 dark per elevation level.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.94 0.030 82)",
      dark: "oklch(0.16 0.010 59)",
    },
  },
  {
    name: "surface-elevated",
    category: "surface",
    displayName: "Surface — Elevated",
    description:
      "Card body — first lift above the page. Hue warms slightly with elevation in dark mode (catches more lamplight).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.965 0.014 82)",
      dark: "oklch(0.28 0.014 81)",
    },
  },
  {
    name: "surface-raised",
    category: "surface",
    displayName: "Surface — Raised",
    description:
      "Modals, dropdowns, popovers, slide-over rails. Second lift above page.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.985 0.010 82)",
      dark: "oklch(0.32 0.016 85)",
    },
  },
  {
    name: "surface-sunken",
    category: "surface",
    displayName: "Surface — Sunken",
    description:
      "Recessed track surface — sidebar shell, footer regions, skeleton placeholders.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.91 0.020 82)",
      dark: "oklch(0.13 0.010 55)",
    },
  },

  // ── Content family ──────────────────────────────────────────
  {
    name: "content-strong",
    category: "content",
    displayName: "Content — Strong",
    description: "Page titles, h1-h3, primary KPIs.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.22 0.015 70)",
      dark: "oklch(0.96 0.012 80)",
    },
  },
  {
    name: "content-base",
    category: "content",
    displayName: "Content — Base",
    description: "Body text, primary readable surfaces.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.30 0.015 70)",
      dark: "oklch(0.90 0.014 75)",
    },
  },
  {
    name: "content-muted",
    category: "content",
    displayName: "Content — Muted",
    description: "Secondary text, helper copy, captions.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.48 0.014 70)",
      dark: "oklch(0.72 0.014 70)",
    },
  },
  {
    name: "content-subtle",
    category: "content",
    displayName: "Content — Subtle",
    description: "Placeholder text, ghost states, fine-print.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.62 0.012 70)",
      dark: "oklch(0.55 0.012 68)",
    },
  },
  {
    name: "content-on-accent",
    category: "content",
    displayName: "Content — On Accent",
    description: "Text rendered on accent-filled surfaces (brass buttons, etc.). Light cream in both modes.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.98 0.006 82)",
      dark: "oklch(0.98 0.006 82)",
    },
  },

  // ── Border family ───────────────────────────────────────────
  {
    name: "border-subtle",
    category: "border",
    displayName: "Border — Subtle",
    description: "Whispers — internal section dividers, footer separators.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.88 0.012 80 / 0.6)",
      dark: "oklch(0.35 0.015 65 / 0.5)",
    },
  },
  {
    name: "border-base",
    category: "border",
    displayName: "Border — Base",
    description: "Form input borders, table rules, default outlines.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.82 0.015 78 / 0.8)",
      dark: "oklch(0.42 0.018 68 / 0.7)",
    },
  },
  {
    name: "border-strong",
    category: "border",
    displayName: "Border — Strong",
    description: "Emphasis borders, active form outlines, status callouts.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.70 0.020 76)",
      dark: "oklch(0.55 0.025 70)",
    },
  },
  {
    name: "border-accent",
    category: "border",
    displayName: "Border — Accent",
    description: "Primary accent border — selected items, active states.",
    valueType: "rgba",
    defaults: {
      light: "rgba(156, 86, 64, 0.70)",
      dark: "rgba(156, 86, 64, 0.70)",
    },
  },

  // ── Shadow color ────────────────────────────────────────────
  {
    name: "shadow-color-subtle",
    category: "shadow-color",
    displayName: "Shadow Color — Subtle",
    description: "Faintest shadow tint — used as secondary halo on multi-layer compositions.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.40 0.045 78 / 0.06)",
      dark: "oklch(0.11 0.020 65 / 0.35)",
    },
  },
  {
    name: "shadow-color-base",
    category: "shadow-color",
    displayName: "Shadow Color — Base",
    description: "Default shadow tint — primary halo at every elevation.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.40 0.045 78 / 0.10)",
      dark: "oklch(0.09 0.020 65 / 0.45)",
    },
  },
  {
    name: "shadow-color-strong",
    category: "shadow-color",
    displayName: "Shadow Color — Strong",
    description: "Tight grounding shadow — used as the close-to-surface layer in dark-mode three-layer compositions.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.37 0.050 75 / 0.16)",
      dark: "oklch(0.08 0.020 65 / 0.55)",
    },
  },
  {
    name: "shadow-highlight-top",
    category: "shadow-color",
    displayName: "Shadow Highlight — Top",
    description:
      "Top-edge inset highlight (dark mode focused-light-pool effect). Per Tier-4 measurement: 3px band at L=0.32, alpha 0.9. Light mode: not rendered (morning light is ambient + diffuse).",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "transparent",
      dark: "oklch(0.32 0.010 61 / 0.9)",
    },
  },

  // ── Shadow elevation (compositions) ─────────────────────────
  {
    name: "shadow-level-1",
    category: "shadow-elevation",
    displayName: "Shadow Level 1",
    description:
      "Cards, widgets, pinned items. Single-layer in light; three-layer (tight ground + soft halo + 3px top-edge inset highlight) in dark.",
    valueType: "shadow-composition",
    defaults: {
      light: "0 2px 8px var(--shadow-color-base)",
      dark:
        "0 1px 3px var(--shadow-color-strong), 0 4px 16px var(--shadow-color-base), inset 0 3px 0 var(--shadow-highlight-top)",
    },
    derivedFrom: ["shadow-color-base", "shadow-color-strong", "shadow-highlight-top"],
    editable: false,
  },
  {
    name: "shadow-level-2",
    category: "shadow-elevation",
    displayName: "Shadow Level 2",
    description: "Dialogs, dropdowns, popovers, notification rails.",
    valueType: "shadow-composition",
    defaults: {
      light: "0 8px 24px var(--shadow-color-base), 0 2px 6px var(--shadow-color-subtle)",
      dark: "(see tokens.css — three-layer composition)",
    },
    derivedFrom: ["shadow-color-base", "shadow-color-subtle", "shadow-color-strong", "shadow-highlight-top"],
    editable: false,
  },
  {
    name: "shadow-level-3",
    category: "shadow-elevation",
    displayName: "Shadow Level 3",
    description: "Slide-overs, focus modals, peak elevation.",
    valueType: "shadow-composition",
    defaults: {
      light: "0 16px 40px var(--shadow-color-strong), 0 4px 12px var(--shadow-color-base)",
      dark: "(see tokens.css — three-layer composition)",
    },
    derivedFrom: ["shadow-color-strong", "shadow-color-base", "shadow-highlight-top"],
    editable: false,
  },

  // ── Shadow specialty (read-only) ────────────────────────────
  {
    name: "shadow-widget-tablet",
    category: "shadow-special",
    displayName: "Shadow — Widget Tablet",
    description: "Pulse/widget-tablet ambient shadow. Read-only composition.",
    valueType: "shadow-composition",
    defaults: { light: "(composition)", dark: "(composition)" },
    derivedFrom: ["shadow-level-1"],
    editable: false,
  },
  {
    name: "shadow-jewel-inset",
    category: "shadow-special",
    displayName: "Shadow — Jewel Inset",
    description: "Inset jewel highlight on accent-filled surfaces.",
    valueType: "shadow-composition",
    defaults: {
      light: "inset 0 1px 2px rgba(0, 0, 0, 0.25)",
      dark: "inset 0 1px 2px rgba(0, 0, 0, 0.25)",
    },
    editable: false,
  },
  {
    name: "card-ambient-shadow",
    category: "shadow-special",
    displayName: "Card Ambient Shadow",
    description: "Card-specific ambient halo. Computed from level-1.",
    valueType: "shadow-composition",
    defaults: { light: "(computed)", dark: "(computed)" },
    derivedFrom: ["shadow-level-1"],
    editable: false,
  },
  {
    name: "card-edge-highlight",
    category: "shadow-special",
    displayName: "Card Edge Highlight",
    description: "Top-edge highlight on cards (dark mode only).",
    valueType: "shadow-composition",
    defaults: { light: "(none)", dark: "(computed)" },
    derivedFrom: ["shadow-highlight-top"],
    editable: false,
  },
  {
    name: "card-edge-shadow",
    category: "shadow-special",
    displayName: "Card Edge Shadow",
    description: "Bottom-edge cast shadow on cards.",
    valueType: "shadow-composition",
    defaults: { light: "(computed)", dark: "(computed)" },
    derivedFrom: ["shadow-color-strong"],
    editable: false,
  },
  {
    name: "flag-press-shadow",
    category: "shadow-special",
    displayName: "Flag Press Shadow",
    description: "Active-press shadow for buttons/flags.",
    valueType: "shadow-composition",
    defaults: { light: "(computed)", dark: "(computed)" },
    editable: false,
  },
  {
    name: "widget-ambient-shadow",
    category: "shadow-special",
    displayName: "Widget Ambient Shadow",
    description: "Widget-specific ambient halo.",
    valueType: "shadow-composition",
    defaults: { light: "(computed)", dark: "(computed)" },
    derivedFrom: ["shadow-color-base"],
    editable: false,
  },

  // ── Accent family ───────────────────────────────────────────
  {
    name: "accent",
    category: "accent",
    displayName: "Accent — Primary",
    description:
      "Single canonical accent across both modes — deepened terracotta at oklch(0.46 0.10 39). Per Aesthetic Arc Session 2: warm-family asymmetric to substrate (warm cream substrate hue ~82, accent hue 39); reads as 'earthen architectural detail on warm stone' rather than yellow-on-yellow.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.46 0.10 39)",
      dark: "oklch(0.46 0.10 39)",
    },
  },
  {
    name: "accent-hover",
    category: "accent",
    displayName: "Accent — Hover",
    description:
      "Universal lift signal — accent brightens on hover in BOTH modes (replaces brass-era asymmetric press-in light / glow dark pattern).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.54 0.10 39)",
      dark: "oklch(0.54 0.10 39)",
    },
  },
  {
    name: "accent-muted",
    category: "accent",
    displayName: "Accent — Muted",
    description: "20%-alpha accent fill — count badges, secondary chips.",
    valueType: "rgba",
    defaults: {
      light: "rgba(156, 86, 64, 0.20)",
      dark: "rgba(156, 86, 64, 0.20)",
    },
  },
  {
    name: "accent-subtle",
    category: "accent",
    displayName: "Accent — Subtle",
    description: "10%-alpha accent fill — selected items, hover backgrounds.",
    valueType: "rgba",
    defaults: {
      light: "rgba(156, 86, 64, 0.10)",
      dark: "rgba(156, 86, 64, 0.10)",
    },
  },
  {
    name: "accent-confirmed",
    category: "accent",
    subcategory: "confirmed",
    displayName: "Accent — Confirmed",
    description: "Sage-green confirmed state.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.58 0.05 138)",
      dark: "oklch(0.58 0.05 138)",
    },
  },

  // ── Status family ───────────────────────────────────────────
  {
    name: "status-error",
    category: "status",
    subcategory: "error",
    displayName: "Status — Error",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.55 0.18 25)",
      dark: "oklch(0.68 0.17 25)",
    },
  },
  {
    name: "status-error-muted",
    category: "status",
    subcategory: "error",
    displayName: "Status — Error Muted",
    description: "Error background fill — paired with status-error text.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.92 0.04 25)",
      dark: "oklch(0.22 0.07 25)",
    },
  },
  {
    name: "status-warning",
    category: "status",
    subcategory: "warning",
    displayName: "Status — Warning",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.70 0.14 65)",
      dark: "oklch(0.76 0.14 65)",
    },
  },
  {
    name: "status-warning-muted",
    category: "status",
    subcategory: "warning",
    displayName: "Status — Warning Muted",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.94 0.04 65)",
      dark: "oklch(0.24 0.06 65)",
    },
  },
  {
    name: "status-success",
    category: "status",
    subcategory: "success",
    displayName: "Status — Success",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.58 0.12 135)",
      dark: "oklch(0.70 0.13 135)",
    },
  },
  {
    name: "status-success-muted",
    category: "status",
    subcategory: "success",
    displayName: "Status — Success Muted",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.93 0.04 135)",
      dark: "oklch(0.22 0.05 135)",
    },
  },
  {
    name: "status-info",
    category: "status",
    subcategory: "info",
    displayName: "Status — Info",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.55 0.08 225)",
      dark: "oklch(0.70 0.09 225)",
    },
  },
  {
    name: "status-info-muted",
    category: "status",
    subcategory: "info",
    displayName: "Status — Info Muted",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.93 0.03 225)",
      dark: "oklch(0.22 0.04 225)",
    },
  },

  // ── Focus ring ──────────────────────────────────────────────
  {
    name: "focus-ring-alpha",
    category: "focus-ring",
    displayName: "Focus Ring Alpha",
    description:
      "Brass focus ring opacity. Tier-4 raised to 0.40 light / 0.48 dark for WCAG 2.4.7 contrast on raised surface.",
    valueType: "alpha",
    defaults: { light: "0.40", dark: "0.48" },
    bounds: [0, 1],
  },

  // ── Typography family ───────────────────────────────────────
  {
    name: "font-fraunces",
    category: "typography-family",
    displayName: "Font — Fraunces",
    description: "Display serif. Used for h1–h3 + briefing headers.",
    valueType: "font-family",
    defaults: {
      light: '"Fraunces Variable", "Fraunces", Georgia, "Times New Roman", serif',
      dark: '"Fraunces Variable", "Fraunces", Georgia, "Times New Roman", serif',
    },
  },
  {
    name: "font-geist",
    category: "typography-family",
    displayName: "Font — Geist Sans",
    description: "Body sans. Default for prose + form labels.",
    valueType: "font-family",
    defaults: {
      light:
        '"Geist Variable", "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      dark:
        '"Geist Variable", "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    },
  },
  {
    name: "font-geist-mono",
    category: "typography-family",
    displayName: "Font — Geist Mono",
    description: "Monospace. Used for IDs, timestamps, code, count badges.",
    valueType: "font-family",
    defaults: {
      light:
        '"Geist Mono Variable", "Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace',
      dark:
        '"Geist Mono Variable", "Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace',
    },
  },
  {
    name: "font-plex-sans",
    category: "typography-family",
    displayName: "Font — Plex Sans (alias)",
    description: "Alias to font-geist. Legacy name preserved during font migration.",
    valueType: "font-family",
    defaults: { light: "var(--font-geist)", dark: "var(--font-geist)" },
    derivedFrom: ["font-geist"],
    editable: false,
  },
  {
    name: "font-plex-serif",
    category: "typography-family",
    displayName: "Font — Plex Serif (alias)",
    description: "Alias to font-fraunces.",
    valueType: "font-family",
    defaults: { light: "var(--font-fraunces)", dark: "var(--font-fraunces)" },
    derivedFrom: ["font-fraunces"],
    editable: false,
  },
  {
    name: "font-plex-mono",
    category: "typography-family",
    displayName: "Font — Plex Mono (alias)",
    description: "Alias to font-geist-mono.",
    valueType: "font-family",
    defaults: { light: "var(--font-geist-mono)", dark: "var(--font-geist-mono)" },
    derivedFrom: ["font-geist-mono"],
    editable: false,
  },

  // ── Typography size (modular scale) ─────────────────────────
  {
    name: "text-display-lg",
    category: "typography-size",
    displayName: "Text — Display Large",
    description: "Hero scale, marketing headers.",
    valueType: "rem",
    defaults: { light: "3.052rem", dark: "3.052rem" },
    bounds: [1, 6],
  },
  {
    name: "text-display",
    category: "typography-size",
    displayName: "Text — Display",
    description: "Page hero, primary KPI numerics.",
    valueType: "rem",
    defaults: { light: "2.441rem", dark: "2.441rem" },
    bounds: [1, 5],
  },
  {
    name: "text-h1",
    category: "typography-size",
    displayName: "Text — H1",
    valueType: "rem",
    defaults: { light: "1.953rem", dark: "1.953rem" },
    bounds: [1, 4],
  },
  {
    name: "text-h2",
    category: "typography-size",
    displayName: "Text — H2",
    valueType: "rem",
    defaults: { light: "1.563rem", dark: "1.563rem" },
    bounds: [1, 3],
  },
  {
    name: "text-h3",
    category: "typography-size",
    displayName: "Text — H3",
    valueType: "rem",
    defaults: { light: "1.25rem", dark: "1.25rem" },
    bounds: [0.875, 2],
  },
  {
    name: "text-h4",
    category: "typography-size",
    displayName: "Text — H4",
    valueType: "rem",
    defaults: { light: "1.125rem", dark: "1.125rem" },
    bounds: [0.875, 2],
  },
  {
    name: "text-body",
    category: "typography-size",
    displayName: "Text — Body",
    description: "Default reading size.",
    valueType: "rem",
    defaults: { light: "1rem", dark: "1rem" },
    bounds: [0.75, 1.5],
  },
  {
    name: "text-body-sm",
    category: "typography-size",
    displayName: "Text — Body Small",
    valueType: "rem",
    defaults: { light: "0.875rem", dark: "0.875rem" },
    bounds: [0.625, 1.25],
  },
  {
    name: "text-caption",
    category: "typography-size",
    displayName: "Text — Caption",
    description: "Helper text, secondary labels.",
    valueType: "rem",
    defaults: { light: "0.75rem", dark: "0.75rem" },
    bounds: [0.5, 1],
  },
  {
    name: "text-micro",
    category: "typography-size",
    displayName: "Text — Micro",
    description: "Eyebrows, micro-caps tracking.",
    valueType: "rem",
    defaults: { light: "0.6875rem", dark: "0.6875rem" },
    bounds: [0.5, 1],
  },

  // ── Radius ──────────────────────────────────────────────────
  {
    name: "radius-base",
    category: "radius",
    displayName: "Radius — Base",
    description: "Default corner radius. Pairs with rounded-md utility.",
    valueType: "px",
    defaults: { light: "6px", dark: "6px" },
    bounds: [0, 32],
  },
  {
    name: "radius-full",
    category: "radius",
    displayName: "Radius — Full",
    description: "Pill rounding (chips, status pills, avatar).",
    valueType: "px",
    defaults: { light: "9999px", dark: "9999px" },
    bounds: [0, 9999],
    editable: false,
  },

  // ── Motion duration ─────────────────────────────────────────
  {
    name: "duration-instant",
    category: "motion-duration",
    displayName: "Duration — Instant",
    description: "Snap responses (cursor pointer change, hover tint).",
    valueType: "ms",
    defaults: { light: "100ms", dark: "100ms" },
    bounds: [0, 500],
  },
  {
    name: "duration-quick",
    category: "motion-duration",
    displayName: "Duration — Quick",
    description: "Color transitions, opacity fades.",
    valueType: "ms",
    defaults: { light: "200ms", dark: "200ms" },
    bounds: [0, 800],
  },
  {
    name: "duration-settle",
    category: "motion-duration",
    displayName: "Duration — Settle",
    description: "Layout settles, popover open/close.",
    valueType: "ms",
    defaults: { light: "300ms", dark: "300ms" },
    bounds: [0, 1200],
  },
  {
    name: "duration-arrive",
    category: "motion-duration",
    displayName: "Duration — Arrive",
    description: "Modal/dialog enter — gentler entrance feel.",
    valueType: "ms",
    defaults: { light: "400ms", dark: "400ms" },
    bounds: [0, 1500],
  },
  {
    name: "duration-considered",
    category: "motion-duration",
    displayName: "Duration — Considered",
    description: "Multi-step transitions, narrative reveals.",
    valueType: "ms",
    defaults: { light: "600ms", dark: "600ms" },
    bounds: [0, 2000],
  },

  // ── Motion easing ───────────────────────────────────────────
  {
    name: "ease-settle",
    category: "motion-easing",
    displayName: "Ease — Settle",
    description: "Default easing for layout settles + arrives.",
    valueType: "cubic-bezier",
    defaults: {
      light: "cubic-bezier(0.2, 0, 0.1, 1)",
      dark: "cubic-bezier(0.2, 0, 0.1, 1)",
    },
  },
  {
    name: "ease-gentle",
    category: "motion-easing",
    displayName: "Ease — Gentle",
    description: "Softer easing for exits + secondary motion.",
    valueType: "cubic-bezier",
    defaults: {
      light: "cubic-bezier(0.4, 0, 0.4, 1)",
      dark: "cubic-bezier(0.4, 0, 0.4, 1)",
    },
  },

  // ── Max width ───────────────────────────────────────────────
  {
    name: "max-w-reading",
    category: "max-width",
    displayName: "Max Width — Reading",
    description: "Optimal prose line-length.",
    valueType: "rem",
    defaults: { light: "34rem", dark: "34rem" },
    bounds: [20, 80],
  },
  {
    name: "max-w-form",
    category: "max-width",
    displayName: "Max Width — Form",
    valueType: "rem",
    defaults: { light: "40rem", dark: "40rem" },
    bounds: [20, 80],
  },
  {
    name: "max-w-content",
    category: "max-width",
    displayName: "Max Width — Content",
    valueType: "rem",
    defaults: { light: "56rem", dark: "56rem" },
    bounds: [40, 120],
  },
  {
    name: "max-w-wide",
    category: "max-width",
    displayName: "Max Width — Wide",
    valueType: "rem",
    defaults: { light: "72rem", dark: "72rem" },
    bounds: [48, 144],
  },
  {
    name: "max-w-dashboard",
    category: "max-width",
    displayName: "Max Width — Dashboard",
    description: "Operations Board, Vault Overview, primary work surfaces.",
    valueType: "rem",
    defaults: { light: "96rem", dark: "96rem" },
    bounds: [64, 160],
  },

  // ── Z-index (layering) ──────────────────────────────────────
  {
    name: "z-base",
    category: "z-index",
    displayName: "Z — Base",
    valueType: "integer",
    defaults: { light: "0", dark: "0" },
    editable: false,
  },
  {
    name: "z-elevated",
    category: "z-index",
    displayName: "Z — Elevated",
    valueType: "integer",
    defaults: { light: "10", dark: "10" },
    editable: false,
  },
  {
    name: "z-dropdown",
    category: "z-index",
    displayName: "Z — Dropdown",
    valueType: "integer",
    defaults: { light: "50", dark: "50" },
    editable: false,
  },
  {
    name: "z-focus",
    category: "z-index",
    displayName: "Z — Focus",
    valueType: "integer",
    defaults: { light: "100", dark: "100" },
    editable: false,
  },
  {
    name: "z-modal",
    category: "z-index",
    displayName: "Z — Modal",
    valueType: "integer",
    defaults: { light: "105", dark: "105" },
    editable: false,
  },
  {
    name: "z-command-bar",
    category: "z-index",
    displayName: "Z — Command Bar",
    valueType: "integer",
    defaults: { light: "110", dark: "110" },
    editable: false,
  },
  {
    name: "z-toast",
    category: "z-index",
    displayName: "Z — Toast",
    valueType: "integer",
    defaults: { light: "120", dark: "120" },
    editable: false,
  },
  {
    name: "z-tooltip",
    category: "z-index",
    displayName: "Z — Tooltip",
    valueType: "integer",
    defaults: { light: "130", dark: "130" },
    editable: false,
  },

  // ── Transform ───────────────────────────────────────────────
  {
    name: "widget-tablet-transform",
    category: "transform",
    displayName: "Widget Tablet Transform",
    description: "Subtle lift on widget-tablet hover/active.",
    valueType: "transform",
    defaults: { light: "translateY(-2px)", dark: "translateY(-2px)" },
  },
]


// ─── Indexes ────────────────────────────────────────────────────


export function getTokenByName(name: string): TokenEntry | undefined {
  return TOKEN_CATALOG.find((t) => t.name === name)
}


export function getTokensByCategory(category: TokenCategory): TokenEntry[] {
  return TOKEN_CATALOG.filter((t) => t.category === category)
}


export function getCategoryOrder(): TokenCategory[] {
  return [
    "surface",
    "content",
    "border",
    "accent",
    "status",
    "shadow-color",
    "shadow-elevation",
    "shadow-special",
    "focus-ring",
    "typography-family",
    "typography-size",
    "radius",
    "motion-duration",
    "motion-easing",
    "max-width",
    "z-index",
    "transform",
  ]
}


export function getCategoryLabel(category: TokenCategory): string {
  const labels: Record<TokenCategory, string> = {
    surface: "Surface",
    content: "Content",
    border: "Border",
    accent: "Accent",
    status: "Status",
    "shadow-color": "Shadow color",
    "shadow-elevation": "Shadow elevation",
    "shadow-special": "Shadow specialty",
    "focus-ring": "Focus ring",
    "typography-family": "Typography — family",
    "typography-size": "Typography — size",
    radius: "Radius",
    "motion-duration": "Motion — duration",
    "motion-easing": "Motion — easing",
    "max-width": "Max width",
    "z-index": "Z-index",
    transform: "Transform",
  }
  return labels[category]
}
