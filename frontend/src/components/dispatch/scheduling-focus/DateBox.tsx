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
 * is jewelry. Accent border + accent-subtle wash signals "this day is
 * selected, the affordance has been engaged." At rest, calm. On
 * hover, subtle warming (`bg-accent-subtle/30`). On active, the
 * accent border lights up (`border-accent`) — same composition the
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
 * decorative chrome), same accent-as-jewelry vocabulary (functional
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
              // corners. Aesthetic Arc Session 3 (April 2026) restores
              // a subtle warm fill at rest — Session 1.6's transparent
              // + border-only treatment read as "barely visible
              // outline" against the dimmed/blurred Focus substrate.
              // User feedback: "date boxes are too quiet at rest,
              // calibrate to read as peripheral interactive surface
              // comparable to Pin's presence."
              "inline-flex flex-col items-center justify-center",
              "min-w-[48px] px-2.5 py-1 rounded-sm",
              // Aesthetic Arc Session 3 — `bg-surface-elevated/50`
              // warm fill at rest. Pin uses `bg-surface-elevated/85`
              // because it's a floating card with backdrop-blur; the
              // DateBox is INLINE header chrome, not a card, so /50
              // is the right register: visible warmer-than-substrate
              // fill that establishes "interactive surface" without
              // claiming card-level presence. Border at full strength
              // (Session 1.6 calibration) layered on top defines the
              // edge.
              //
              // Section 0 Detail Concentration: quiet but present at
              // rest, jewelry only at active state. The fill makes the
              // box discoverable; the H2 day label remains the
              // dominant element in the header hierarchy.
              "bg-surface-elevated/50",
              "border border-border-subtle",
              // Hover — subtle accent warming. Bumped opacity slightly
              // (/20 → /30) for clearer interactive feedback at the
              // new visibility level.
              "hover:bg-accent-subtle/30",
              // Quietness — motion is purposeful, no bounce. Same
              // tokens as the rest of the platform's hover transitions.
              "transition-colors duration-quick ease-settle",
              // Accent focus ring — platform-wide convention for
              // interactive non-input elements (DESIGN_LANGUAGE §6
              // focus indicators).
              "focus-ring-accent outline-none",
              // Active state — jewelry on. Accent border + accent-
              // subtle wash. Same composition as AncillaryPoolPin
              // active drop-target + Finalize button at-rest accent
              // text. Cross-surface vocabulary consistency.
              active && [
                "border-accent bg-accent-subtle/50",
              ],
            )}
          >
            {/* Eyebrow — weekday abbreviation. text-micro is platform-
                wide eyebrow treatment. Cross-surface vocabulary
                consistency: same micro-eyebrow as Scheduling header
                + AncillaryPoolPin header. */}
            <span
              className={cn(
                "text-micro uppercase tracking-wider leading-tight",
                "text-content-muted font-plex-sans",
                active && "text-content-base",
              )}
            >
              {weekday}
            </span>
            {/* Date — month + day. Aesthetic Arc Session 1.6 —
                font-size restored from 12px to 13px (text-[0.8125rem])
                — middle ground between Session 1's 14px (text-body-sm)
                and Session 1.5's 12px (text-caption). User: "slightly
                larger than current, but still smaller than H2." H2 is
                16px (text-h3); 13px keeps the box subordinate. Plex
                Mono retained for tabular alignment with lane count
                digits + count chip. */}
            <span
              className={cn(
                "text-[0.8125rem] leading-tight tabular-nums",
                "text-content-base font-plex-mono",
                active && "text-content-strong",
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
