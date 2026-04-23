/**
 * Dispatch Monitor — Phase B Session 1.
 *
 * Three-day read-mostly Pulse surface for dispatchers. Today,
 * Tomorrow, Two days out, each with driver-lane kanban of
 * kanban-scheduling deliveries. Real Sunnycrest-shaped data.
 *
 * Per SPACES_PLAN Option 1: this is NOT a Space. It's a route that
 * prepares to become the primary Operational-layer component of
 * Home Pulse for the (manufacturing, dispatcher) role when Phase D
 * ships the composition engine. Today it's reached via:
 *
 *   - direct URL `/dispatch/monitor`
 *   - command bar action "show dispatch monitor" (Phase 3d)
 *   - future: Pulse composition default (Phase D)
 *
 * No DotNav entry, no Space registration.
 *
 * Supports:
 *   - Click card → QuickEditDialog (time / driver / hole-dug / note)
 *   - Drag card between driver lanes within the same day (DnD via
 *     @dnd-kit)
 *   - Finalize button per day (draft → finalized)
 *   - Hole-dug quick toggle via card badge cycle
 *   - Ancillary +N badge with inline expand per parent
 *   - Revert confirmation whenever an edit happens on a finalized day
 *
 * Data fetching: plain axios via `dispatch-service.ts`, reloaded on
 * action. No TanStack.
 */

import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { RefreshCwIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { MonitorDayColumn } from "@/components/dispatch/MonitorDayColumn"
import {
  QuickEditDialog,
  type QuickEditSavePayload,
} from "@/components/dispatch/QuickEditDialog"
import {
  fetchDeliveriesForRange,
  fetchDrivers,
  fetchScheduleRange,
  finalizeSchedule,
  revertSchedule,
  updateDelivery,
  updateHoleDug,
  type DeliveryDTO,
  type DriverDTO,
  type HoleDugStatus,
  type ScheduleStateDTO,
} from "@/services/dispatch-service"
import { cn } from "@/lib/utils"


const DAY_COUNT = 3  // Today, Tomorrow, Two days out


function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}


function buildDays(startDate: Date, n: number): string[] {
  const out: string[] = []
  for (let i = 0; i < n; i++) {
    const d = new Date(startDate)
    d.setDate(startDate.getDate() + i)
    out.push(isoDate(d))
  }
  return out
}


function labelForOffset(offset: number): string {
  if (offset === 0) return "Today"
  if (offset === 1) return "Tomorrow"
  if (offset === 2) return "Two days out"
  return `+${offset} days`
}


export default function DispatchMonitorPage() {
  const navigate = useNavigate()

  // Days the Monitor renders. Anchored to the moment the page loads
  // (not re-derived on every render) so a resize doesn't trigger a
  // day-boundary shift mid-session.
  const [anchor] = useState<Date>(() => new Date())
  const days = useMemo(() => buildDays(anchor, DAY_COUNT), [anchor])
  const start = days[0]
  const end = days[days.length - 1]

  // Data state
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [schedules, setSchedules] = useState<Map<string, ScheduleStateDTO>>(
    () => new Map(),
  )
  const [deliveries, setDeliveries] = useState<DeliveryDTO[]>([])
  const [drivers, setDrivers] = useState<DriverDTO[]>([])

  // Quick-edit state
  const [editTarget, setEditTarget] = useState<DeliveryDTO | null>(null)

  // Refresh counter — bumping triggers reload.
  const [refreshCount, setRefreshCount] = useState(0)

  // Initial load + reload on refresh.
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      fetchScheduleRange(start, end),
      fetchDeliveriesForRange({ start, end }),
      fetchDrivers(),
    ])
      .then(([schedRange, deliveriesList, driversList]) => {
        if (cancelled) return
        const map = new Map<string, ScheduleStateDTO>()
        for (const s of schedRange.schedules) map.set(s.schedule_date, s)
        // Fill missing days with placeholder not_created entries
        // so every day has a known state for rendering.
        for (const d of days) {
          if (!map.has(d)) {
            map.set(d, {
              id: null,
              company_id: null,
              schedule_date: d,
              state: "not_created",
              finalized_at: null,
              finalized_by_user_id: null,
              auto_finalized: false,
              last_reverted_at: null,
              last_revert_reason: null,
              created_at: null,
              updated_at: null,
            })
          }
        }
        setSchedules(map)
        setDeliveries(deliveriesList)
        setDrivers(driversList)
      })
      .catch((e) => {
        if (cancelled) return
        console.error("dispatch monitor load failed:", e)
        setError("Couldn't load the dispatch monitor. Try refreshing.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [start, end, refreshCount, days])

  // ── Derived data — split deliveries into per-day groups + ancillary maps
  const { deliveriesByDate, ancillaryCountsByDate, ancillariesByParent } =
    useMemo(() => {
      const byDate = new Map<string, DeliveryDTO[]>()
      const parentCounts = new Map<string, number>()
      const parentMap = new Map<string, DeliveryDTO[]>()

      for (const d of deliveries) {
        if (!d.requested_date) continue
        if (!byDate.has(d.requested_date)) byDate.set(d.requested_date, [])
        byDate.get(d.requested_date)!.push(d)

        // Ancillary attachment: conservatively attach to parent by
        // order_id — any delivery sharing an order_id with an
        // ancillary delivery is treated as the parent. Simple +N
        // attach rule sufficient for B.1; refined attachment is
        // Phase 4 scope.
        if (
          d.scheduling_type === "ancillary" ||
          d.scheduling_type === "direct_ship"
        ) {
          if (d.order_id) {
            // Find the kanban delivery with the same order_id as
            // parent (if any)
            const parent = deliveries.find(
              (p) =>
                p.scheduling_type === "kanban" && p.order_id === d.order_id,
            )
            if (parent) {
              parentCounts.set(
                parent.id,
                (parentCounts.get(parent.id) ?? 0) + 1,
              )
              if (!parentMap.has(parent.id)) parentMap.set(parent.id, [])
              parentMap.get(parent.id)!.push(d)
            }
          }
        }
      }
      return {
        deliveriesByDate: byDate,
        ancillaryCountsByDate: parentCounts,
        ancillariesByParent: parentMap,
      }
    }, [deliveries])

  // ── Actions ────────────────────────────────────────────────────────

  const reload = useCallback(() => setRefreshCount((n) => n + 1), [])

  const handleFinalize = useCallback(
    async (dateStr: string) => {
      try {
        await finalizeSchedule(dateStr)
        reload()
      } catch (e) {
        console.error("finalize failed:", e)
        alert("Couldn't finalize. Try again.")
      }
    },
    [reload],
  )

  const handleOpenScheduling = useCallback(
    (dateStr: string) => {
      // Phase 4 mounts the Scheduling Focus at Cmd+K; for now route
      // to the existing scheduling board with a date param. That
      // surface still exists pre-Focus-migration.
      navigate(`/delivery/scheduling-board?date=${dateStr}`)
    },
    [navigate],
  )

  const handleCycleHoleDug = useCallback(
    async (delivery: DeliveryDTO, next: HoleDugStatus) => {
      // Optimistic UI
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === delivery.id ? { ...d, hole_dug_status: next } : d,
        ),
      )
      try {
        await updateHoleDug(delivery.id, next)
        // Hole-dug may have reverted the schedule server-side; reload
        // schedule state (cheap) to reflect.
        reload()
      } catch (e) {
        console.error("hole-dug update failed:", e)
        // Revert optimistic change
        reload()
      }
    },
    [reload],
  )

  const handleSaveEdit = useCallback(
    async (payload: QuickEditSavePayload) => {
      const delivery = deliveries.find((d) => d.id === payload.deliveryId)
      if (!delivery) return
      // Build the patch. Preserves existing type_config keys + updates
      // service_time via the same bag.
      const existingTc = delivery.type_config ?? {}
      const nextTc = {
        ...existingTc,
        service_time: payload.serviceTime,
      }
      try {
        await updateDelivery(payload.deliveryId, {
          assigned_driver_id: payload.assignedDriverId,
          special_instructions: payload.note,
          type_config: nextTc,
        })
        if (payload.holeDugStatus !== delivery.hole_dug_status) {
          await updateHoleDug(payload.deliveryId, payload.holeDugStatus)
        }
        setEditTarget(null)
        reload()
      } catch (e) {
        console.error("quick-edit save failed:", e)
        alert("Couldn't save the edit. Try again.")
      }
    },
    [deliveries, reload],
  )

  // Drag within-day reassign.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      const { active, over } = ev
      if (!over) return
      const deliveryId = String(active.id).replace(/^delivery:/, "")
      const laneKey = String(over.id)
      // laneKey format: "YYYY-MM-DD:<driverId|__UNASSIGNED__>"
      const sep = laneKey.indexOf(":")
      if (sep === -1) return
      const targetDriverRaw = laneKey.slice(sep + 1)
      const targetDriverId =
        targetDriverRaw === "__UNASSIGNED__" ? null : targetDriverRaw

      const delivery = deliveries.find((d) => d.id === deliveryId)
      if (!delivery) return
      if (delivery.assigned_driver_id === targetDriverId) return

      // Optimistic
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === deliveryId
            ? { ...d, assigned_driver_id: targetDriverId }
            : d,
        ),
      )
      try {
        await updateDelivery(deliveryId, {
          assigned_driver_id: targetDriverId,
        })
        reload()
      } catch (e) {
        console.error("driver reassign failed:", e)
        reload()
      }
    },
    [deliveries, reload],
  )

  // ── Render ─────────────────────────────────────────────────────────

  const dispatcherNameById = useMemo(() => {
    // Resolve finalized-by user id → driver display name when possible;
    // in practice the dispatcher is rarely a driver but this gives a
    // fallback. For pure-dispatcher attribution the name isn't
    // resolvable without a user lookup endpoint; display "Finalized
    // at {time}" attribution in MonitorDayColumn.
    return new Map<string, string>()
  }, [])

  return (
    <div
      data-slot="dispatch-monitor-page"
      className={cn(
        "mx-auto max-w-[1800px] p-4 sm:p-6 lg:p-8",
        "font-plex-sans text-content-base",
      )}
    >
      {/* Header */}
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h2 font-medium text-content-strong font-plex-serif">
            Dispatch monitor
          </h1>
          <p className="mt-1 text-body-sm text-content-muted">
            Three-day view. Drag cards between drivers within a day.
            Click any card to quick-edit. Finalize locks in tomorrow's
            work so drivers can plan their morning.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={reload}
          disabled={loading}
          data-slot="dispatch-monitor-refresh"
        >
          <RefreshCwIcon
            className={cn("h-4 w-4", loading && "animate-spin")}
            aria-hidden
          />
          Refresh
        </Button>
      </header>

      {/* Loading / error */}
      {loading && (
        <div
          data-slot="dispatch-monitor-loading"
          className="py-16 text-center text-body-sm text-content-muted"
        >
          Loading schedule…
        </div>
      )}
      {error && (
        <div
          role="alert"
          data-slot="dispatch-monitor-error"
          className={cn(
            "mb-4 rounded border p-3",
            "bg-status-error-muted border-status-error/30 text-status-error",
          )}
        >
          {error}
        </div>
      )}

      {!loading && !error && (
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div
            data-slot="dispatch-monitor-grid"
            className={cn(
              // Three-day grid on lg+, stacked below.
              "grid gap-4",
              "grid-cols-1 lg:grid-cols-3",
            )}
          >
            {days.map((dateStr, offset) => {
              const schedule = schedules.get(dateStr)!
              const dayDeliveries = deliveriesByDate.get(dateStr) ?? []
              const finalizedByLabel =
                schedule.finalized_by_user_id
                  ? dispatcherNameById.get(schedule.finalized_by_user_id) ??
                    null
                  : schedule.auto_finalized
                  ? "Auto-finalized"
                  : null
              return (
                <MonitorDayColumn
                  key={dateStr}
                  dateStr={dateStr}
                  dayLabel={labelForOffset(offset)}
                  schedule={schedule}
                  deliveries={dayDeliveries}
                  drivers={drivers}
                  ancillaryCounts={ancillaryCountsByDate}
                  ancillariesByParent={ancillariesByParent}
                  onOpenEdit={setEditTarget}
                  onCycleHoleDug={handleCycleHoleDug}
                  onFinalize={handleFinalize}
                  onOpenScheduling={handleOpenScheduling}
                  finalizedByLabel={finalizedByLabel}
                />
              )
            })}
          </div>
        </DndContext>
      )}

      {/* Quick-edit dialog */}
      <QuickEditDialog
        delivery={editTarget}
        drivers={drivers}
        scheduleFinalized={
          editTarget
            ? schedules.get(editTarget.requested_date ?? "")?.state === "finalized"
            : false
        }
        onClose={() => setEditTarget(null)}
        onSave={handleSaveEdit}
      />
    </div>
  )
}


// Side-effect export — marking that a delivery update on a finalized
// day triggers a server-side revert in `delivery_service.update_
// delivery`. The dialog warns the user pre-save; the actual revert
// happens in the patch call. This keeps the client simple: send the
// update, trust the backend to revert, reload schedule state.
export { revertSchedule }
