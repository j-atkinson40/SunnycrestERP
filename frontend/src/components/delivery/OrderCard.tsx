/**
 * OrderCard — individual delivery card (Draggable) for the Scheduling
 * Board's KanbanPanel.
 *
 * R-2.0 — extracted from `kanban-panel.tsx` so that the canonical
 * runtime-editor entity-card registration pattern can wrap it at a
 * single import site (mirrors DeliveryCard / AncillaryCard's
 * standalone-file shape). Pre-R-2.0 OrderCard was a nested function
 * declaration inside kanban-panel.tsx; nesting blocked Path 1 wrapping
 * because the registration shim couldn't import a non-exported function.
 *
 * The component itself is unchanged from the kanban-panel.tsx version;
 * only its location moved. Render contract preserved: same props, same
 * Draggable wrapper, same icon dispatch on service_location, same
 * accent-pulse on critical/warning windows.
 *
 * **Import discipline**: per R-2.0's ESLint rule, every consumer site
 * should import OrderCard from
 * `@/lib/visual-editor/registry/registrations/entity-cards` (the
 * wrapped version that carries `data-component-name` for runtime-editor
 * click-to-edit). Importing `OrderCardRaw` directly bypasses the
 * runtime registration and breaks the editor's click-to-select gesture
 * on this card.
 */

import { Draggable } from "@hello-pangea/dnd"

import { cn } from "@/lib/utils"
import type { KanbanCard, KanbanConfig } from "@/types/delivery"

// R-2.1 — sub-section wrapped components imported from the registrations
// barrel. Each emits a data-component-name boundary div for click-to-
// edit resolution. R-2.1 ALSO adds data-slot markers to OrderCard's
// regions (pre-R-2.1 OrderCard had none — DeliveryCard + AncillaryCard
// had them already).
import {
  OrderCardHeader,
  OrderCardBody,
  OrderCardActions,
} from "@/lib/visual-editor/registry/registrations/entity-card-sections"


export interface OrderCardProps {
  card: KanbanCard
  config: KanbanConfig
  index: number
  panelPrefix: string
}


function cemeteryWithLocation(card: KanbanCard): string {
  const name = card.cemetery_name || "TBD"
  const city = card.cemetery_city
  const state = card.cemetery_state
  const county = card.cemetery_county
  let loc = ""
  if (city && state) loc = `${city}, ${state}`
  else if (city) loc = city
  else if (county && state) loc = `${county}, ${state}`
  else if (state) loc = state
  return loc ? `${name} · ${loc}` : name
}


/** R-2.0 — exported as `OrderCardRaw`; the wrapped version (carrying
 *  `data-component-name="order-card"` for runtime-editor click-to-edit)
 *  is the default export from
 *  `@/lib/visual-editor/registry/registrations/entity-cards`. The raw
 *  reference stays exported so the registration shim can wrap it; new
 *  call sites should import the wrapped version, not this one. */
export function OrderCardRaw({
  card,
  config,
  index,
  panelPrefix,
}: OrderCardProps) {
  return (
    <Draggable
      draggableId={`${panelPrefix}-${card.delivery_id}`}
      index={index}
    >
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          data-slot="order-card"
          className={cn(
            "rounded-lg border bg-surface-elevated p-3 shadow-sm transition-shadow",
            snapshot.isDragging && "shadow-lg ring-2 ring-accent",
            card.is_critical && "border-status-error bg-status-error-muted",
            card.is_warning &&
              !card.is_critical &&
              "border-status-warning bg-status-warning-muted",
          )}
        >
          {/* R-2.1 — header sub-section (FH name + deceased "RE:"). */}
          <OrderCardHeader
            funeralHomeName={card.funeral_home_name ?? null}
            deceasedName={card.deceased_name ?? null}
            showFuneralHome={config.card_show_funeral_home}
          />

          {/* R-2.1 — body sub-section (vault/equipment + service block). */}
          <OrderCardBody card={card} cemeteryWithLocation={cemeteryWithLocation} />

          {/* R-2.1 — actions sub-section (countdown + notes + optional
              R-4 button row). Self-collapses when nothing to show. */}
          <OrderCardActions card={card} />
        </div>
      )}
    </Draggable>
  )
}
