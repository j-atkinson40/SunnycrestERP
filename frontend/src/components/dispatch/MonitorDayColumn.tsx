/**
 * MonitorDayColumn — one day's pane in the Dispatch Monitor.
 *
 * Phase 3.3 surface polish (2026-04-23) — Apple Reminders quality
 * pass. Changes from Phase 3.2.1:
 *
 *   - REMOVED outer container chrome. The day pane no longer carries
 *     `bg-surface-sunken` + border + shadow. Day sits directly on
 *     the page surface (`--surface-base`); the header's typography
 *     and the floating cards below carry the composition.
 *   - REMOVED driver-lane container chrome. Each lane is now a
 *     typography header (driver name + count) + space + floating
 *     cards. No `rounded border border-border-subtle bg-surface-
 *     elevated` wrapper. Cards provide visual weight via their own
 *     shadow-level-1 (DL §6 canonical — "elevation + shadow + color
 *     do the structural work, not drawn lines").
 *   - ALL drivers render, even with zero deliveries. Empty column
 *     shows driver name + count (0) header; page background below.
 *     Space allocated consistently across rows (dispatcher's eye
 *     scans left-to-right by driver without the driver set shifting
 *     when a column goes empty).
 *   - Day header: two-row composition. Row 1 = day label (text-h2
 *     Plex Sans, weight-medium) + right-aligned action/attribution.
 *     Row 2 = date · state-pill. Same slot for Finalize action and
 *     Finalized-by attribution; only color differentiates semantic.
 *   - Drop-target highlight: brass ring appears on the lane ONLY
 *     during an active drag (the lane has no background by default,
 *     so ring + offset is what signals "drop here" without
 *     introducing chrome in the resting state).
 *
 * Reference: Apple Reminders. Cozy warmth on warm off-white, cards
 * float, no containers competing with card shadows. Per
 * PLATFORM_QUALITY_BAR.md "would this feel as good as the Apple
 * equivalent?" — Apple Reminders is the explicit comparison for this
 * surface.
 */

import { useMemo, useState } from "react"
import { useDroppable } from "@dnd-kit/core"
import { CheckCircle2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type {
  DeliveryDTO,
  DriverDTO,
  HoleDugStatus,
  ScheduleStateDTO,
} from "@/services/dispatch-service"

import { DeliveryCard } from "./DeliveryCard"


export interface MonitorDayColumnProps {
  dateStr: string                         // ISO YYYY-MM-DD
  dayLabel: string                        // "Today" | "Tomorrow" | "Two days out" etc
  schedule: ScheduleStateDTO               // never null; "not_created" state means no row
  deliveries: DeliveryDTO[]               // deliveries for this date (all scheduling_types)
  drivers: DriverDTO[]
  /** Map of ancillary parent_delivery_id → count of ancillaries. */
  ancillaryCounts: Map<string, number>
  /** Ancillaries keyed by parent_delivery_id (for inline expand). */
  ancillariesByParent: Map<string, DeliveryDTO[]>
  onOpenEdit: (delivery: DeliveryDTO) => void
  onCycleHoleDug: (delivery: DeliveryDTO, next: HoleDugStatus) => void
  onFinalize: (dateStr: string) => Promise<void> | void
  onOpenScheduling: (dateStr: string) => void
  onReassignDriver?: (
    deliveryId: string,
    fromDriverId: string | null,
    toDriverId: string | null,
  ) => Promise<void> | void
  /** Override the finalized-by attribution text (e.g. resolved name).
   *  When omitted falls back to a generic "Finalized at {time}". */
  finalizedByLabel?: string | null
}


const UNASSIGNED_LANE_ID = "__UNASSIGNED__"


export function MonitorDayColumn({
  dateStr,
  dayLabel,
  schedule,
  deliveries,
  drivers,
  ancillaryCounts,
  ancillariesByParent,
  onOpenEdit,
  onCycleHoleDug,
  onFinalize,
  onOpenScheduling,
  finalizedByLabel,
}: MonitorDayColumnProps) {
  const finalized = schedule.state === "finalized"
  const notCreated = schedule.state === "not_created"

  const [expandedParents, setExpandedParents] = useState<Set<string>>(
    () => new Set(),
  )
  const [finalizing, setFinalizing] = useState(false)

  // Separate kanban deliveries (primary cards on lanes) from
  // ancillary+direct_ship (surfaced via parent's +N badge).
  const { kanbanByDriver, unassignedKanban } = useMemo(() => {
    const byDriver = new Map<string, DeliveryDTO[]>()
    const unassigned: DeliveryDTO[] = []
    for (const d of deliveries) {
      if (d.scheduling_type !== "kanban") continue
      const did = d.assigned_driver_id
      if (did) {
        if (!byDriver.has(did)) byDriver.set(did, [])
        byDriver.get(did)!.push(d)
      } else {
        unassigned.push(d)
      }
    }
    return { kanbanByDriver: byDriver, unassignedKanban: unassigned }
  }, [deliveries])

  function toggleAncillary(deliveryId: string) {
    setExpandedParents((prev) => {
      const next = new Set(prev)
      if (next.has(deliveryId)) next.delete(deliveryId)
      else next.add(deliveryId)
      return next
    })
  }

  async function handleFinalizeClick() {
    setFinalizing(true)
    try {
      await onFinalize(dateStr)
    } finally {
      setFinalizing(false)
    }
  }

  const dateDisplay = formatDateDisplay(dateStr)

  return (
    <section
      data-slot="dispatch-day-column"
      data-date={dateStr}
      data-schedule-state={schedule.state}
      // Phase 3.3: no outer container chrome. Day sits on page surface.
      // The header's typography + the floating cards carry the
      // composition. Apple Reminders — no drawn box around the whole
      // list.
      className="flex flex-col min-w-0"
    >
      {/* ── Day header ──────────────────────────────────────────────── */}
      <header
        data-slot="dispatch-day-header"
        className="px-1 pb-4 pt-1"
      >
        {/* Row 1: day label (left) + action or attribution (right) */}
        <div className="flex items-baseline justify-between gap-4">
          <h2
            className={cn(
              "text-h2 font-medium leading-none text-content-strong",
              "font-plex-sans tracking-tight",
            )}
          >
            {dayLabel}
          </h2>

          {/* Action / attribution slot — same position regardless of
              schedule state; only the color + text differentiate
              semantic. Draft → brass action; Finalized → muted
              success attribution; not_created → brass "open
              scheduling" action. */}
          <div className="flex flex-none items-center text-caption leading-normal">
            {finalized && schedule.finalized_at && (
              <div
                data-slot="dispatch-day-finalized-attribution"
                className="flex items-center gap-1.5 text-status-success"
              >
                <CheckCircle2Icon className="h-3.5 w-3.5" aria-hidden />
                <span>
                  {finalizedByLabel ??
                    `Finalized ${formatTime(schedule.finalized_at)}`}
                </span>
              </div>
            )}
            {schedule.state === "draft" && (
              <button
                type="button"
                onClick={handleFinalizeClick}
                disabled={finalizing}
                data-slot="dispatch-day-finalize-btn"
                className={cn(
                  "inline-flex items-center gap-1 rounded-sm px-1.5 py-1 -mx-1.5",
                  "text-caption font-medium text-brass hover:text-brass-hover",
                  "transition-colors duration-quick ease-settle",
                  "focus-ring-brass outline-none",
                  "disabled:opacity-60 disabled:cursor-not-allowed",
                  "hover:bg-brass-subtle/40",
                )}
                aria-label={`Finalize schedule for ${dayLabel}`}
              >
                {finalizing
                  ? `Finalizing ${dayLabel}…`
                  : `Finalize ${dayLabel} →`}
              </button>
            )}
            {notCreated && (
              <button
                type="button"
                onClick={() => onOpenScheduling(dateStr)}
                data-slot="dispatch-day-open-scheduling-btn"
                className={cn(
                  "inline-flex items-center gap-1 rounded-sm px-1.5 py-1 -mx-1.5",
                  "text-caption font-medium text-brass hover:text-brass-hover",
                  "transition-colors duration-quick ease-settle",
                  "focus-ring-brass outline-none",
                  "hover:bg-brass-subtle/40",
                )}
              >
                No schedule yet — open scheduling →
              </button>
            )}
          </div>
        </div>

        {/* Row 2: date + state pill (draft only — finalized carries
            its pill content in the attribution text above). */}
        <div className="mt-1.5 flex items-center gap-2 text-body-sm text-content-muted">
          <span className="font-plex-sans">{dateDisplay}</span>
          {schedule.state === "draft" && (
            <span
              data-slot="dispatch-day-draft-badge"
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5",
                "text-micro font-medium uppercase tracking-wider",
                "bg-status-warning-muted text-status-warning",
              )}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full bg-status-warning"
              />
              Draft
            </span>
          )}
        </div>
      </header>

      {/* ── Body — horizontal driver kanban ──────────────────────────── */}
      {notCreated ? (
        <div
          data-slot="dispatch-day-empty"
          className={cn(
            "flex flex-1 flex-col items-center justify-center gap-3",
            "px-4 py-16 text-center",
          )}
        >
          <div className="text-body-sm text-content-muted">
            No schedule yet.
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onOpenScheduling(dateStr)}
          >
            Open scheduling
          </Button>
        </div>
      ) : drivers.length === 0 && unassignedKanban.length === 0 ? (
        // True empty state — no drivers in roster, no unassigned. Rare
        // at Sunnycrest scale; kept for defense.
        <div
          data-slot="dispatch-day-empty"
          className={cn(
            "flex flex-1 flex-col items-center justify-center gap-3",
            "px-4 py-16 text-center",
          )}
        >
          <div className="text-body-sm text-content-muted">
            No deliveries scheduled.
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onOpenScheduling(dateStr)}
          >
            Open scheduling
          </Button>
        </div>
      ) : (
        <div
          data-slot="dispatch-day-kanban"
          className={cn(
            "flex flex-row gap-6 overflow-x-auto overflow-y-hidden",
            // Px-1 keeps shadows from getting clipped at left/right
            // edges when columns sit flush against scroll boundary.
            "px-1 pb-4",
            "scroll-smooth",
          )}
        >
          {/* Unassigned lane first — only if any kanban cards are
              unassigned. Dispatchers want the "needs attention" pile
              at the left edge where their eye lands first. */}
          {unassignedKanban.length > 0 && (
            <DriverLane
              laneKey={`${dateStr}:${UNASSIGNED_LANE_ID}`}
              laneLabel="Unassigned"
              deliveries={unassignedKanban}
              ancillaryCounts={ancillaryCounts}
              ancillariesByParent={ancillariesByParent}
              expandedParents={expandedParents}
              onToggleAncillary={toggleAncillary}
              onOpenEdit={onOpenEdit}
              onCycleHoleDug={onCycleHoleDug}
              scheduleFinalized={finalized}
              isUnassignedLane
            />
          )}

          {/* Driver lanes — horizontal stack. Phase 3.3: ALL active
              drivers render, even with zero deliveries. Consistency
              across days matters more than compaction — dispatcher's
              eye scans the same driver set every day. */}
          {drivers.map((driver) => {
            const laneDeliveries = kanbanByDriver.get(driver.id) ?? []
            return (
              <DriverLane
                key={driver.id}
                laneKey={`${dateStr}:${driver.id}`}
                laneLabel={
                  driver.display_name ??
                  `Driver ${driver.license_number ?? "—"}`
                }
                deliveries={laneDeliveries}
                ancillaryCounts={ancillaryCounts}
                ancillariesByParent={ancillariesByParent}
                expandedParents={expandedParents}
                onToggleAncillary={toggleAncillary}
                onOpenEdit={onOpenEdit}
                onCycleHoleDug={onCycleHoleDug}
                scheduleFinalized={finalized}
              />
            )
          })}
        </div>
      )}
    </section>
  )
}


// ── Driver lane ───────────────────────────────────────────────────────


interface DriverLaneProps {
  laneKey: string
  laneLabel: string
  deliveries: DeliveryDTO[]
  ancillaryCounts: Map<string, number>
  ancillariesByParent: Map<string, DeliveryDTO[]>
  expandedParents: Set<string>
  onToggleAncillary: (parentId: string) => void
  onOpenEdit: (delivery: DeliveryDTO) => void
  onCycleHoleDug: (d: DeliveryDTO, next: HoleDugStatus) => void
  scheduleFinalized: boolean
  isUnassignedLane?: boolean
}


function DriverLane({
  laneKey,
  laneLabel,
  deliveries,
  ancillaryCounts,
  ancillariesByParent,
  expandedParents,
  onToggleAncillary,
  onOpenEdit,
  onCycleHoleDug,
  scheduleFinalized,
  isUnassignedLane,
}: DriverLaneProps) {
  const { setNodeRef, isOver } = useDroppable({
    id: laneKey,
    data: { laneKey },
  })

  const hasDeliveries = deliveries.length > 0

  return (
    <div
      ref={setNodeRef}
      data-slot="dispatch-driver-lane"
      data-lane={laneKey}
      data-drop-over={isOver ? "true" : "false"}
      data-empty={hasDeliveries ? "false" : "true"}
      className={cn(
        "flex-none w-[280px] flex flex-col",
        // Phase 3.3: no lane container chrome. Column is
        // typography header + card stack. Rely on card shadows +
        // page background for visual weight.
        "transition-[box-shadow] duration-quick ease-settle",
        // Drop target affordance — brass ring appears only during
        // an active drag. Surfaces against the page without
        // introducing resting-state chrome.
        isOver && [
          "rounded-md",
          "ring-2 ring-brass ring-offset-4 ring-offset-surface-base",
        ],
      )}
    >
      {/* Column header — typography-led, no background. */}
      <div
        data-slot="dispatch-driver-lane-header"
        className={cn(
          "flex items-baseline gap-2 px-1 pb-3",
          isUnassignedLane && "italic",
        )}
      >
        <span
          className={cn(
            "text-body-sm font-medium text-content-strong truncate",
          )}
          title={laneLabel}
        >
          {laneLabel}
        </span>
        <span
          className={cn(
            "flex-none text-caption text-content-muted tabular-nums",
            "font-plex-mono",
            !hasDeliveries && "text-content-subtle",
          )}
        >
          {deliveries.length}
        </span>
      </div>

      {/* Card stack — cards float via their own shadows. Empty
          state shows a subtle placeholder so the column doesn't
          feel broken; min-height keeps columns aligned row-wise
          even when a driver has zero deliveries today. */}
      <div
        data-slot="dispatch-driver-lane-body"
        className={cn(
          "flex-1 space-y-3 pb-2",
          // Min-height so an empty column still holds vertical
          // space. Keeps the driver-row baseline consistent across
          // days: if Mike has 5 cards today and 0 tomorrow, his
          // column appears at the same x-offset in both.
          "min-h-[80px]",
        )}
      >
        {!hasDeliveries && (
          <div
            data-slot="dispatch-driver-lane-empty"
            className={cn(
              "flex h-20 items-center justify-center px-3",
              "text-caption text-content-subtle",
            )}
          >
            —
          </div>
        )}
        {deliveries.map((d) => {
          const ancCount = ancillaryCounts.get(d.id) ?? 0
          const expanded = expandedParents.has(d.id)
          const ancillaries = expanded
            ? (ancillariesByParent.get(d.id) ?? [])
            : []
          return (
            <div key={d.id}>
              <DeliveryCard
                delivery={d}
                scheduleFinalized={scheduleFinalized}
                ancillaryCount={ancCount}
                ancillaryExpanded={expanded}
                onOpenEdit={onOpenEdit}
                onCycleHoleDug={onCycleHoleDug}
                onToggleAncillary={onToggleAncillary}
              />
              {expanded && ancillaries.length > 0 && (
                <div
                  data-slot="dispatch-ancillary-expanded"
                  className={cn(
                    "mt-1.5 ml-4 space-y-1 rounded-md border-l-2 border-brass/40",
                    "bg-surface-sunken/60 px-3 py-2",
                  )}
                >
                  {ancillaries.map((a) => {
                    const family =
                      (a.type_config?.family_name as string | undefined) ?? "—"
                    const type =
                      (a.type_config?.service_type as string | undefined) ?? ""
                    return (
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => onOpenEdit(a)}
                        className={cn(
                          "w-full text-left text-caption",
                          "text-content-base hover:text-content-strong",
                          "focus-ring-brass outline-none rounded",
                          "px-1 py-0.5",
                        )}
                      >
                        <span className="font-medium">{family}</span>
                        {type && (
                          <span className="ml-2 text-content-muted">
                            · {type.replace(/_/g, " ")}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ── helpers ───────────────────────────────────────────────────────────


function formatDateDisplay(isoDate: string): string {
  // Parse as local date (avoid TZ shift for date-only strings).
  const [y, m, d] = isoDate.split("-").map(Number)
  if (!y || !m || !d) return isoDate
  const dt = new Date(y, m - 1, d)
  return dt.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
}


function formatTime(isoDateTime: string): string {
  try {
    const dt = new Date(isoDateTime)
    return dt.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    })
  } catch {
    return isoDateTime
  }
}
