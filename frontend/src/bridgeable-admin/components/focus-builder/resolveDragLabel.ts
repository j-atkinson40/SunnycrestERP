/**
 * resolveDragLabel — pure helper for FocusBuilderPage's DragOverlay
 * label resolution.
 *
 * The DragOverlay child renders the resolved label as visible text.
 * Before this helper, `handleDragStart` used a `slug ?? id` fallback
 * that leaked raw drag ids (placement UUIDs, `<uuid>-handle-<position>`
 * strings) as visible text adjacent to the cursor during in-canvas
 * manipulation drags.
 *
 * Per the 2026-05-20 read-only investigation
 * (docs/investigations/2026-05-20-resize-handle-ux-refinements.md
 * Finding 2), the canonical fix is a dedicated resolver that knows
 * about all drag-id shapes:
 *
 *   - `palette-widget:<slug>`  → returns `<slug>` (palette drag from
 *                                 the left rail; the overlay's floating
 *                                 label is genuinely useful here because
 *                                 the source palette icon is far from
 *                                 the cursor's drop position)
 *   - any other id shape       → returns null (whole-widget drag and
 *                                 resize-handle drag both move the
 *                                 widget itself under the cursor, so a
 *                                 floating label adjacent to the cursor
 *                                 adds no operational information and
 *                                 just leaks internal id strings)
 *
 * Future drag id shapes default to null (no UUID leak by accident).
 * To add a new human-readable label for a future drag-id shape, extend
 * this resolver with an additional prefix check; do NOT extend
 * `paletteItemIdToSlug` (which is specifically about palette ids and
 * has its own test contract).
 *
 * This helper does NOT call into `paletteItemIdToSlug` — both are
 * thin prefix-strip operations on the canonical
 * `palette-widget:` prefix; encapsulating the check here keeps the
 * helper self-contained (no cross-file dependency on the Palette
 * component module).
 */

/**
 * Palette-widget id prefix. Mirrors `PALETTE_ITEM_PREFIX` in
 * FocusBuilderPalette.tsx (kept in lockstep — both files own a copy
 * of the canonical prefix string). If either drifts, palette drag
 * label resolution breaks.
 */
const PALETTE_WIDGET_PREFIX = "palette-widget:"

export function resolveDragLabel(id: string): string | null {
  if (id.startsWith(PALETTE_WIDGET_PREFIX)) {
    return id.slice(PALETTE_WIDGET_PREFIX.length)
  }
  return null
}
