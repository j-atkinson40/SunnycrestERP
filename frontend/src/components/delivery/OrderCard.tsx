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
import { Box, Church, Landmark, MapPin } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { KanbanCard, KanbanConfig } from "@/types/delivery"


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
          className={cn(
            "rounded-lg border bg-surface-elevated p-3 shadow-sm transition-shadow",
            snapshot.isDragging && "shadow-lg ring-2 ring-accent",
            card.is_critical && "border-status-error bg-status-error-muted",
            card.is_warning &&
              !card.is_critical &&
              "border-status-warning bg-status-warning-muted",
          )}
        >
          {/* Funeral home name */}
          {config.card_show_funeral_home && card.funeral_home_name && (
            <div className="text-sm font-semibold text-content-strong leading-tight">
              {card.funeral_home_name}
            </div>
          )}

          {/* Deceased name */}
          {card.deceased_name && (
            <div className="text-xs text-content-muted mt-0.5">
              RE: {card.deceased_name}
            </div>
          )}

          {/* Vault · Equipment */}
          {(card.vault_type || card.equipment_summary) && (
            <div className="mt-1.5 text-xs text-content-base">
              {[card.vault_type, card.equipment_summary]
                .filter(Boolean)
                .join(" · ")}
              {card.vault_personalization && (
                <Badge
                  variant="secondary"
                  className="ml-1 text-[10px] px-1 py-0"
                >
                  Custom
                </Badge>
              )}
            </div>
          )}

          {/* Service location → Cemetery + times */}
          <div className="mt-1.5 text-xs text-content-muted space-y-0.5">
            {/* Location line */}
            {(card.service_location || card.cemetery_name) && (
              <div className="flex items-center gap-1">
                <span
                  className="text-content-subtle"
                  aria-label={
                    card.service_location === "church"
                      ? "Church"
                      : card.service_location === "funeral_home"
                        ? "Funeral home"
                        : card.service_location === "graveside"
                          ? "Graveside"
                          : "Location"
                  }
                >
                  {card.service_location === "church" ? (
                    <Church className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : card.service_location === "funeral_home" ? (
                    <Landmark className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : card.service_location === "graveside" ? (
                    <Box className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : (
                    <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                </span>
                {card.service_location === "graveside" ? (
                  <span>Graveside · {cemeteryWithLocation(card)}</span>
                ) : (
                  <span>
                    {card.service_location === "church"
                      ? "Church"
                      : card.service_location === "funeral_home"
                        ? "Funeral Home"
                        : card.service_location_other || "Service"}
                    {card.cemetery_name
                      ? ` → ${cemeteryWithLocation(card)}`
                      : ""}
                  </span>
                )}
              </div>
            )}
            {!card.service_location && card.cemetery_name && (
              <div className="truncate">{cemeteryWithLocation(card)}</div>
            )}

            {/* Time line */}
            {card.service_location === "graveside" ? (
              card.service_time_display ? (
                <div className="font-medium">{card.service_time_display}</div>
              ) : (
                <div className="text-status-warning">Time TBD</div>
              )
            ) : card.service_time_display ? (
              <div>
                Service: {card.service_time_display}
                {card.eta_display ? (
                  <span className="font-medium ml-2">
                    ETA: {card.eta_display}
                  </span>
                ) : (
                  <span className="text-status-warning ml-2">ETA: TBD</span>
                )}
              </div>
            ) : (
              <div className="text-status-warning">Time TBD</div>
            )}
          </div>

          {/* Hours countdown — critical pulses with error-family,
              warning is warning-family, otherwise subtle outline. */}
          {card.hours_until_service !== null &&
            card.hours_until_service > 0 && (
              <div className="mt-1.5">
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px]",
                    card.is_critical
                      ? "border-status-error text-status-error animate-pulse"
                      : card.is_warning
                        ? "border-status-warning text-status-warning"
                        : "border-border-subtle text-content-muted",
                  )}
                >
                  {card.hours_until_service < 1
                    ? `${Math.round(card.hours_until_service * 60)}m until service`
                    : `${card.hours_until_service}h until service`}
                </Badge>
              </div>
            )}

          {card.notes && (
            <div className="mt-1.5 truncate text-[11px] italic text-content-subtle">
              {card.notes}
            </div>
          )}
        </div>
      )}
    </Draggable>
  )
}
