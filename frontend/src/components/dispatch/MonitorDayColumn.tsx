/**
 * MonitorDayColumn — one day's column in the three-day Dispatch
 * Monitor. Carries:
 *
 *   - Day header: weekday label + date + schedule-state badge
 *     (DRAFT / Finalized) + affordance (Finalize / Open Scheduling)
 *   - Driver-lane kanban body: one lane per driver + one
 *     "Unassigned" lane on top
 *   - Within-day drag: cards drop onto driver lanes via @dnd-kit
 *     `useDroppable`. Drop inside a different lane fires the
 *     onReassignDriver callback; no-op if the drop is on the same
 *     lane.
 *   - Empty-state: when no rows exist for this day, a "No schedule
 *     yet" placeholder with an Open Scheduling affordance.
 *
 * Schedule state surfaces visually:
 *   - Draft   → amber "DRAFT" badge + Finalize button in header
 *   - Finalized → "Finalized by {name} at {time}" attribution + no
 *                 Finalize button (still editable; any save triggers
 *                 revert-confirmation per QuickEditDialog)
 *   - not_created → "No schedule yet" with Open Scheduling button
 *
 * Cards render via <DeliveryCard>. Ancillary badge + expand state
 * live in this component (so expansion is per-day scoped).
 */

import { useMemo, useState } from "react"
import { useDroppable } from "@dnd-kit/core"
import { ClockIcon, CalendarIcon, CheckCircle2Icon } from "lucide-react"

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

  // ── Header ─────────────────────────────────────────────────────────
  const dateDisplay = formatDateDisplay(dateStr)

  return (
    <div
      data-slot="dispatch-day-column"
      data-date={dateStr}
      data-schedule-state={schedule.state}
      className={cn(
        "flex flex-col min-w-0 rounded-md border border-border-subtle",
        "bg-surface-sunken shadow-level-1",
      )}
    >
      {/* Day header */}
      <div
        data-slot="dispatch-day-header"
        className="flex items-start justify-between gap-3 border-b border-border-subtle px-3 py-3"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-h4 font-medium text-content-strong">
              {dayLabel}
            </h3>
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
          <div className="mt-0.5 flex items-center gap-1 text-caption text-content-muted">
            <CalendarIcon className="h-3 w-3" aria-hidden />
            {dateDisplay}
          </div>
          {finalized && schedule.finalized_at && (
            <div
              data-slot="dispatch-day-finalized-attribution"
              className="mt-1 flex items-center gap-1 text-caption text-status-success"
            >
              <CheckCircle2Icon className="h-3 w-3" aria-hidden />
              {finalizedByLabel ??
                `Finalized ${formatTime(schedule.finalized_at)}`}
            </div>
          )}
        </div>
        <div className="flex flex-none gap-2">
          {schedule.state === "draft" && (
            <Button
              size="sm"
              onClick={handleFinalizeClick}
              disabled={finalizing}
              data-slot="dispatch-day-finalize-btn"
            >
              {finalizing ? "Finalizing…" : `Finalize ${dayLabel}`}
            </Button>
          )}
          {notCreated && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onOpenScheduling(dateStr)}
              data-slot="dispatch-day-open-scheduling-btn"
            >
              Open scheduling
            </Button>
          )}
        </div>
      </div>

      {/* Body — driver lanes + unassigned lane */}
      {notCreated || (deliveries.length === 0 && !notCreated) ? (
        <div
          data-slot="dispatch-day-empty"
          className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-8 text-center"
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
        <div className="flex-1 space-y-3 p-3">
          {/* Unassigned lane (only if any kanban cards are unassigned) */}
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

          {/* Driver lanes */}
          {drivers.map((driver) => {
            const laneDeliveries = kanbanByDriver.get(driver.id) ?? []
            if (laneDeliveries.length === 0) return null
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

          {/* When all drivers are empty we still want the column to
              remain useful visually — show a hint. */}
          {Array.from(kanbanByDriver.entries()).every(
            ([, list]) => list.length === 0,
          ) &&
            unassignedKanban.length === 0 && (
              <div className="py-8 text-center text-body-sm text-content-muted">
                No kanban deliveries for this day.
              </div>
            )}
        </div>
      )}
    </div>
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
        "rounded border border-border-subtle bg-surface-elevated",
        "transition-colors duration-quick ease-settle",
        isOver && "ring-2 ring-brass ring-offset-1 ring-offset-surface-sunken",
        isUnassignedLane && "border-dashed",
      )}
    >
      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
        <ClockIcon
          className="h-3.5 w-3.5 text-content-muted flex-none"
          aria-hidden
        />
        <span className="text-body-sm font-medium text-content-strong">
          {laneLabel}
        </span>
        <span className="ml-auto text-caption text-content-muted">
          {deliveries.length}{" "}
          {deliveries.length === 1 ? "delivery" : "deliveries"}
        </span>
      </div>
      <div className="space-y-2 p-2">
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
