/**
 * S-2 (§4.3) contextual-surfaces contract types.
 *
 * The ratified addendum shapes (docs/investigations/
 * 2026-07-24-s2-contextual-surfaces.md): the ExtractionContext lifted
 * out of NaturalLanguageOverlay, the SurfaceDescriptor the generalized
 * host renders, and the ContextualSurfaceDecl the CONTEXTUAL_SURFACES
 * map is built from.
 */

import type { VariantId } from "@/components/widgets/types"

/** One in-flight quote line, normalized from the overlay's FieldMap.
 *  productRef is a NAME string — the NL extract does not resolve
 *  products to rows; the backend resolves it. */
export interface QuoteDraftLine {
  productRef: string
  productId?: string
  quantity: number
}

/** The normalized read of the overlay's in-flight extraction. Lifted
 *  via onExtraction (ruled decision 1 — a callback, NOT a duplicate
 *  /extract call, NOT a migration off the workflow overlay). */
export interface ExtractionContext {
  entryIntent: "order" | "quote"
  customer: { id?: string; name: string } | null
  lines: QuoteDraftLine[]
  /** Raw overlay text — best-effort rhythm context for the trigger seam. */
  rawInput: string
}

/** What the generalized CommandBarSurfaceHost renders. Host-agnostic:
 *  the host dispatches widgetId via getWidgetRenderer and passes config
 *  through — it knows nothing about what the surface is. */
export interface SurfaceDescriptor {
  /** Stable key for React + the widget's telemetry id. */
  key: string
  /** Registry id resolved via getWidgetRenderer. */
  widgetId: string
  variantId?: VariantId
  config?: Record<string, unknown>
}

/** A declaration in the CONTEXTUAL_SURFACES map. configFrom is a PURE
 *  derivation of the widget config from the lifted context; returning
 *  null SUPPRESSES the surface (e.g. price-list reference before any
 *  product resolves — no empty shell). */
export interface ContextualSurfaceDecl {
  kind: string
  widgetId: string
  configFrom: (ctx: ExtractionContext) => Record<string, unknown> | null
}

// ── Trigger seam (ruled decision 6) ──────────────────────────────────

/** WHY the trigger fired + typing-rhythm context — so S-4 has something
 *  to refine. v1 emits reason:"extraction_settled" with best-effort
 *  rhythm; S-4's pause sensor swaps the impl to emit reason:"pause"
 *  with a real adaptive threshold, SAME shape. */
export interface SurfaceTriggerSignal {
  reason: "extraction_settled" | "pause" | "manual"
  msSinceLastKeystroke: number | null
  cursorMoved: boolean
  inputText: string
}

export interface ContextualSurfaceTrigger {
  /** Host reads this: should surfaces show now? */
  active: boolean
  signal: SurfaceTriggerSignal | null
  /** Resume-typing / action-complete clears it (S-4 primary caller). */
  dismiss: () => void
}
