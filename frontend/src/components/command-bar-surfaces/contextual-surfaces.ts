/**
 * S-2 (§4.3) CONTEXTUAL_SURFACES — the summon map (ruled decision 5).
 *
 * Keyed on the committed in-flight INTENT STRING (entry_intent:"quote"
 * for this slice). The map is PRODUCER-AGNOSTIC: it keys on the string,
 * not on who computed it. Today the key comes from the overlay's
 * detect_entry_intent; S-4's interpretation chip can supply the same
 * key later for the bare-command-bar case — this map never changes.
 *
 * configFrom is a PURE derivation of widget config from the lifted
 * ExtractionContext; returning null SUPPRESSES the surface (no empty
 * shell). The host renders whatever descriptors this yields, dispatching
 * each via getWidgetRenderer — it knows nothing about quotes.
 */

import type {
  ContextualSurfaceDecl,
  ExtractionContext,
  SurfaceDescriptor,
} from "./types"

export const CONTEXTUAL_SURFACES: Record<string, ContextualSurfaceDecl[]> = {
  quote: [
    {
      kind: "quote_preview",
      widgetId: "surface.quote-preview",
      // Materializes once the user has committed at least a customer or
      // a product, then fills in as more fields resolve. Suppressed on a
      // wholly-empty draft so nothing flashes before there's content.
      configFrom: (ctx: ExtractionContext) =>
        ctx.customer || ctx.lines.length > 0
          ? { customer: ctx.customer, lines: ctx.lines }
          : null,
    },
    {
      kind: "price_list_reference",
      widgetId: "surface.price-list-reference",
      // Suppressed until a product resolves — no empty reference card.
      configFrom: (ctx: ExtractionContext) =>
        ctx.lines.length > 0
          ? {
              products: ctx.lines.map((l) => l.productRef),
              customerId: ctx.customer?.id ?? null,
            }
          : null,
    },
  ],
}

/** Resolve the ordered surface descriptors for a committed intent +
 *  the current extraction. Suppressed (configFrom null) surfaces are
 *  omitted. Brief variant is the command-bar default. */
export function surfacesForIntent(
  intent: string,
  ctx: ExtractionContext,
): SurfaceDescriptor[] {
  const decls = CONTEXTUAL_SURFACES[intent] ?? []
  const out: SurfaceDescriptor[] = []
  for (const decl of decls) {
    const config = decl.configFrom(ctx)
    if (config === null) continue // suppressed
    out.push({
      key: decl.kind,
      widgetId: decl.widgetId,
      variantId: "brief",
      config,
    })
  }
  return out
}
