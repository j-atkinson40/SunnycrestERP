/**
 * R-2.1 — OrderCardBody sub-component.
 *
 * "What + where + when" block — vault/equipment summary + service
 * location/cemetery + service/ETA times. Extracted from OrderCard.tsx
 * (lines 102-186 pre-R-2.1).
 *
 * R-2.1 ADDS data-slot markers — pre-R-2.1 OrderCard had none.
 * `order-card-vault` + `order-card-service`.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
import { Box, Church, Landmark, MapPin } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { KanbanCard } from "@/types/delivery"


export interface OrderCardBodyProps {
  card: KanbanCard
  cemeteryWithLocation: (card: KanbanCard) => string
}


/** R-2.1 — exported as `OrderCardBodyRaw`. */
export function OrderCardBodyRaw({
  card,
  cemeteryWithLocation,
}: OrderCardBodyProps) {
  return (
    <>
      {/* Vault · Equipment */}
      {(card.vault_type || card.equipment_summary) && (
        <div
          className="mt-1.5 text-xs text-content-base"
          data-slot="order-card-vault"
        >
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
      <div
        className="mt-1.5 text-xs text-content-muted space-y-0.5"
        data-slot="order-card-service"
      >
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
    </>
  )
}
