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
  | "signature"
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
    displayName: "Surface — Base (substrate)",
    description:
      "Page canvas (new-doc name: --substrate-base). Chrome/steel language: cool neutral at hue anchor 255, dark-first. Light values provisional pending mood-anchor calibration.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.965 0.004 255)",
      dark: "oklch(0.16 0.008 255)",
    },
  },
  {
    name: "surface-elevated",
    category: "surface",
    displayName: "Surface — Elevated (panel)",
    description:
      "Panel / card body (new-doc name: --surface-2). First lift above the canvas. Panels never render as flat fills — the card family composes --panel-gradient + --edge-specular + shadow on top.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.985 0.002 255)",
      dark: "oklch(0.21 0.009 255)",
    },
  },
  {
    name: "surface-raised",
    category: "surface",
    displayName: "Surface — Raised (popover)",
    description:
      "Modals, dropdowns, popovers, slide-over rails (new-doc name: --surface-3). Second lift above the canvas.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.995 0.002 255)",
      dark: "oklch(0.24 0.010 255)",
    },
  },
  {
    name: "surface-sunken",
    category: "surface",
    displayName: "Surface — Sunken (rail)",
    description:
      "Rail / recessed surface (new-doc name: --surface-1) — sidebar shell, footer regions, skeleton placeholders. Dark mode sits between substrate and panel per §3; light mode recesses below the canvas.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.945 0.005 255)",
      dark: "oklch(0.18 0.008 255)",
    },
  },
  {
    name: "surface-frosted",
    category: "surface",
    displayName: "Surface — Frosted (translucent)",
    description:
      "Translucent variant for backdrop-filter glass surfaces (sub-arc C-1.1 frosted chrome preset). Alpha channel is load-bearing — opaque backgrounds mask backdrop-filter blur. Tracks --surface-elevated.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.985 0.002 255 / 0.60)",
      dark: "oklch(0.21 0.009 255 / 0.55)",
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
      light: "oklch(0.17 0.008 255)",
      dark: "oklch(0.97 0.004 255)",
    },
  },
  {
    name: "content-base",
    category: "content",
    displayName: "Content — Base",
    description: "Body text, primary readable surfaces (§4 --text-primary).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.24 0.008 255)",
      dark: "oklch(0.95 0.004 255)",
    },
  },
  {
    name: "content-muted",
    category: "content",
    displayName: "Content — Muted",
    description: "Secondary text, helper copy, captions (§4 --text-secondary).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.47 0.008 255)",
      dark: "oklch(0.66 0.006 255)",
    },
  },
  {
    name: "content-subtle",
    category: "content",
    displayName: "Content — Subtle",
    description: "Placeholder text, ghost states, fine-print (§4 --text-muted).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.60 0.007 255)",
      dark: "oklch(0.55 0.006 255)",
    },
  },
  {
    name: "content-on-accent",
    category: "content",
    displayName: "Content — On Accent (on-chrome)",
    description:
      "Text rendered on chrome-filled surfaces (new-doc name: --on-chrome). Dark mode = the substrate value (dark text on bright chrome); light mode = near-white text on the ink fill. Couples to --accent by design.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.97 0.003 255)",
      dark: "oklch(0.16 0.008 255)",
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
      light: "oklch(0.15 0.010 255 / 0.07)",
      dark: "oklch(1 0 0 / 0.05)",
    },
  },
  {
    name: "border-base",
    category: "border",
    displayName: "Border — Base",
    description: "Form input borders, table rules, default outlines.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.15 0.010 255 / 0.13)",
      dark: "oklch(1 0 0 / 0.09)",
    },
  },
  {
    name: "border-strong",
    category: "border",
    displayName: "Border — Strong",
    description: "Emphasis borders, active form outlines, status callouts.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.60 0.010 255)",
      dark: "oklch(0.48 0.010 255)",
    },
  },
  {
    name: "border-accent",
    category: "border",
    displayName: "Border — Accent (chrome)",
    description:
      "Chrome accent border — selected items, active states. Re-derived for the near-monochrome accent: ink at 70% in light mode, chrome at 70% in dark.",
    valueType: "rgba",
    defaults: {
      light: "rgba(38, 41, 48, 0.70)",
      dark: "rgba(233, 234, 238, 0.70)",
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
      light: "oklch(0.20 0.010 255 / 0.06)",
      dark: "oklch(0.05 0.005 255 / 0.25)",
    },
  },
  {
    name: "shadow-color-base",
    category: "shadow-color",
    displayName: "Shadow Color — Base",
    description:
      "Default shadow tint — primary halo at every elevation. Dark-mode alpha 0.35 = the §3 --shadow-panel alpha.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.20 0.010 255 / 0.10)",
      dark: "oklch(0.05 0.005 255 / 0.35)",
    },
  },
  {
    name: "shadow-color-strong",
    category: "shadow-color",
    displayName: "Shadow Color — Strong",
    description: "Tight grounding shadow — deepest layer in multi-layer compositions.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.18 0.010 255 / 0.16)",
      dark: "oklch(0.03 0.005 255 / 0.50)",
    },
  },
  {
    name: "shadow-highlight-top",
    category: "shadow-color",
    displayName: "Shadow Highlight — Top (legacy alias of edge specular)",
    description:
      "Legacy slot from the brass-era 3px warm band. Chrome/steel replaces it with the 1px --edge-specular; this token now carries the same white-5% value for any residual consumer. Prefer --edge-specular in new work.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "transparent",
      dark: "oklch(1 0 0 / 0.05)",
    },
  },

  // ── Shadow elevation (compositions) ─────────────────────────
  {
    name: "shadow-level-1",
    category: "shadow-elevation",
    displayName: "Shadow Level 1",
    description:
      "Cards, widgets, pinned items. Single-layer in light; dark mode = the §3 machined stack — the --shadow-panel drop + 1px inset --edge-specular.",
    valueType: "shadow-composition",
    defaults: {
      light: "0 2px 8px var(--shadow-color-base)",
      dark:
        "0 6px 20px var(--shadow-color-base), inset 0 1px 0 var(--edge-specular)",
    },
    derivedFrom: ["shadow-color-base", "edge-specular"],
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
    derivedFrom: ["shadow-color-base", "shadow-color-subtle", "shadow-color-strong", "edge-specular"],
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
    derivedFrom: ["shadow-color-strong", "shadow-color-base", "edge-specular"],
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

  // ── Accent family (chrome — §5) ─────────────────────────────
  {
    name: "accent",
    category: "accent",
    displayName: "Accent — Chrome",
    description:
      "Chrome IS the accent (new-doc name: --accent-chrome). Near-monochrome cool-neutral: bright chrome in dark mode, ink in light mode. State variants ride the LIGHTNESS axis — a near-white accent cannot signal state via chroma. At most ONE chrome-filled primary per view.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.25 0.010 255)",
      dark: "oklch(0.93 0.004 255)",
    },
  },
  {
    name: "accent-hover",
    category: "accent",
    displayName: "Accent — Hover (lighter)",
    description:
      "Hover state on the lightness axis — LIGHTER than rest in both modes.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.32 0.010 255)",
      dark: "oklch(0.97 0.004 255)",
    },
  },
  {
    name: "accent-active",
    category: "accent",
    displayName: "Accent — Active (dimmer)",
    description:
      "Momentary press state on the lightness axis — slightly DIMMER than rest in both modes. New in the chrome/steel pivot (the brass era deliberately omitted it).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.20 0.010 255)",
      dark: "oklch(0.88 0.005 255)",
    },
  },
  {
    name: "accent-disabled",
    category: "accent",
    displayName: "Accent — Disabled (low-contrast neutral)",
    description:
      "Disabled chrome fill — lower-contrast neutral, still on the lightness axis.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.72 0.006 255)",
      dark: "oklch(0.45 0.006 255)",
    },
  },
  {
    name: "accent-muted",
    category: "accent",
    displayName: "Accent — Muted",
    description:
      "Alpha accent wash — count badges, secondary chips. Re-derived for the near-monochrome accent: ink wash in light mode, chrome (faint white) wash in dark.",
    valueType: "rgba",
    defaults: {
      light: "rgba(38, 41, 48, 0.12)",
      dark: "rgba(235, 237, 242, 0.16)",
    },
  },
  {
    name: "accent-subtle",
    category: "accent",
    displayName: "Accent — Subtle",
    description:
      "Faint alpha accent wash — selected items, hover backgrounds. Re-derived like accent-muted.",
    valueType: "rgba",
    defaults: {
      light: "rgba(38, 41, 48, 0.06)",
      dark: "rgba(235, 237, 242, 0.08)",
    },
  },
  {
    name: "accent-confirmed",
    category: "accent",
    subcategory: "confirmed",
    displayName: "Accent — Confirmed",
    description: "Sage-green confirmed state (a green — functional-lawful; unchanged in the chrome/steel pivot).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.58 0.05 138)",
      dark: "oklch(0.58 0.05 138)",
    },
  },

  // ── Signature family (§6 — NEW ROLE in the chrome/steel pivot) ──
  {
    name: "signature-steel",
    category: "signature",
    displayName: "Signature — Steel",
    description:
      "The rationed signature tone — the ONLY blue on screen. Allowed ONLY in: focus/selection ring, link text, one row-hover accent, and the logo mark's inner detail. Never a button fill, never a large surface. If it appears more than ~3 times on a screen, it's misused. Rationing is a convention, not enforced in code — this dedicated slot exists so uses stay auditable.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.52 0.09 255)",
      dark: "oklch(0.62 0.08 255)",
    },
  },
  {
    name: "signature-steel-ring",
    category: "signature",
    displayName: "Signature — Steel Ring",
    description:
      "Focus/selection ring flavor of the signature (§6: steel at 50% alpha). The .focus-ring-accent utility composes --signature-steel with --focus-ring-alpha; this token serves consumers that want the pre-composed value.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(0.52 0.09 255 / 0.5)",
      dark: "oklch(0.62 0.08 255 / 0.5)",
    },
    derivedFrom: ["signature-steel"],
  },

  // ── Nav active (§5) ─────────────────────────────────────────
  {
    name: "nav-active-indicator",
    category: "signature",
    subcategory: "nav",
    displayName: "Nav — Active Indicator",
    description:
      "2px left border on the active nav item (§5). References the chrome accent — edit --accent instead.",
    valueType: "oklch",
    defaults: {
      light: "var(--accent)",
      dark: "var(--accent)",
    },
    derivedFrom: ["accent"],
    editable: false,
  },
  {
    name: "nav-active-text",
    category: "signature",
    subcategory: "nav",
    displayName: "Nav — Active Text",
    description: "Active nav item label color (§5).",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.28 0.008 255)",
      dark: "oklch(0.82 0.005 255)",
    },
  },

  // ── Edge specular (§3) ──────────────────────────────────────
  {
    name: "edge-specular",
    category: "shadow-color",
    displayName: "Edge Specular",
    description:
      "1px inset top-edge highlight on every panel (§3: white @ 5% in dark mode) — the machined catch-light. Composed into --shadow-level-1/2/3; near-invisible on light-mode near-white panels by nature.",
    valueType: "oklch-with-alpha",
    defaults: {
      light: "oklch(1 0 0 / 0.65)",
      dark: "oklch(1 0 0 / 0.05)",
    },
  },

  // ── Panel gradients (§3) ────────────────────────────────────
  {
    name: "panel-gradient",
    category: "shadow-special",
    displayName: "Panel Gradient",
    description:
      "The §3 barely-there vertical gradient (surface-2 toward surface-1 at the bottom). Consumed by the card family via [background-image:var(--panel-gradient)] — flat fills are banned for panels. Edit the surface tokens instead.",
    valueType: "shadow-composition",
    defaults: { light: "(composition)", dark: "(composition)" },
    derivedFrom: ["surface-elevated", "surface-sunken"],
    editable: false,
  },
  {
    name: "panel-gradient-raised",
    category: "shadow-special",
    displayName: "Panel Gradient — Raised",
    description:
      "Raised/popover flavor of the panel gradient (surface-3 toward surface-2). Consumed by the overlay family. Edit the surface tokens instead.",
    valueType: "shadow-composition",
    defaults: { light: "(composition)", dark: "(composition)" },
    derivedFrom: ["surface-raised", "surface-elevated"],
    editable: false,
  },

  // ── Status family (functional color — §7) ───────────────────
  {
    name: "status-error",
    category: "status",
    subcategory: "error",
    displayName: "Status — Error (fn-negative)",
    description:
      "Overdue / danger / attention (§7 --fn-negative). Terracotta hue 40 — the cool-era descendant of the old warm thread.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.52 0.11 40)",
      dark: "oklch(0.70 0.09 40)",
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
      light: "oklch(0.94 0.03 40)",
      dark: "oklch(0.26 0.04 40)",
    },
  },
  {
    name: "status-warning",
    category: "status",
    subcategory: "warning",
    displayName: "Status — Warning (fn-caution)",
    description: "§7 --fn-caution — use sparingly.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.60 0.11 78)",
      dark: "oklch(0.80 0.10 78)",
    },
  },
  {
    name: "status-warning-muted",
    category: "status",
    subcategory: "warning",
    displayName: "Status — Warning Muted",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.95 0.04 78)",
      dark: "oklch(0.27 0.05 78)",
    },
  },
  {
    name: "status-success",
    category: "status",
    subcategory: "success",
    displayName: "Status — Success (fn-positive)",
    description:
      "Positive / ready / up (§7 --fn-positive). True leaf-green (hue 155) so it never blurs with steel.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.55 0.12 155)",
      dark: "oklch(0.74 0.11 155)",
    },
  },
  {
    name: "status-success-muted",
    category: "status",
    subcategory: "success",
    displayName: "Status — Success Muted",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.94 0.04 155)",
      dark: "oklch(0.25 0.05 155)",
    },
  },
  {
    name: "status-info",
    category: "status",
    subcategory: "info",
    displayName: "Status — Info (DEMOTED to neutral chrome)",
    description:
      "Info is 'note this,' not an alarm — demoted to a hue-free neutral in the chrome/steel pivot so steel stays the ONLY blue on screen.",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.45 0.008 255)",
      dark: "oklch(0.78 0.006 255)",
    },
  },
  {
    name: "status-info-muted",
    category: "status",
    subcategory: "info",
    displayName: "Status — Info Muted (neutral)",
    valueType: "oklch",
    defaults: {
      light: "oklch(0.94 0.004 255)",
      dark: "oklch(0.26 0.006 255)",
    },
  },

  // ── Focus ring ──────────────────────────────────────────────
  {
    name: "focus-ring-alpha",
    category: "focus-ring",
    displayName: "Focus Ring Alpha",
    description:
      "Focus ring opacity. The .focus-ring-accent utility composes --signature-steel at this alpha (§6 ring ships at /0.5 in dark mode).",
    valueType: "alpha",
    defaults: { light: "0.45", dark: "0.50" },
    bounds: [0, 1],
  },

  // ── Typography family ───────────────────────────────────────
  {
    name: "font-fraunces",
    category: "typography-family",
    displayName: "Font — Display slot (system sans; serif retired)",
    description:
      "§8: single-family UI. The display-serif role is retired from the UI — this slot now resolves to the SF system stack so the 21 font-display call sites render sans without churn. Memorial documents keep their serif via the backend document-emission arc (Fraunces assets retained, unbundled).",
    valueType: "font-family",
    defaults: {
      light:
        '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", system-ui, sans-serif',
      dark:
        '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", system-ui, sans-serif',
    },
  },
  {
    name: "font-geist",
    category: "typography-family",
    displayName: "Font — UI Sans (SF system stack)",
    description:
      "§8: SF renders natively on Apple hardware; Inter is the licensed fallback for Windows/Android. NO bundled webfont. Weights 400/500 only. Slot name kept from the Geist era to avoid churning the --font-sans alias chain.",
    valueType: "font-family",
    defaults: {
      light:
        '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", system-ui, sans-serif',
      dark:
        '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", system-ui, sans-serif',
    },
  },
  {
    name: "font-geist-mono",
    category: "typography-family",
    displayName: "Font — Mono (system stack)",
    description:
      "Monospace for IDs, timestamps, code, count badges. System stack (SF Mono on Apple hardware); data numerics use tabular-nums per §8.",
    valueType: "font-family",
    defaults: {
      light:
        'ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace',
      dark:
        'ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace',
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
    // R-5.0 — edge panel handle + open panel sit at 96 (above editor
    // chrome at 91-95 but below Focus at 100).
    name: "z-edge-panel",
    category: "z-index",
    displayName: "Z — Edge panel",
    valueType: "integer",
    defaults: { light: "96", dark: "96" },
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
    "signature",
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
    signature: "Signature (steel — rationed)",
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
