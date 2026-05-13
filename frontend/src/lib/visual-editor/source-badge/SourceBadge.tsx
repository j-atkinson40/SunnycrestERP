/**
 * Arc 4d — SourceBadge canonical primitive.
 *
 * Tenth shared authoring component primitive. Promoted from inline
 * declaration at `bridgeable-admin/components/visual-editor/
 * CompactPropControl.tsx:50-69` to a canonical shared module per
 * 3-way pattern drift closure (ThemeTab inline + per-tab implementations
 * + new canonical primitive → single SourceBadge with variant interface).
 *
 * Two canonical variants for genuinely-asymmetric substrate (Q-ARC4D-1
 * settled):
 *   - "letter": single-char circle (D/C/P/V/T/•) — Class/Props inspector
 *     tabs (Class A per-field source metadata).
 *   - "chip":   full-word pill (Default/Class default/Platform/Vertical
 *     /Tenant/Draft) — Workflows/Documents/FocusCompositions inspector
 *     tabs (Class B per-instance source metadata).
 *
 * **Substrate asymmetry is canonical, not flattened.** Sixth audit-count
 * recalibration shape: audit-frames-as-uniform-where-substrate-is-
 * architecturally-distinct. Runtime substrate is genuinely asymmetric;
 * Class A's per-field source-vs-default distinction warrants single-letter
 * density; Class B's per-instance scope tier warrants stronger word-pill
 * presence. Substrate flattening would be anti-pattern; unification
 * belongs at primitive interface layer (this variant prop).
 *
 * Both variants accent (terracotta) when source ≠ default. Optional
 * `onHoverReveal` callback fires when the user hovers (consumed by
 * ScopeDiffPopover wrapper for hover-reveal scope diff UX).
 */
import type { JSX } from "react"


/**
 * Canonical six-value source vocabulary.
 *
 * - `default`         — registration default (no override anywhere)
 * - `class-default`   — inherited from ComponentClass-level config
 * - `platform`        — platform_default scope (canonical baseline)
 * - `vertical`        — vertical_default scope (per-vertical override)
 * - `tenant`          — tenant_override scope (per-tenant override)
 * - `draft`           — unsaved operator edit
 */
export type SourceValue =
  | "default"
  | "class-default"
  | "platform"
  | "vertical"
  | "tenant"
  | "draft"


export type SourceBadgeVariant = "letter" | "chip"


export interface SourceBadgeProps {
  /** Canonical source value — drives letter, full label, and accent state. */
  source: SourceValue
  /**
   * Letter variant = single-char circle (Class/Props tabs);
   * chip variant = full-word pill (Workflows/Documents/Focus tabs).
   * Choose per substrate cardinality (Class A per-field vs Class B
   * per-instance) — see module docstring.
   */
  variant: SourceBadgeVariant
  /**
   * Optional hover callback. Consumed by ScopeDiffPopover wrapper
   * to trigger the up-the-chain diff reveal.
   */
  onHoverReveal?: () => void
  /** Optional test-id override; defaults to `source-badge-{variant}-{source}`. */
  "data-testid"?: string
}


/**
 * Single-letter sigil for the letter variant. Lookup is canonical
 * because the per-tab consumers (Class/Props) historically used
 * exactly these letters at CompactPropControl.tsx pre-Arc-4d.
 */
const LETTER_BY_SOURCE: Record<SourceValue, string> = {
  default: "D",
  "class-default": "C",
  platform: "P",
  vertical: "V",
  tenant: "T",
  draft: "•",
}


/**
 * Full-word label for both variants:
 *   - letter variant: shown as title (hover tooltip)
 *   - chip variant: shown as visible label
 */
const LABEL_BY_SOURCE: Record<SourceValue, string> = {
  default: "Default",
  "class-default": "Class default",
  platform: "Platform",
  vertical: "Vertical",
  tenant: "Tenant",
  draft: "Draft",
}


/**
 * Sources that visually accent (terracotta) because they represent an
 * override above the default baseline. Default + class-default are
 * baseline; platform/vertical/tenant/draft are overrides.
 *
 * NOTE: class-default visually accents subtly (muted) — it IS an
 * override at the substrate level, but not operator-authored. The
 * letter-variant pre-Arc-4d treatment used text-content-muted for
 * class-default; we preserve that.
 */
const SOURCE_IS_ACCENTED: Record<SourceValue, boolean> = {
  default: false,
  "class-default": false,
  platform: false,
  vertical: false,
  tenant: true, // tenant override = operator-authored = accent
  draft: true, // unsaved edit = visual call-out
}


export function SourceBadge({
  source,
  variant,
  onHoverReveal,
  "data-testid": testId,
}: SourceBadgeProps): JSX.Element {
  const letter = LETTER_BY_SOURCE[source]
  const label = LABEL_BY_SOURCE[source]
  const isAccented = SOURCE_IS_ACCENTED[source]
  const defaultTestId = `source-badge-${variant}-${source}`
  const dataTestId = testId ?? defaultTestId

  if (variant === "letter") {
    // Single-char circle — preserves pre-Arc-4d CompactPropControl.tsx
    // visual contract verbatim. Tone variation per source matches the
    // historical pre-promotion implementation.
    const tone =
      source === "draft"
        ? "text-status-warning"
        : source === "tenant"
        ? "text-accent"
        : source === "default"
        ? "text-content-subtle"
        : "text-content-muted"

    return (
      <span
        className={`inline-flex h-4 w-4 items-center justify-center rounded-full bg-surface-sunken text-[9px] font-medium ${tone}`}
        title={label}
        data-testid={dataTestId}
        data-source={source}
        data-variant="letter"
        data-accented={isAccented ? "true" : "false"}
        onMouseEnter={onHoverReveal}
      >
        {letter}
      </span>
    )
  }

  // Chip variant — full-word pill. Used by Workflows/Documents/Focus
  // inspector tabs at the per-instance scope tier display. Stronger
  // visual presence than letter variant because the substrate
  // exposes scope per-instance rather than per-field.
  const chipChrome = isAccented
    ? "bg-accent-subtle border-accent text-accent"
    : source === "draft"
    ? "bg-status-warning-muted border-status-warning text-status-warning"
    : source === "default"
    ? "bg-surface-sunken border-border-subtle text-content-subtle"
    : "bg-surface-elevated border-border-subtle text-content-muted"

  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-[10px] font-medium leading-tight ${chipChrome}`}
      title={label}
      data-testid={dataTestId}
      data-source={source}
      data-variant="chip"
      data-accented={isAccented ? "true" : "false"}
      onMouseEnter={onHoverReveal}
    >
      {label}
    </span>
  )
}
