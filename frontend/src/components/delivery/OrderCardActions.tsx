/**
 * R-2.1 — OrderCardActions sub-component.
 *
 * Bottom region of OrderCard — hours-countdown badge + free-form
 * notes. Extracted from OrderCard.tsx (lines 188-215 pre-R-2.1).
 *
 * Marked `optional: true` in the registration. Per
 * /tmp/r2_1_subsection_scope.md Section 1: OrderCard's "actions"
 * region is the weakest fit for the common spine — its bottom
 * region is informational (countdown + notes), not action-shaped.
 * Section renders only when at least one of (countdown / notes /
 * R-2.1 buttons) has content.
 *
 * R-2.1 ADDS data-slot markers — pre-R-2.1 OrderCard had none.
 * `order-card-countdown` + `order-card-notes`.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { RegisteredButton } from "@/lib/runtime-host/buttons/RegisteredButton"
import type { KanbanCard } from "@/types/delivery"


export interface OrderCardActionsProps {
  card: KanbanCard
  /** R-2.1 — optional list of registered button slugs. */
  buttonSlugs?: string[]
}


/** R-2.1 — exported as `OrderCardActionsRaw`. */
export function OrderCardActionsRaw({
  card,
  buttonSlugs,
}: OrderCardActionsProps) {
  const hasButtons = buttonSlugs && buttonSlugs.length > 0
  const hasCountdown =
    card.hours_until_service !== null && card.hours_until_service > 0
  const hasNotes = !!card.notes
  // Optional section — collapse entirely if nothing to show.
  if (!hasCountdown && !hasNotes && !hasButtons) return null

  return (
    <>
      {/* R-2.1 — optional R-4 button row above countdown. */}
      {hasButtons && (
        <div
          className="mt-1.5 flex items-center gap-1"
          data-slot="order-card-button-row"
        >
          {buttonSlugs!.map((slug) => (
            <RegisteredButton key={slug} componentName={slug} />
          ))}
        </div>
      )}

      {/* Hours countdown — critical pulses with error-family,
          warning is warning-family, otherwise subtle outline. */}
      {hasCountdown && (
        <div className="mt-1.5" data-slot="order-card-countdown">
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
            {card.hours_until_service! < 1
              ? `${Math.round(card.hours_until_service! * 60)}m until service`
              : `${card.hours_until_service}h until service`}
          </Badge>
        </div>
      )}

      {hasNotes && (
        <div
          className="mt-1.5 truncate text-[11px] italic text-content-subtle"
          data-slot="order-card-notes"
        >
          {card.notes}
        </div>
      )}
    </>
  )
}
