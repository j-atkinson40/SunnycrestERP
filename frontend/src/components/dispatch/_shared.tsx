/**
 * Shared dispatch-card primitives — Phase 4.3.3 commit 2.
 *
 * Extracted from `DeliveryCard.tsx` so `AncillaryCard.tsx` (smaller,
 * fewer-fields card for standalone ancillaries on the Scheduling
 * Focus kanban) can reuse the same icon+tooltip composition without
 * duplicating implementation. PQB §5 Consistency: the family/section/
 * note/chat status icons must look + behave identically across
 * primary delivery cards and ancillary cards. Same gesture, same
 * tooltip delay, same hover affordance.
 *
 * Currently exported:
 *   - IconTooltip: a Lucide icon wrapped in TooltipTrigger +
 *     TooltipContent, with optional `highlight` (text-brass when
 *     content is "worth noticing") and optional `badge` (small
 *     count pill, e.g. unread chat count).
 *
 * Future candidates for this file (NOT in 4.3.3 scope):
 *   - HoleDugBadge — currently DeliveryCard-only; ancillaries don't
 *     have hole-dug state.
 *   - Card chrome wrapper that handles drag + body click contract
 *     consistently. Premature to extract until a third card type
 *     surfaces.
 */

import type { ComponentType } from "react"

import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"


export interface IconTooltipProps {
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>
  /** Tooltip body. Becomes the icon's `aria-label` too. */
  label: string
  /** `data-slot` for testability. */
  dataSlot: string
  /** True = render the icon in `text-brass` (signals "this has
   *  non-empty content worth noticing", e.g. a pending note or
   *  unread chat). False/default = `text-content-muted`. */
  highlight?: boolean
  /** Optional small count pill at the icon's top-right corner.
   *  Used for unread-chat counts. Hidden when 0 or undefined. */
  badge?: number
}


/**
 * IconTooltip — a Lucide icon wrapped in a base-ui Tooltip with
 * `data-slot` + ARIA wired up. Phase 4.2.4 removed the previous
 * `onPointerDown={e.stopPropagation()}` so drag activates from the
 * icon-row area too; PointerSensor `activationConstraint:
 * { distance: 8 }` cleanly separates hover (no movement) from drag.
 */
export function IconTooltip({
  icon: Icon,
  label,
  dataSlot,
  highlight = false,
  badge,
}: IconTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            data-slot={dataSlot}
            className={cn(
              "relative inline-flex h-6 w-6 items-center justify-center rounded-sm",
              "focus-ring-brass outline-none cursor-default",
              highlight ? "text-brass" : "text-content-muted",
              "hover:bg-surface-sunken transition-colors duration-quick",
            )}
            role="img"
            aria-label={label}
            tabIndex={0}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {typeof badge === "number" && badge > 0 && (
              <span
                data-slot={`${dataSlot}-badge`}
                className={cn(
                  "absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] px-1",
                  "inline-flex items-center justify-center rounded-full",
                  "bg-brass text-content-on-brass text-[10px] font-medium",
                  "font-plex-mono tabular-nums",
                )}
                aria-hidden
              >
                {badge}
              </span>
            )}
          </span>
        }
      />
      <TooltipContent side="top" size="default" className="max-w-[240px]">
        {label}
      </TooltipContent>
    </Tooltip>
  )
}
