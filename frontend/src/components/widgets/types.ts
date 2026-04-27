// Widget framework types — shared across all dashboard pages.
//
// Phase W-1 of the Widget Library Architecture (DESIGN_LANGUAGE.md
// Section 12) extends this file with the unified contract:
//   • Vertical — 4 industry-preset enum values
//   • WidgetSurface — 7 surface enum values per Section 12.5
//   • VariantId / VariantDensity — Section 12.2 4-tier taxonomy
//   • WidgetVariant — per-variant size + surface declaration
//   • WidgetVariantProps — runtime props every widget component
//     receives (replaces loose WidgetProps for new builds)
//   • Extended WidgetDefinition — adds variants + required_vertical
//     + supported_surfaces + default_surfaces + intelligence_keywords
//
// Backwards compatibility: existing dashboard widgets continue
// consuming `WidgetProps` (loose `[key: string]: unknown`) per
// Decision 10 (both frameworks coexist 1-2 release windows). New
// widgets land on `WidgetVariantProps`. Migration is "as touched."

import type { ComponentType } from "react"


// ─── Vertical enum (4-axis filter axis 4) ────────────────────────────

/** Tenant vertical preset. Per CLAUDE.md §1, 4 canonical values.
 * Maps to backend `Company.vertical` field. */
export type Vertical =
  | "manufacturing"
  | "funeral_home"
  | "cemetery"
  | "crematory"


// ─── Surface enum (Section 12.5 composition rules) ───────────────────

/** Where a widget can render. Surface discriminator on
 * WidgetVariantProps lets one component adapt internal layout
 * across surfaces. Section 12.5 documents per-surface composition
 * rules. */
export type WidgetSurface =
  | "pulse_grid"        // Pulse responsive grid (per-Space)
  | "focus_canvas"      // Focus free-form canvas (anchor-positioned)
  | "focus_stack"       // Focus stack rail (mobile tier)
  | "spaces_pin"        // Spaces sidebar pin (Glance-only)
  | "floating_tablet"   // Command bar floating tablet (peek content)
  | "dashboard_grid"    // Operations Board / Vault Overview / hub dashboards
  | "peek_inline"       // Peek panel content composition (no chrome)


// ─── Variant taxonomy (Section 12.2) ─────────────────────────────────

/** Canonical variant ids per Section 12.2 — 4 named density tiers.
 * Glance / Brief / Detail / Deep map to user mental model
 * ("give me a brief on...") and forward-compatible across form
 * factors (Glance = future Watch tier, Brief = phone, Detail =
 * tablet/desktop, Deep = primary work surface). */
export type VariantId = "glance" | "brief" | "detail" | "deep"

/** Density level per variant (metadata for Intelligence + UI).
 * Maps to VariantId 1:1 but kept distinct for type safety:
 * VariantId is the canonical name; density is the perceived
 * content scope. */
export type VariantDensity = "minimal" | "focused" | "rich" | "deep"

/** Single variant declaration. Section 12.3 shape. */
export interface WidgetVariant {
  variant_id: VariantId
  density: VariantDensity
  /** Grid sizing for fixed-grid surfaces (Pulse, Vault Overview,
   * Operations Board). cols/rows in grid units. */
  grid_size: { cols: number; rows: number }
  /** Canvas sizing for free-form surfaces (Focus). height "auto"
   * means content-driven (Phase A Session 1.5 Widget Compactness
   * canon); maxHeight is the cap. */
  canvas_size: {
    width: number
    height: number | "auto"
    maxHeight?: number
  }
  /** Surface compatibility for this variant (subset of
   * definition.supported_surfaces). Section 12.2 compatibility
   * matrix is enforced via this field. */
  supported_surfaces: WidgetSurface[]
  /** Hard min dimensions — surface refuses to render this variant
   * smaller. Optional; most variants accept content-driven sizing
   * within the variant's intended density tier. */
  min_dimensions?: { width: number; height: number }
  /** Some variants need extra context (e.g., "drag-context",
   * "dnd-kit-context"). Phase W-3 widget builds may declare. */
  required_features?: string[]
}


// ─── Configuration schema (Section 12.3) ─────────────────────────────

/** Per-instance widget configuration shape. Reuses the saved-view
 * config schema pattern (see frontend/src/types/saved-views.ts)
 * for consistency. Phase W-3 widget builds may use richer
 * ConfigSchema<T>; Phase W-1 keeps it simple as
 * `Record<string, unknown>` typed via TConfig.
 *
 * Configuration validation lives in widget definition files
 * (Phase W-3); the type alias below is the contract surface. */
export type WidgetConfigSchema<T = unknown> = {
  // Phase W-3 may extend with full schema validation. Phase W-1
  // keeps the contract simple — TConfig is the per-widget config
  // type, validated by per-widget definitions if they choose.
  shape?: T
}


// ─── Extended WidgetDefinition (Section 12.3) ────────────────────────

/** Widget catalog entry. Mirrors backend `WidgetDefinition` table
 * + `get_available_widgets()` response shape post-Phase-W-1. */
export interface WidgetDefinition<TConfig = unknown> {
  // Identity (existing)
  widget_id: string                    // dot-namespaced, e.g., "scheduling.ancillary-pool"
  title: string
  description: string | null
  icon: string | null
  category: string | null

  // Legacy size fields (kept for one release window per Decision 10)
  default_size: string
  min_size?: string
  max_size?: string
  supported_sizes: string[]
  default_enabled: boolean
  default_position: number

  // Visibility — 4-axis filter (Section 12.4)
  required_extension: string | null
  required_permission?: string | null
  required_vertical: Vertical[] | ["*"]

  // Phase W-1 unified contract (Section 12.3)
  variants: WidgetVariant[]
  default_variant_id: VariantId
  supported_surfaces: WidgetSurface[]
  default_surfaces: WidgetSurface[]
  intelligence_keywords: string[]

  // Per-instance configuration
  config_schema?: WidgetConfigSchema<TConfig>
  default_config?: TConfig

  // Catalog UI flags
  is_available: boolean
  unavailable_reason: string | null
}


// ─── Layout items (existing, lightly extended) ───────────────────────

export interface WidgetLayoutItem {
  widget_id: string
  enabled: boolean
  position: number
  size: string
  config: Record<string, unknown>
  // Phase W-1: per-instance variant selection. Optional during
  // migration window — Phase W-3+ widget builds set explicitly;
  // legacy items default to widget's `default_variant_id`.
  variant_id?: VariantId
  // Enriched from definition
  title?: string
  description?: string | null
  icon?: string | null
  category?: string | null
  supported_sizes?: string[]
  required_extension?: string | null
}

export interface WidgetLayout {
  page_context: string
  widgets: WidgetLayoutItem[]
}


// ─── Component contract ──────────────────────────────────────────────

/** Loose props shape for legacy widgets. New widgets should adopt
 * `WidgetVariantProps<TConfig>` instead. */
export interface WidgetProps {
  onAction?: (action: string, data?: unknown) => void
  // Internal props passed by WidgetGrid — widgets forward to WidgetWrapper
  [key: string]: unknown
}

/** Section 12.3 — canonical widget component contract. Every
 * widget variant component receives this shape. Surfaces inject
 * the props; widgets read them to adapt internal layout per
 * surface + variant.
 *
 * Data ownership flexible per Decision 6: canvas widgets continue
 * using feature contexts (Focus session state); dashboard widgets
 * continue using `useWidgetData` hook; SavedView-backed widgets
 * use `executeSavedView()`. The contract doesn't dictate.
 *
 * Per-variant interaction declarations (Section 12.6a) are
 * convention for Phase W-1 + W-2; Phase W-3 widget builds declare
 * supported interactions in their definition file as
 * documentation-comments. The discipline is enforced by code review
 * + the canonical examples table in Section 12.6a, not by schema. */
export interface WidgetVariantProps<TConfig = unknown> {
  /** Unique instance id (telemetry, drag, persistence). */
  widget_id: string
  /** Resolved per-instance config (default merged with user
   * overrides). */
  config: TConfig
  /** Surface discriminator — widget adapts internal layout per
   * surface. */
  surface: WidgetSurface
  /** Which variant this component is rendering. Internal switch
   * on variant_id keeps each widget's state + data hooks shared
   * across variants per Decision 5. */
  variant_id: VariantId
  /** Computed pixel dimensions for this slot (optional —
   * surfaces inject when available). */
  size_hint?: { width: number; height: number }
  /** Grid surfaces in edit mode. */
  is_edit_mode?: boolean
  /** For stacked / icon-tier widgets, which is currently visible. */
  is_active?: boolean
}


// ─── Component registries ────────────────────────────────────────────

/** Maps widget_id → React component. Used by WidgetGrid +
 * vault-hub-registry. */
export type WidgetComponentMap = Record<string, ComponentType<WidgetProps>>

/** Phase W-1 unified component map — widget components that adopt
 * the new contract receive WidgetVariantProps. Migration window
 * supports both. */
export type WidgetVariantComponentMap = Record<
  string,
  ComponentType<WidgetVariantProps>
>


// ─── Helpers ─────────────────────────────────────────────────────────

/** Parse "NxM" size string into col/row spans. */
export function parseSize(size: string): { cols: number; rows: number } {
  const [c, r] = size.split("x").map(Number)
  return { cols: c || 1, rows: r || 1 }
}

/** Resolve a variant by id from a definition. Phase W-1 utility —
 * widget catalog UI + surfaces look up the variant for a given
 * instance to size + place it correctly. Returns null when
 * variant_id doesn't match a declared variant (catalog UI should
 * fall back to definition.default_variant_id). */
export function findVariant(
  definition: WidgetDefinition,
  variant_id: VariantId,
): WidgetVariant | null {
  return definition.variants.find((v) => v.variant_id === variant_id) ?? null
}

/** Resolve the default variant for a definition. Always returns a
 * variant (definitions invariant: default_variant_id ∈ variants —
 * enforced by backend test in test_widget_library_w1_foundation.py). */
export function defaultVariant(
  definition: WidgetDefinition,
): WidgetVariant {
  const found = findVariant(definition, definition.default_variant_id)
  if (found) return found
  // Defense in depth: if the definition is malformed, return the
  // first variant (test_default_variant_id_references_a_declared_variant
  // catches malformed definitions in CI).
  return definition.variants[0]
}

/** Section 12.4 4-axis filter — predicate for "is this widget
 * available to this user/tenant?" Phase W-1 frontend mirrors the
 * backend filter for defense-in-depth (catalog UI rendering
 * decisions, layout-fetch reconciliation, render-dispatch gating).
 *
 * Backend `get_available_widgets()` is the canonical filter source
 * (it has access to permissions, modules, extensions). Frontend
 * uses this helper for UI-side filtering when the backend response
 * already includes `is_available` — typically just rechecking the
 * vertical axis on ad-hoc client-side filtering needs. */
export function isWidgetAvailableForVertical(
  definition: Pick<WidgetDefinition, "required_vertical">,
  tenantVertical: Vertical | null,
): boolean {
  const rv = definition.required_vertical
  if (!rv || (rv as readonly string[]).includes("*")) return true
  if (!tenantVertical) return false
  return (rv as Vertical[]).includes(tenantVertical)
}
