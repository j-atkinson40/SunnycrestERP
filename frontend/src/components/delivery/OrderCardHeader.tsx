/**
 * R-2.1 — OrderCardHeader sub-component.
 *
 * "Who is this case" identity block — funeral home name + deceased
 * "RE:" line. Extracted from OrderCard.tsx (lines 87-99 pre-R-2.1).
 *
 * R-2.1 ADDS data-slot markers to OrderCard's regions — pre-R-2.1
 * OrderCard had zero data-slot attributes (DeliveryCard + AncillaryCard
 * had them already). The new markers parallel the dispatch family's
 * conventions: `order-card-fh` + `order-card-deceased`.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */


export interface OrderCardHeaderProps {
  /** Funeral home name. Empty / missing = line not rendered. */
  funeralHomeName: string | null
  /** Deceased name. Empty / null = line not rendered. */
  deceasedName: string | null
  /** Whether the parent's KanbanConfig has card_show_funeral_home enabled. */
  showFuneralHome: boolean
}


/** R-2.1 — exported as `OrderCardHeaderRaw`. */
export function OrderCardHeaderRaw({
  funeralHomeName,
  deceasedName,
  showFuneralHome,
}: OrderCardHeaderProps) {
  return (
    <>
      {/* Funeral home name */}
      {showFuneralHome && funeralHomeName && (
        <div
          className="text-sm font-semibold text-content-strong leading-tight"
          data-slot="order-card-fh"
        >
          {funeralHomeName}
        </div>
      )}

      {/* Deceased name */}
      {deceasedName && (
        <div
          className="text-xs text-content-muted mt-0.5"
          data-slot="order-card-deceased"
        >
          RE: {deceasedName}
        </div>
      )}
    </>
  )
}
