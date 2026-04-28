/**
 * Pulse piece renderability — Phase W-4a Step 6 Commit 4.
 *
 * Per DESIGN_LANGUAGE.md §13.4.3 agency-dictated error surface:
 *   "Pulse (`pulse_grid`) — composition engine plans the surface.
 *    If a widget can't render, the platform's choice is silently
 *    overridden. The slot disappears from the layout entirely;
 *    layer compacts to remaining items via tetris repacking.
 *    `console.warn(...)` fires for observability."
 *
 * This module supplies the renderability predicate that both
 * PulseSurface (measurement walk) and PulseLayer (rendering) call so
 * the cell-height solver's denominator matches the actually-rendered
 * piece count. Single source of truth for "is this Pulse piece
 * renderable?"
 *
 * Renderability checks:
 *   1. `kind === "stream"` — stream pieces dispatch through a
 *      separate registry path inside PulsePiece; they're always
 *      considered renderable (their own dispatch handles missing
 *      streams via a different path — defensive null-render rather
 *      than a fallback component).
 *   2. `kind === "widget"` — widget pieces dispatch via
 *      `getWidgetRenderer(component_key)`. If the resolved renderer
 *      is `MissingWidgetEmptyState` (registered-but-unknown widget_id
 *      per Step 5 split) OR `MockSavedViewWidget` (legacy/test
 *      fallback), the piece is NOT renderable in Pulse — silently
 *      filtered.
 *
 * The two fallback components are imported by reference comparison
 * — `getWidgetRenderer` returns the SAME component instance for the
 * fallback path, so identity comparison is safe + zero-cost.
 *
 * console.warn does NOT fire from this module — that's the
 * PulseLayer rendering site's responsibility per canon (so warns
 * fire once per render at the right granularity, debounced per
 * `${layer.layer}:${component_key}` key).
 */

import type { LayerItem } from "@/types/pulse"
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers"
import { MissingWidgetEmptyState } from "@/components/focus/canvas/MissingWidgetEmptyState"
import { MockSavedViewWidget } from "@/components/focus/canvas/MockSavedViewWidget"


/** Pulse piece is renderable when:
 *  - It's a stream piece (separate dispatch path), OR
 *  - It's a widget piece whose `component_key` resolves to a
 *    real registered renderer (not the canon-defined fallbacks).
 */
export function isItemRenderable(item: LayerItem): boolean {
  if (item.kind === "stream") return true
  // kind === "widget" — check renderer resolution.
  const renderer = getWidgetRenderer(item.component_key)
  return (
    renderer !== MissingWidgetEmptyState &&
    renderer !== MockSavedViewWidget
  )
}


/** Test-only export. Exposes the same renderability check parametric
 *  over the renderer-resolver function so tests can substitute a
 *  fixture renderer without registering against the production
 *  registry. Production code uses `isItemRenderable` exclusively. */
export const __renderability_internals = {
  isItemRenderableParametric(
    item: LayerItem,
    getRenderer: typeof getWidgetRenderer,
    fallbackComponents: Set<unknown>,
  ): boolean {
    if (item.kind === "stream") return true
    const renderer = getRenderer(item.component_key)
    return !fallbackComponents.has(renderer)
  },
}
