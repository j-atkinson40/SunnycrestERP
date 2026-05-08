/**
 * R-2.1 — DeliveryCardHoleDugBadge sub-component.
 *
 * Three-state jewel-set status indicator (unknown → yes → no →
 * unknown) at the bottom-right of DeliveryCard. Extracted from
 * DeliveryCard.tsx (lines 739-830 pre-R-2.1) — the badge was already
 * a separate internal function declaration; R-2.1 promotes it to its
 * own file + sub-section registration so admins can author its
 * tokens + behavior independently of the parent card chrome.
 *
 * Per /tmp/r2_1_subsection_scope.md Section 2 amendment 2: HoleDugBadge
 * has its own meaningful authoring surface (token color, jewel-set
 * vs flat treatment, three-state mapping). Registered with
 * sectionRole "custom" (not part of the canonical header/body/actions
 * spine).
 *
 * Aesthetic Arc Session 4.7 — Pattern 3 jewel-set badge. Background
 * uses `--surface-base` (page substrate; substantially darker than
 * card surface `--surface-elevated`). The ~0.12 OKLCH lightness
 * delta is enough to read as "well below the surface."
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
import {
  CheckIcon,
  HelpCircleIcon,
  MinusIcon,
} from "lucide-react"

import type { HoleDugStatus } from "@/services/dispatch-service"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"


export interface DeliveryCardHoleDugBadgeProps {
  status: HoleDugStatus
  /** Click handler — when set, the badge is clickable + shows hover
   *  ring + cycle hint. When unset, the badge renders as a static
   *  status display. */
  onCycle?: () => void
}


/** R-2.1 — exported as `DeliveryCardHoleDugBadgeRaw`. */
export function DeliveryCardHoleDugBadgeRaw({
  status,
  onCycle,
}: DeliveryCardHoleDugBadgeProps) {
  // Aesthetic Arc Session 4.7 — Pattern 3 jewel-set badge.
  const config = {
    yes: {
      icon: CheckIcon,
      cls: "bg-surface-base text-accent-confirmed",
      label: "Hole dug: yes",
    },
    no: {
      icon: MinusIcon,
      cls: "bg-surface-base text-content-muted",
      label: "Hole dug: no",
    },
    unknown: {
      icon: HelpCircleIcon,
      cls: "bg-surface-base text-accent",
      label: "Hole dug: unknown (not yet confirmed)",
    },
  }[status]

  const Icon = config.icon

  const clickProps = onCycle
    ? {
        onPointerDown: (e: React.PointerEvent) => e.stopPropagation(),
        onClick: (e: React.MouseEvent) => {
          e.stopPropagation()
          onCycle()
        },
      }
    : {}

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            data-slot="dispatch-hole-dug-badge"
            data-status={status}
            disabled={!onCycle}
            className={cn(
              "inline-flex h-5 w-5 items-center justify-center rounded-full",
              config.cls,
              // Aesthetic Arc Session 4.5 — Pattern 3 jewel-set status
              // indicator. Mode-aware inset shadow via
              // `--shadow-jewel-inset` token. Reads as physical
              // recessed ring with the icon set into the surface.
              "shadow-[var(--shadow-jewel-inset)]",
              onCycle &&
                "hover:ring-1 hover:ring-accent/40 transition-all duration-quick cursor-pointer",
              !onCycle && "cursor-default",
              "focus-ring-accent outline-none",
            )}
            aria-label={config.label}
            {...clickProps}
          >
            <Icon className="h-3 w-3" aria-hidden />
          </button>
        }
      />
      <TooltipContent side="top" size="default">
        {config.label}
        {onCycle && (
          <span className="ml-1 text-content-muted">— click to cycle</span>
        )}
      </TooltipContent>
    </Tooltip>
  )
}
