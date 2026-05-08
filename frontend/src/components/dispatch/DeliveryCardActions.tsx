/**
 * R-2.1 — DeliveryCardActions sub-component.
 *
 * Status + icons row at the bottom of DeliveryCard. Extracted from
 * DeliveryCard.tsx (lines 568-708 pre-R-2.1). Renders below + outside
 * the parent's QuickEdit click-button (the actions row is its own
 * independent click region — chat icon, ancillary toggle, hole-dug
 * cycle each have their own onClick).
 *
 * Three clusters in canonical order:
 *   1. Left — secondary-info icons (family / section / helper / note
 *      / chat) via IconTooltip.
 *   2. Right — state indicators (ancillary count badge + HoleDugBadge).
 *   3. R-2.1 NEW — optional R-4 button row (`buttonSlugs`). Renders
 *      between the left icon cluster + right state cluster when set.
 *
 * R-2.1 button composition: the section's `buttonSlugs` prop is an
 * array of registered button slugs (per registry/registrations/buttons).
 * Each slug renders via `<RegisteredButton componentName={slug} />`
 * which handles its own R-4 contract dispatch (open_focus /
 * trigger_workflow / navigate / etc.). Order = array index. Visual
 * editor authoring of `buttonSlugs` happens via the inspector's array-
 * of-componentReference picker (existing infrastructure).
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
import {
  MapPinIcon,
  MessageCircleIcon,
  PaperclipIcon,
  StickyNoteIcon,
  UserIcon,
  UsersIcon,
} from "lucide-react"

import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { RegisteredButton } from "@/lib/runtime-host/buttons/RegisteredButton"

import { IconTooltip } from "./_shared"
import { DeliveryCardHoleDugBadgeRaw } from "./DeliveryCardHoleDugBadge"
import type { DeliveryDTO, HoleDugStatus } from "@/services/dispatch-service"


export interface DeliveryCardActionsProps {
  /** The full delivery DTO — needed for the hole-dug onCycle callback
   *  + ancillary toggle handler. */
  delivery: DeliveryDTO
  /** The parent's density mode — affects icon-row padding scale. */
  isCompact: boolean
  /** Family name. Empty = no family icon. */
  family: string
  /** Cemetery section. Empty = no section icon. */
  section: string
  /** Driver note. Empty = no note icon. */
  driverNote: string
  /** Unread chat count. 0 = no chat icon. */
  chatCount: number
  /** Count of attached ancillaries. 0 = no badge. */
  ancillaryCount: number
  /** Whether the inline ancillary expansion is currently open. */
  ancillaryExpanded: boolean
  /** Click handler for the ancillary toggle. */
  onToggleAncillary?: (deliveryId: string) => void
  /** Click handler for the hole-dug cycle. */
  onCycleHoleDug?: (delivery: DeliveryDTO, nextStatus: HoleDugStatus) => void
  /** Computed next-status for the hole-dug cycle. Pre-computed in
   *  parent so this component stays presentation-only. */
  nextHoleDugStatus: HoleDugStatus
  /** R-2.1 — optional list of registered button slugs to render in
   *  the actions row. When present, renders a `<RegisteredButton>`
   *  per slug between the left + right clusters. Default empty
   *  array. */
  buttonSlugs?: string[]
}


/** R-2.1 — exported as `DeliveryCardActionsRaw`. */
export function DeliveryCardActionsRaw({
  delivery,
  isCompact,
  family,
  section,
  driverNote,
  chatCount,
  ancillaryCount,
  ancillaryExpanded,
  onToggleAncillary,
  onCycleHoleDug,
  nextHoleDugStatus,
  buttonSlugs,
}: DeliveryCardActionsProps) {
  return (
    <div
      data-slot="dispatch-card-icon-row"
      className={cn(
        "flex items-center justify-between gap-1.5",
        "border-t border-border-subtle/60",
        // Phase 4.2.1 — density-driven row padding. Keeps the
        // icon sizes stable across densities.
        isCompact ? "px-2.5 py-1" : "px-3 py-1.5",
      )}
    >
      {/* Left — secondary-info icons with tooltips. */}
      <div className="flex items-center gap-0.5">
        {family && (
          <IconTooltip
            icon={UserIcon}
            label={`Family: ${family}`}
            dataSlot="dispatch-icon-family"
          />
        )}
        {section && (
          <IconTooltip
            icon={MapPinIcon}
            label={`Cemetery section: ${section}`}
            dataSlot="dispatch-icon-section"
          />
        )}
        {/* Phase 4.3.3.1 — helper indicator. */}
        {delivery.helper_user_id && (
          <IconTooltip
            icon={UsersIcon}
            label={
              delivery.helper_user_name
                ? `Helper: ${delivery.helper_user_name}`
                : "Helper: assigned"
            }
            dataSlot="dispatch-icon-helper"
            highlight
          />
        )}
        {driverNote && (
          <IconTooltip
            icon={StickyNoteIcon}
            label={driverNote}
            dataSlot="dispatch-icon-note"
            highlight
          />
        )}
        {chatCount > 0 && (
          <IconTooltip
            icon={MessageCircleIcon}
            label={`${chatCount} unread ${chatCount === 1 ? "message" : "messages"} with funeral home`}
            dataSlot="dispatch-icon-chat"
            highlight
            badge={chatCount}
          />
        )}
      </div>

      {/* R-2.1 — optional R-4 button row (composition-authored).
          Renders between left icon cluster + right state cluster.
          Each slug fires its R-4 contract on click via
          `RegisteredButton`'s internal dispatch. */}
      {buttonSlugs && buttonSlugs.length > 0 && (
        <div
          className="flex items-center gap-1"
          data-slot="dispatch-card-button-row"
        >
          {buttonSlugs.map((slug) => (
            <RegisteredButton key={slug} componentName={slug} />
          ))}
        </div>
      )}

      {/* Right — status indicators (ancillary + hole-dug). */}
      <div className="flex items-center gap-1">
        {ancillaryCount > 0 && (
          <Tooltip>
            <TooltipTrigger
              render={
                <button
                  type="button"
                  data-slot="dispatch-ancillary-badge"
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleAncillary?.(delivery.id)
                  }}
                  className={cn(
                    "relative inline-flex h-6 w-6 items-center justify-center rounded-sm",
                    "text-content-muted hover:bg-surface-sunken transition-colors duration-quick",
                    "focus-ring-accent outline-none cursor-pointer",
                  )}
                  aria-label={`${ancillaryCount} ancillary ${
                    ancillaryCount === 1 ? "item" : "items"
                  } attached — click to ${
                    ancillaryExpanded ? "collapse" : "expand"
                  }`}
                  aria-expanded={ancillaryExpanded}
                >
                  <PaperclipIcon className="h-3.5 w-3.5" aria-hidden />
                  <span
                    data-slot="dispatch-ancillary-badge-count"
                    className={cn(
                      "absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] px-1",
                      "inline-flex items-center justify-center rounded-full",
                      "bg-accent text-content-on-accent text-[10px] font-medium",
                      "font-mono tabular-nums",
                    )}
                    aria-hidden
                  >
                    {ancillaryCount}
                  </span>
                </button>
              }
            />
            <TooltipContent side="top" size="default">
              {`${ancillaryCount} ancillary ${
                ancillaryCount === 1 ? "item" : "items"
              } attached — click to ${
                ancillaryExpanded ? "collapse" : "expand"
              }`}
            </TooltipContent>
          </Tooltip>
        )}
        <DeliveryCardHoleDugBadgeRaw
          status={delivery.hole_dug_status}
          onCycle={
            onCycleHoleDug
              ? () => onCycleHoleDug(delivery, nextHoleDugStatus)
              : undefined
          }
        />
      </div>
    </div>
  )
}
