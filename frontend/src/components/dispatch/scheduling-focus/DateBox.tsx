/**
 * DateBox — Phase B Session 4.4.3 adjacent-day peek/slide affordance.
 *
 * Two DateBoxes flank the H2 day label in the Scheduling Focus header:
 *
 *   [today_box]  H2 (clickable for any-day jump)  [day_after_box]
 *                ↑ peek today                     ↑ peek tomorrow
 *
 * Each box shows an abbreviated weekday + month-day label, hover-
 * reveals a text summary tooltip ("{N} deliveries · {M} unassigned ·
 * {finalize}"), and toggles an active state on click. The active
 * state is consumed by Phase 4.4.4 to render that adjacent day
 * inline. Phase 4.4.3 is state-tracking only — no animation, no
 * multi-day rendering yet.
 *
 * Aesthetic register — calibrated to DESIGN_LANGUAGE Section 0
 * ────────────────────────────────────────────────────────────
 * The first surface built against locked Section 0. Calibration
 * notes:
 *
 * ARCHITECTURAL PROPORTIONS (Translation Principle 2). Square-
 * shouldered. `radius-sm` (4px) — sharper than card-md (8px). Range
 * Rover door surface, not pillowy chip. Lean toward sharp.
 *
 * MATERIAL HONESTY. `bg-surface-elevated` at rest — small lift from
 * the page surface, no shadow because date boxes are inline header
 * affordances, not floating cards. The lift is fill-only, the way
 * AncillaryPoolPin's pool surface lifts (no perimeter border, no
 * shadow halo).
 *
 * RESTRAINT. Two lines of content. Eyebrow weekday (text-micro
 * uppercase tracking-wider — same eyebrow treatment as the
 * Scheduling header itself + AncillaryPoolPin). Body-sm date.
 * Nothing else. No icons, no badges, no decorative chrome.
 *
 * DETAIL CONCENTRATION (Translation Principle 4). The active state
 * is jewelry. Brass border + brass-subtle wash signals "this day is
 * selected, the affordance has been engaged." At rest, calm. On
 * hover, subtle warming (`bg-brass-subtle/30`). On active, the
 * brass border lights up (`border-brass`) — same composition the
 * AncillaryPoolPin uses for active drop-target feedback (Phase
 * 4.3b.4) for cross-surface consistency.
 *
 * QUIETNESS. Hover and active transitions ride the platform's
 * `duration-quick ease-settle` motion contract. No bouncing, no
 * theatrical reveal. Click feels like a switch.
 *
 * BRITISH REGISTER. The boxes don't announce. No "Click for
 * preview" copy. No "→" arrow indicating expansion. The placement
 * (flanking the H2, identical visual register on both sides) is
 * the affordance.
 *
 * The aesthetic test: would these flank a DeliveryCard floating on
 * the kanban lane, look like the same team made both? Yes — same
 * surface family (bg-surface-elevated), same restraint (no
 * decorative chrome), same brass-as-jewelry vocabulary (functional
 * emphasis only on engaged state).
 */

import { useMemo } from "react"

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useDaySummary } from "@/hooks/useDaySummary"
import { cn } from "@/lib/utils"


export interface DateBoxProps {
  /** ISO date string (YYYY-MM-DD) for this box's target day. */
  date: string
  /** True when this box has been engaged — the day is part of the
   *  multi-day expanded view. Phase 4.4.3: state-only; visual
   *  feedback only. Phase 4.4.4 wires this to render the adjacent
   *  day's lane content. */
  active: boolean
  /** Click handler — toggles the active state up at the parent. */
  onClick: () => void
  /** Optional aria-label override for context-sensitive labeling
   *  (e.g. "Yesterday, April 24" vs "Tomorrow, April 26"). When
   *  omitted, falls back to the formatted full date string. */
  ariaLabel?: string
}


// Format helpers. Pure functions — kept in the module so tests can
// import without rendering the component.

export function formatWeekdayShort(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number)
  if (!y || !m || !d) return ""
  // Local-tz parse — date-only strings don't carry tz, so the user's
  // browser tz is correct for display. The backend already resolves
  // tenant-local dates separately via tenant-time.
  const dt = new Date(y, m - 1, d)
  // "Tue", "Wed", "Sun" — three-letter abbreviation per spec.
  return dt.toLocaleDateString(undefined, { weekday: "short" })
}

export function formatMonthDayShort(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number)
  if (!y || !m || !d) return ""
  const dt = new Date(y, m - 1, d)
  // "Apr 25" — abbreviated month + numeric day.
  return dt.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function formatFullLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number)
  if (!y || !m || !d) return iso
  const dt = new Date(y, m - 1, d)
  return dt.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
}


function formatFinalizeStatusForTooltip(
  status: "draft" | "finalized" | "not_created",
  finalizedAt: string | null,
): string {
  if (status === "finalized") {
    if (!finalizedAt) return "Finalized"
    const dt = new Date(finalizedAt)
    if (Number.isNaN(dt.getTime())) return "Finalized"
    // "Finalized 2:34pm" — short tenant-local-ish time. Browser-tz
    // is acceptable here; the dispatcher's clock and the tenant's
    // clock match in the deployed configuration.
    const time = dt.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    })
    return `Finalized ${time}`
  }
  if (status === "draft") return "Draft"
  return "No schedule"
}


export function DateBox({ date, active, onClick, ariaLabel }: DateBoxProps) {
  const { summary, loading, error } = useDaySummary(date)

  const weekday = useMemo(() => formatWeekdayShort(date), [date])
  const monthDay = useMemo(() => formatMonthDayShort(date), [date])
  const fullLabel = useMemo(() => ariaLabel ?? formatFullLabel(date), [
    ariaLabel,
    date,
  ])

  const tooltipBody = useMemo(() => {
    if (error) return "Couldn't load summary"
    if (loading || !summary) return "…"
    const total = summary.total_deliveries
    const unassigned = summary.unassigned_count
    const status = formatFinalizeStatusForTooltip(
      summary.finalize_status,
      summary.finalized_at,
    )
    const deliveriesPart = `${total} ${total === 1 ? "delivery" : "deliveries"}`
    const unassignedPart = `${unassigned} unassigned`
    return `${deliveriesPart} · ${unassignedPart} · ${status}`
  }, [summary, loading, error])

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <button
            type="button"
            onClick={onClick}
            data-slot="scheduling-focus-date-box"
            data-date={date}
            data-active={active ? "true" : "false"}
            aria-label={fullLabel}
            aria-pressed={active}
            className={cn(
              // Architectural proportions — square-shouldered, sharp
              // corners. Generous internal padding (workshop-not-
              // cramped per Section 5).
              "inline-flex flex-col items-center justify-center",
              "min-w-[60px] px-3 py-1.5 rounded-sm",
              // Material at rest — fill-only lift from page bg, no
              // shadow (date boxes are inline affordances, not
              // floating cards). Subtle warm-gray surface.
              "bg-surface-elevated",
              // Border rest state — subtle perimeter to give the box
              // its "object" affordance. Brass on active state
              // (jewelry — Detail Concentration §4 translation).
              "border border-border-subtle",
              // Hover — subtle brass warming. No border change at
              // hover; border change reserved for active (the
              // selected day signal). Matches AncillaryPoolPin
              // PoolItem's hover pattern (`hover:bg-brass-subtle/40`).
              "hover:bg-brass-subtle/30",
              // Quietness — motion is purposeful, no bounce. Same
              // tokens as the rest of the platform's hover transitions.
              "transition-colors duration-quick ease-settle",
              // Brass focus ring — platform-wide convention for
              // interactive non-input elements (DESIGN_LANGUAGE §6
              // focus indicators). Inherits the `--focus-ring-alpha`
              // composition.
              "focus-ring-brass outline-none",
              // Active state — jewelry on. Brass border + brass-
              // subtle wash. Matches AncillaryPoolPin's active drop-
              // target chrome (`bg-brass-subtle/40` + brass border)
              // for cross-surface consistency. Tightening the border
              // color to `border-brass` (full saturation) at active
              // gives the "this day is selected" signal weight; rest
              // and hover both carry the subtle border.
              active && [
                "border-brass bg-brass-subtle/50",
              ],
            )}
          >
            {/* Eyebrow — weekday abbreviation. Same micro-eyebrow
                treatment used in the Scheduling header itself + the
                AncillaryPoolPin header. Cross-surface vocabulary
                consistency. */}
            <span
              className={cn(
                "text-micro uppercase tracking-wider leading-tight",
                "text-content-muted font-plex-sans",
                active && "text-content-base",
              )}
            >
              {weekday}
            </span>
            {/* Date — month + day. Plex Mono on the digit area for
                tabular alignment with the lane count digits + the
                ancillary pool count chip; both sit on the same vertical
                rhythm in the surrounding chrome. */}
            <span
              className={cn(
                "text-body-sm leading-tight tabular-nums",
                "text-content-strong font-plex-mono",
              )}
            >
              {monthDay}
            </span>
          </button>
        }
      />
      <TooltipContent side="bottom" align="center">
        {tooltipBody}
      </TooltipContent>
    </Tooltip>
  )
}
