/**
 * MonitorDayColumn — one day's pane in the Dispatch Monitor.
 *
 * Phase 3.1 + 3.2 rebuild (2026-04-23). Major structural changes from
 * Phase 3:
 *
 *   - LAYOUT: the day pane is now a vertical container with a
 *     HORIZONTAL driver-lane kanban inside it (Airtable visual
 *     pattern). Lanes stack horizontally; each lane is a vertical
 *     column of cards. When drivers exceed viewport width, the
 *     inner region scrolls horizontally (no vertical page scroll
 *     needed to see another driver). Matches the only prior solution
 *     James found that got dispatch density right.
 *
 *   - FINALIZE BUTTON STYLE: the draft-state "Finalize this schedule"
 *     now sits in the same header slot + same typography as the
 *     finalized attribution. Only the color changes semantic —
 *     finalized renders text-status-success; draft renders text-brass
 *     (clickable action color). Visual consistency across both
 *     states; the dispatcher's eye lands on the same location for
 *     "what's going on with this day".
 *
 *   - Empty states still show "No schedule yet" / "No deliveries
 *     scheduled" with an Open Scheduling affordance.
 *
 *   - Ancillary badge + inline expand unchanged from Phase 3; lives
 *     in this component (per-day scope).
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
  const driversWithDeliveries = drivers.filter(
    (d) => (kanbanByDriver.get(d.id) ?? []).length > 0,
  )

  return (
    <section
      data-slot="dispatch-day-column"
      data-date={dateStr}
      data-schedule-state={schedule.state}
      className={cn(
        "flex flex-col min-w-0 rounded-md border border-border-subtle",
        "bg-surface-sunken shadow-level-1",
      )}
    >
      {/* ── Day header ──────────────────────────────────────────────── */}
      <header
        data-slot="dispatch-day-header"
        className="border-b border-border-subtle px-4 py-3"
      >
        <div className="flex items-baseline gap-3">
          <h3
            className={cn(
              "text-h3 font-medium leading-none text-content-strong",
              "font-plex-serif",
            )}
          >
            {dayLabel}
          </h3>
          <span className="text-body-sm text-content-muted">
            {dateDisplay}
          </span>
          {schedule.state === "draft" && (
            <span
              data-slot="dispatch-day-draft-badge"
              className={cn(
                "inline-flex items-center rounded-sm px-1.5 py-0.5",
                "text-micro font-medium uppercase tracking-wider",
                "bg-status-warning-muted text-status-warning",
              )}
            >
              Draft
            </span>
          )}
        </div>

        {/* Action/attribution row — same slot, same typography, color
            differentiates semantic. Finalized → muted success; draft
            → clickable brass button; not_created → Open Scheduling. */}
        <div className="mt-1.5 min-h-[1.5rem] text-caption leading-normal">
          {finalized && schedule.finalized_at && (
            <div
              data-slot="dispatch-day-finalized-attribution"
              className="flex items-center gap-1 text-status-success"
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
                "inline-flex items-center gap-1 rounded-sm",
                "text-caption text-brass hover:text-brass-hover",
                "transition-colors duration-quick",
                "focus-ring-brass outline-none",
                "disabled:opacity-60 disabled:cursor-not-allowed",
                // Underlined-on-hover reinforces "action" without
                // turning into a full button visual (keeps the slot
                // matched with finalized-attribution below it).
                "hover:underline decoration-brass/40 underline-offset-2",
              )}
              aria-label={`Finalize schedule for ${dayLabel}`}
            >
              {finalizing
                ? `Finalizing ${dayLabel}…`
                : `Finalize ${dayLabel} ▸`}
            </button>
          )}
          {notCreated && (
            <button
              type="button"
              onClick={() => onOpenScheduling(dateStr)}
              data-slot="dispatch-day-open-scheduling-btn"
              className={cn(
                "inline-flex items-center gap-1 rounded-sm",
                "text-caption text-brass hover:text-brass-hover",
                "transition-colors duration-quick",
                "focus-ring-brass outline-none",
                "hover:underline decoration-brass/40 underline-offset-2",
              )}
            >
              No schedule yet — open scheduling ▸
            </button>
          )}
        </div>
      </header>

      {/* ── Body — horizontal driver kanban ──────────────────────────── */}
      {notCreated || deliveries.length === 0 ? (
        <div
          data-slot="dispatch-day-empty"
          className={cn(
            "flex flex-1 flex-col items-center justify-center gap-3",
            "px-4 py-12 text-center",
          )}
        >
          <div className="text-body-sm text-content-muted">
            {notCreated ? "No schedule yet." : "No deliveries scheduled."}
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
            "flex flex-row gap-3 overflow-x-auto overflow-y-hidden",
            "p-3",
            // Scroll-shadow hint via light inset so users see there's
            // more when lanes exceed viewport width.
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

          {/* Driver lanes — horizontal stack. Empty drivers skipped
              (there's no "show all drivers" checkbox in the spec; the
              dispatcher picks a driver when assigning via QuickEdit). */}
          {driversWithDeliveries.map((driver) => {
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

          {/* Empty-lane pile — all drivers empty + no unassigned.
              Rare, but possible mid-setup. */}
          {driversWithDeliveries.length === 0 &&
            unassignedKanban.length === 0 && (
              <div className="flex-1 py-8 text-center text-body-sm text-content-muted">
                No kanban deliveries for this day.
              </div>
            )}
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

  return (
    <div
      ref={setNodeRef}
      data-slot="dispatch-driver-lane"
      data-lane={laneKey}
      data-drop-over={isOver ? "true" : "false"}
      className={cn(
        "flex-none w-[280px] flex flex-col",
        "rounded border border-border-subtle bg-surface-elevated",
        "transition-colors duration-quick ease-settle",
        isOver && "ring-2 ring-brass ring-offset-1 ring-offset-surface-sunken",
        isUnassignedLane && "border-dashed",
      )}
    >
      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
        <span
          className={cn(
            "text-body-sm font-medium text-content-strong truncate",
          )}
          title={laneLabel}
        >
          {laneLabel}
        </span>
        <span className="ml-auto flex-none text-caption text-content-muted font-plex-mono tabular-nums">
          {deliveries.length}
        </span>
      </div>
      <div className="flex-1 space-y-2 p-2 overflow-y-auto">
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
                    "mt-1 ml-4 space-y-1 rounded border-l-2 border-brass/40",
                    "bg-surface-sunken/50 px-3 py-2",
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
    weekday: "short",
    month: "short",
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
