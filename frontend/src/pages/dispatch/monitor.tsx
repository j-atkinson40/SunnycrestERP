/**
 * Dispatch Monitor — Phase B Session 1 (Phase 3.2 rebuild).
 *
 * Single-day default with Smart Stack navigation. Multi-day "show
 * all days" opt-in via URL param + Cmd+K.
 *
 *   - Default: ONE day visible at a time, full horizontal driver
 *     kanban per day. Vertical scroll-snap cycles between days
 *     (iOS-Smart-Stack pattern reused from Focus primitive).
 *   - Time-based initial day: before 1pm tenant-local → Today is
 *     primary; after 1pm → Tomorrow is primary ("ops has shifted to
 *     tomorrow's planning by afternoon"). Tenant-local time comes
 *     from `/dispatch/tenant-time` — server authoritative, no
 *     reliance on browser clock.
 *   - Multi-day: toggle in the header OR Cmd+K action "show all days".
 *     Stacks every day vertically without scroll-snap. Good for "let
 *     me see the whole week at once" moments.
 *   - URL state: `?view=all` = multi; default (no param) = single.
 *     `?day=YYYY-MM-DD` deep-links to a specific day in single mode.
 *     No localStorage persistence — reload of `/dispatch/monitor`
 *     with no params reverts to the time-based default (per user
 *     spec).
 *
 * Per SPACES_PLAN Option 1: this is NOT a Space. It's a route that
 * prepares to become the primary Operational-layer component of
 * Home Pulse for the (manufacturing, dispatcher) role when Phase D
 * ships the composition engine. Today it's reached via direct URL,
 * command bar action, and future Pulse composition default.
 */

import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import {
  ChevronDownIcon,
  ChevronUpIcon,
  LayersIcon,
  RefreshCwIcon,
  RowsIcon,
} from "lucide-react"

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
  fetchTenantTime,
  finalizeSchedule,
  revertSchedule,
  updateDelivery,
  updateHoleDug,
  type DeliveryDTO,
  type DriverDTO,
  type HoleDugStatus,
  type ScheduleStateDTO,
  type TenantTimeDTO,
} from "@/services/dispatch-service"
import { cn } from "@/lib/utils"


const DAY_COUNT = 4  // Today, Tomorrow, +2, +3. Larger window than
                     // Phase 3 so the Smart Stack has enough "throw"
                     // to feel like a stack, not a pair.

/** After 1pm tenant-local, "primary" shifts to tomorrow — drivers plan
 *  the next morning, auto-finalize fires at 1pm. Pure integer threshold
 *  (0–23). Exported for tests. */
export const TIME_BASED_DEFAULT_PIVOT_HOUR = 13


function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}


function buildDaysFromLocalDate(localDate: string, n: number): string[] {
  const [y, m, d] = localDate.split("-").map(Number)
  const base = new Date(y, (m ?? 1) - 1, d ?? 1)
  const out: string[] = []
  for (let i = 0; i < n; i++) {
    const dt = new Date(base)
    dt.setDate(base.getDate() + i)
    out.push(isoDate(dt))
  }
  return out
}


function labelForOffset(offset: number): string {
  if (offset === 0) return "Today"
  if (offset === 1) return "Tomorrow"
  if (offset === 2) return "Two days out"
  if (offset === 3) return "Three days out"
  return `+${offset} days`
}


/** Pick the Smart Stack default day. Before 1pm tenant-local → Today
 *  (offset 0); at/after 1pm → Tomorrow (offset 1). Exported for tests. */
export function pickDefaultDayIndex(localHour: number): number {
  return localHour < TIME_BASED_DEFAULT_PIVOT_HOUR ? 0 : 1
}


type ViewMode = "single" | "all"


export default function DispatchMonitorPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // URL-derived state.
  const urlView = searchParams.get("view")
  const viewMode: ViewMode = urlView === "all" ? "all" : "single"
  const urlDay = searchParams.get("day")

  // Tenant time — picks time-based default day + anchors the day window
  // to the tenant-local calendar (not the browser's).
  const [tenantTime, setTenantTime] = useState<TenantTimeDTO | null>(null)
  useEffect(() => {
    let cancelled = false
    fetchTenantTime()
      .then((t) => {
        if (!cancelled) setTenantTime(t)
      })
      .catch((e) => {
        // Fall back to browser clock silently — rare case (dispatcher's
        // tenant has no Company.timezone set + fallback was rejected).
        console.warn("tenant-time fetch failed, using browser clock:", e)
        if (cancelled) return
        const now = new Date()
        setTenantTime({
          tenant_timezone: "local-browser",
          local_iso: now.toISOString(),
          local_date: isoDate(now),
          local_hour: now.getHours(),
          local_minute: now.getMinutes(),
        })
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Days the Monitor renders — computed from tenant-local today
  // once we have tenant time. No tenantTime yet = empty array (we
  // show a loading skeleton until resolve).
  const days = useMemo(() => {
    if (!tenantTime) return [] as string[]
    return buildDaysFromLocalDate(tenantTime.local_date, DAY_COUNT)
  }, [tenantTime])

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

  // Initial load + reload on refresh (gated on tenantTime resolve).
  useEffect(() => {
    if (!start || !end) return
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

  // ── Derived data ──
  const { deliveriesByDate, ancillaryCountsByDate, ancillariesByParent } =
    useMemo(() => {
      const byDate = new Map<string, DeliveryDTO[]>()
      const parentCounts = new Map<string, number>()
      const parentMap = new Map<string, DeliveryDTO[]>()
      for (const d of deliveries) {
        if (!d.requested_date) continue
        if (!byDate.has(d.requested_date)) byDate.set(d.requested_date, [])
        byDate.get(d.requested_date)!.push(d)
        if (
          d.scheduling_type === "ancillary" ||
          d.scheduling_type === "direct_ship"
        ) {
          if (d.order_id) {
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

  // ── Single-day Smart Stack primary day index ──────────────────────
  //
  // In single-day mode, track which day is "active" (the one in the
  // viewport). Driven by IntersectionObserver on the per-day panes.
  // Initial selection derives from URL ?day=... if present, else the
  // time-based default.
  const [activeDayIndex, setActiveDayIndex] = useState<number>(0)
  const dayPaneRefs = useRef<Array<HTMLDivElement | null>>([])
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)

  // Resolve initial single-day primary once both `days` + `tenantTime`
  // are available. Runs once per tenant-time/days change (no ongoing
  // observer fighting).
  const [initialAlignDone, setInitialAlignDone] = useState(false)
  useEffect(() => {
    if (viewMode !== "single") return
    if (!tenantTime || days.length === 0) return
    if (initialAlignDone) return
    let targetIdx: number
    if (urlDay) {
      const hit = days.indexOf(urlDay)
      targetIdx = hit >= 0 ? hit : pickDefaultDayIndex(tenantTime.local_hour)
    } else {
      targetIdx = pickDefaultDayIndex(tenantTime.local_hour)
    }
    setActiveDayIndex(targetIdx)
    // Scroll the target day into view on initial mount. requestAnimation-
    // Frame so the pane refs are populated.
    requestAnimationFrame(() => {
      const el = dayPaneRefs.current[targetIdx]
      if (el) el.scrollIntoView({ block: "start", behavior: "instant" as ScrollBehavior })
      setInitialAlignDone(true)
    })
  }, [viewMode, tenantTime, days, urlDay, initialAlignDone])

  // IntersectionObserver tracks which single-day pane is active.
  // Updates URL ?day= so refresh preserves the view and Cmd+K "go to
  // tomorrow" can navigate via the URL. Skipped in multi-day mode.
  useEffect(() => {
    if (viewMode !== "single") return
    if (!scrollContainerRef.current) return
    if (typeof IntersectionObserver === "undefined") return
    if (days.length === 0) return
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting && e.intersectionRatio > 0.55) {
            const idx = Number(
              (e.target as HTMLElement).dataset.dayIndex ?? -1,
            )
            if (idx >= 0) {
              setActiveDayIndex(idx)
              const dateStr = days[idx]
              if (dateStr && dateStr !== searchParams.get("day")) {
                const sp = new URLSearchParams(searchParams)
                sp.set("day", dateStr)
                setSearchParams(sp, { replace: true })
              }
            }
          }
        }
      },
      { root: scrollContainerRef.current, threshold: [0.55] },
    )
    dayPaneRefs.current.forEach((el) => el && observer.observe(el))
    return () => observer.disconnect()
  }, [viewMode, days, searchParams, setSearchParams])

  // ── Actions ──
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
      navigate(`/delivery/scheduling-board?date=${dateStr}`)
    },
    [navigate],
  )

  const handleCycleHoleDug = useCallback(
    async (delivery: DeliveryDTO, next: HoleDugStatus) => {
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === delivery.id ? { ...d, hole_dug_status: next } : d,
        ),
      )
      try {
        await updateHoleDug(delivery.id, next)
        reload()
      } catch (e) {
        console.error("hole-dug update failed:", e)
        reload()
      }
    },
    [reload],
  )

  const handleSaveEdit = useCallback(
    async (payload: QuickEditSavePayload) => {
      const delivery = deliveries.find((d) => d.id === payload.deliveryId)
      if (!delivery) return
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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      const { active, over } = ev
      if (!over) return
      const deliveryId = String(active.id).replace(/^delivery:/, "")
      const laneKey = String(over.id)
      const sep = laneKey.indexOf(":")
      if (sep === -1) return
      const targetDriverRaw = laneKey.slice(sep + 1)
      const targetDriverId =
        targetDriverRaw === "__UNASSIGNED__" ? null : targetDriverRaw
      const delivery = deliveries.find((d) => d.id === deliveryId)
      if (!delivery) return
      if (delivery.assigned_driver_id === targetDriverId) return
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

  // View mode toggle — updates URL state. Clears ?day= when switching
  // to all (not meaningful in multi-day).
  const setViewMode = useCallback(
    (next: ViewMode) => {
      const sp = new URLSearchParams(searchParams)
      if (next === "all") {
        sp.set("view", "all")
        sp.delete("day")
      } else {
        sp.delete("view")
      }
      setSearchParams(sp, { replace: false })
    },
    [searchParams, setSearchParams],
  )

  // Prev / next day helpers for single mode.
  const goToDay = useCallback(
    (idx: number) => {
      if (idx < 0 || idx >= days.length) return
      const el = dayPaneRefs.current[idx]
      if (el) el.scrollIntoView({ block: "start", behavior: "smooth" })
    },
    [days.length],
  )

  // Keyboard navigation in single mode — arrow keys + j/k for
  // dispatchers on keyboards.
  useEffect(() => {
    if (viewMode !== "single") return
    const onKey = (e: KeyboardEvent) => {
      // Ignore when typing in an input / textarea / contenteditable
      const tgt = e.target as HTMLElement | null
      if (!tgt) return
      const tag = tgt.tagName
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tgt.isContentEditable
      )
        return
      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault()
        goToDay(Math.min(activeDayIndex + 1, days.length - 1))
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault()
        goToDay(Math.max(activeDayIndex - 1, 0))
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [viewMode, activeDayIndex, days.length, goToDay])

  // ── Render ──────────────────────────────────────────────────────────
  const dispatcherNameById = useMemo(
    () => new Map<string, string>(),
    [],
  )

  const activeDayLabel =
    viewMode === "single" && days.length > 0
      ? labelForOffset(activeDayIndex)
      : null

  return (
    <div
      data-slot="dispatch-monitor-page"
      data-view-mode={viewMode}
      className={cn(
        "mx-auto max-w-[1800px] p-4 sm:p-6 lg:p-8",
        "font-plex-sans text-content-base",
      )}
    >
      {/* Header */}
      <header className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-h2 font-medium text-content-strong font-plex-serif">
            Dispatch monitor
          </h1>
          <p className="mt-1 text-body-sm text-content-muted">
            {viewMode === "single"
              ? `Focused on ${activeDayLabel ?? "today"}. Scroll or ↑↓ to switch days.`
              : `All ${DAY_COUNT} days stacked. Switch to single-day for focus.`}
          </p>
        </div>
        <div className="flex flex-none items-center gap-2">
          <div
            role="tablist"
            aria-label="Monitor view mode"
            className={cn(
              "inline-flex items-center rounded-md border border-border-subtle",
              "bg-surface-elevated p-0.5",
            )}
          >
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === "single"}
              onClick={() => setViewMode("single")}
              data-slot="dispatch-monitor-view-single"
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-2.5 py-1",
                "text-caption font-medium",
                "focus-ring-brass outline-none transition-colors duration-quick",
                viewMode === "single"
                  ? "bg-brass text-content-on-brass"
                  : "text-content-muted hover:text-content-strong",
              )}
            >
              <LayersIcon className="h-3.5 w-3.5" aria-hidden />
              Single day
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === "all"}
              onClick={() => setViewMode("all")}
              data-slot="dispatch-monitor-view-all"
              className={cn(
                "inline-flex items-center gap-1.5 rounded px-2.5 py-1",
                "text-caption font-medium",
                "focus-ring-brass outline-none transition-colors duration-quick",
                viewMode === "all"
                  ? "bg-brass text-content-on-brass"
                  : "text-content-muted hover:text-content-strong",
              )}
            >
              <RowsIcon className="h-3.5 w-3.5" aria-hidden />
              All days
            </button>
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
        </div>
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

      {!loading && !error && days.length > 0 && (
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          {viewMode === "single" ? (
            <div className="flex items-stretch gap-3">
              {/* Dots indicator column — left rail, one per day */}
              <nav
                aria-label="Day navigation"
                data-slot="dispatch-monitor-dots"
                className="sticky top-4 flex flex-col items-center gap-1.5 self-start"
              >
                <button
                  type="button"
                  onClick={() => goToDay(activeDayIndex - 1)}
                  disabled={activeDayIndex === 0}
                  aria-label="Previous day"
                  className={cn(
                    "inline-flex h-6 w-6 items-center justify-center rounded-sm",
                    "text-content-muted hover:text-content-strong",
                    "focus-ring-brass outline-none",
                    "disabled:opacity-40 disabled:cursor-not-allowed",
                  )}
                >
                  <ChevronUpIcon className="h-4 w-4" aria-hidden />
                </button>
                {days.map((dateStr, idx) => (
                  <button
                    key={dateStr}
                    type="button"
                    role="tab"
                    aria-selected={idx === activeDayIndex}
                    aria-label={`Go to ${labelForOffset(idx)}`}
                    onClick={() => goToDay(idx)}
                    data-slot="dispatch-monitor-day-dot"
                    data-day-index={idx}
                    className={cn(
                      "h-2 w-2 rounded-full transition-colors duration-quick ease-settle",
                      idx === activeDayIndex
                        ? "bg-brass"
                        : "bg-border-subtle hover:bg-content-muted",
                      "focus-ring-brass outline-none",
                    )}
                  />
                ))}
                <button
                  type="button"
                  onClick={() => goToDay(activeDayIndex + 1)}
                  disabled={activeDayIndex >= days.length - 1}
                  aria-label="Next day"
                  className={cn(
                    "inline-flex h-6 w-6 items-center justify-center rounded-sm",
                    "text-content-muted hover:text-content-strong",
                    "focus-ring-brass outline-none",
                    "disabled:opacity-40 disabled:cursor-not-allowed",
                  )}
                >
                  <ChevronDownIcon className="h-4 w-4" aria-hidden />
                </button>
              </nav>

              {/* Scroll container — each day pane fills the viewport
                  height so scroll-snap settles on one day at a time
                  (same CSS technique as Focus StackRail). */}
              <div
                ref={scrollContainerRef}
                data-slot="dispatch-monitor-stack"
                className={cn(
                  "flex-1 overflow-y-auto",
                  "scroll-smooth",
                )}
                style={{
                  // Slightly less than 100vh so the header stays above
                  // the scroll region. The value matches the p-4/p-6/p-8
                  // container padding + header height roughly.
                  height: "calc(100vh - 12rem)",
                  scrollSnapType: "y mandatory",
                }}
              >
                {days.map((dateStr, idx) => {
                  const schedule = schedules.get(dateStr)!
                  const dayDeliveries = deliveriesByDate.get(dateStr) ?? []
                  const finalizedByLabel =
                    schedule.finalized_by_user_id
                      ? dispatcherNameById.get(
                          schedule.finalized_by_user_id,
                        ) ?? null
                      : schedule.auto_finalized
                      ? "Auto-finalized"
                      : null
                  return (
                    <div
                      key={dateStr}
                      ref={(el) => {
                        dayPaneRefs.current[idx] = el
                      }}
                      data-slot="dispatch-monitor-day-pane"
                      data-day-index={idx}
                      data-day-date={dateStr}
                      className="mb-4 snap-start"
                      style={{
                        // Match the scroll container's height so each
                        // pane IS one scroll-snap "page".
                        minHeight: "100%",
                      }}
                    >
                      <MonitorDayColumn
                        dateStr={dateStr}
                        dayLabel={labelForOffset(idx)}
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
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            /* Multi-day — plain vertical stack, no scroll-snap.
               "Show me the whole week at once" view. */
            <div
              data-slot="dispatch-monitor-all-days"
              className="space-y-4"
            >
              {days.map((dateStr, idx) => {
                const schedule = schedules.get(dateStr)!
                const dayDeliveries = deliveriesByDate.get(dateStr) ?? []
                const finalizedByLabel =
                  schedule.finalized_by_user_id
                    ? dispatcherNameById.get(
                        schedule.finalized_by_user_id,
                      ) ?? null
                    : schedule.auto_finalized
                    ? "Auto-finalized"
                    : null
                return (
                  <MonitorDayColumn
                    key={dateStr}
                    dateStr={dateStr}
                    dayLabel={labelForOffset(idx)}
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
          )}
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
// delivery`.
export { revertSchedule }
