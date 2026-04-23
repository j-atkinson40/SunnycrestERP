/**
 * Funeral Schedule — dispatch Pulse widget for the (manufacturing,
 * dispatcher) role. Phase B Session 1 + 3.2.1 rotation + 3.3 surface
 * polish + 3.3.1 rename.
 *
 * **Terminology note (Phase 3.3.1, 2026-04-23):** This widget is the
 * "Funeral Schedule." In Bridgeable architecture, "Monitor" is the
 * architectural noun for Pulse's purpose (monitoring), NOT a component
 * name. Redi-Rock Schedule and Wastewater Schedule will be distinct
 * widgets with their own names. Previously called "Dispatch Monitor"
 * (Phase 3.0–3.3); renamed for terminology discipline.
 *
 * Single-day default with iOS-style Smart Stack rotation. Multi-day
 * "show all days" opt-in via URL param + Cmd+K.
 *
 * **Phase 3.2.1 change (2026-04-23)**: Phase 3.2 shipped Smart Stack
 * as vertically-stacked scroll-snap panes. User feedback: behavior
 * doesn't match iOS Smart Stack — content should rotate in place
 * rather than the page scrolling. Rebuilt with a single fixed-position
 * "day stage" containing all days as absolute-positioned layers;
 * transform translateY slides the active day into view while the
 * previous day slides out. Page does NOT scroll during day rotation.
 * Horizontal scroll within a day (driver lanes) preserved for that
 * dimension. Vertical scroll within a lane (when lane content exceeds
 * stage height) preserved via boundary-escalation wheel handling —
 * lane scrolls first; when at boundary, stage rotates.
 *
 * **Phase 3.3.1 change (2026-04-23)**: rotation physics tuned from
 * `duration-settle ease-settle` (300ms, cubic-bezier(0.2, 0, 0.1, 1))
 * to 380ms cubic-bezier(0.32, 0.72, 0, 1) — iOS Smart Stack spring
 * approximation. Duration bumped for physical weight; curve has more
 * momentum-settle character than the canonical arrival curve.
 * Empty driver columns hide by default, reveal during active drag
 * as drop targets — surface shows what IS; interaction reveals
 * affordances.
 *
 *   - **Default:** ONE day visible at a time, full horizontal driver
 *     kanban per day. Scroll wheel / swipe / arrow keys / dot clicks
 *     rotate content within a fixed stage; page does not scroll.
 *   - **Time-based initial day:** before 1pm tenant-local → Today is
 *     primary; after 1pm → Tomorrow is primary ("ops has shifted to
 *     tomorrow's planning by afternoon"). Tenant-local time comes
 *     from `/dispatch/tenant-time` — server authoritative, no
 *     reliance on browser clock.
 *   - **Multi-day:** toggle in the header OR Cmd+K action "show all
 *     days". Stacks every day vertically as normal page scroll (NOT
 *     Smart Stack — intentional; the multi-day mode is for "let me
 *     see the whole week at once" which requires all content visible
 *     simultaneously).
 *   - **URL state:** `?view=all` = multi; default (no param) = single.
 *     `?day=YYYY-MM-DD` deep-links to a specific day in single mode.
 *     No localStorage persistence — reload of `/dispatch/funeral-
 *     schedule` with no params reverts to the time-based default
 *     (per user spec).
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
import { FuneralScheduleDayColumn } from "@/components/dispatch/FuneralScheduleDayColumn"
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


export default function FuneralSchedulePage() {
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

  // ── Single-day Smart Stack rotation state ─────────────────────────
  //
  // Phase 3.2.1: rotation-in-place. `activeDayIndex` is the single
  // source of truth for which day is on the stage. Changing it
  // animates the transform translateY on all day layers — the prior
  // active day slides out, the new one slides in. No scroll-snap, no
  // IntersectionObserver — the index IS the state.
  const [activeDayIndex, setActiveDayIndex] = useState<number>(0)
  const stageRef = useRef<HTMLDivElement | null>(null)

  // Wheel/touch gesture state — used by the gesture-capture handlers
  // below to trigger rotation without scrolling the page.
  const wheelAccumRef = useRef(0)
  const wheelEndTimerRef = useRef<number | null>(null)
  const lastRotationAtRef = useRef(0)
  const touchStartRef = useRef<{ x: number; y: number } | null>(null)

  const WHEEL_THRESHOLD = 50              // pixels of accumulated deltaY
  const SWIPE_THRESHOLD = 40              // pixels of vertical pointer delta
  const ROTATION_COOLDOWN_MS = 350        // matches CSS transition duration

  // Resolve initial day from URL or time-based default. Runs once per
  // tenant-time/days resolution.
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
    setInitialAlignDone(true)
  }, [viewMode, tenantTime, days, urlDay, initialAlignDone])

  // Rotation helper — single entry point that every input path (wheel,
  // touch, keyboard, dot click, prev/next button, Cmd+K) funnels
  // through. Handles bounds, URL sync, cooldown stamping. Changing
  // activeDayIndex drives the CSS transition via transform recompute.
  const advanceTo = useCallback(
    (idx: number) => {
      if (idx < 0 || idx >= days.length) return
      if (idx === activeDayIndex) return
      lastRotationAtRef.current = Date.now()
      setActiveDayIndex(idx)
      const dateStr = days[idx]
      if (dateStr && dateStr !== searchParams.get("day")) {
        const sp = new URLSearchParams(searchParams)
        sp.set("day", dateStr)
        setSearchParams(sp, { replace: true })
      }
    },
    [activeDayIndex, days, searchParams, setSearchParams],
  )

  // Wheel gesture → day rotation. Non-passive listener (React onWheel
  // is passive by default; preventDefault would be a no-op). Only
  // consumes vertical wheel; horizontal wheel propagates to driver-
  // lane native overflow-x. Boundary-escalation: if the wheel target
  // is inside a scrollable child that can still scroll in the wheel
  // direction, let it scroll and skip rotation — only rotate when
  // the child is at its boundary (or there's no scrollable child).
  useEffect(() => {
    if (viewMode !== "single") return
    const stage = stageRef.current
    if (!stage) return

    const onWheel = (e: WheelEvent) => {
      const absY = Math.abs(e.deltaY)
      const absX = Math.abs(e.deltaX)
      // Horizontal-dominant wheel — let the driver-lane overflow-x
      // handle it. Don't preventDefault, don't rotate.
      if (absX > absY) return

      // Boundary-escalation — if a vertically scrollable ancestor of
      // the event target can still scroll in the wheel direction,
      // yield to it (lane scrolls before stage rotates).
      let el = e.target as Element | null
      while (el && el !== stage) {
        const style = window.getComputedStyle(el)
        const overflowY = style.overflowY
        if (
          (overflowY === "auto" || overflowY === "scroll") &&
          el.scrollHeight > el.clientHeight
        ) {
          const atTop = el.scrollTop <= 0
          const atBottom =
            el.scrollTop + el.clientHeight >= el.scrollHeight - 1
          if (e.deltaY < 0 && !atTop) return
          if (e.deltaY > 0 && !atBottom) return
          break
        }
        el = el.parentElement
      }

      // Vertical wheel on stage with no consuming child — rotate.
      e.preventDefault()

      // Cooldown — don't rotate again while an animation is in
      // progress. Absorbs the remainder of a continuous trackpad
      // gesture so one swipe = one rotation (not 5).
      const sinceLast = Date.now() - lastRotationAtRef.current
      if (sinceLast < ROTATION_COOLDOWN_MS) return

      wheelAccumRef.current += e.deltaY
      if (Math.abs(wheelAccumRef.current) >= WHEEL_THRESHOLD) {
        const next =
          wheelAccumRef.current > 0
            ? activeDayIndex + 1
            : activeDayIndex - 1
        advanceTo(next)
        wheelAccumRef.current = 0
      }

      // End-of-gesture detector — if wheel stops for 200ms, reset the
      // accumulator so a later gesture starts fresh.
      if (wheelEndTimerRef.current !== null) {
        clearTimeout(wheelEndTimerRef.current)
      }
      wheelEndTimerRef.current = window.setTimeout(() => {
        wheelAccumRef.current = 0
      }, 200)
    }

    stage.addEventListener("wheel", onWheel, { passive: false })
    return () => {
      stage.removeEventListener("wheel", onWheel)
      if (wheelEndTimerRef.current !== null) {
        clearTimeout(wheelEndTimerRef.current)
      }
    }
  }, [viewMode, activeDayIndex, advanceTo])

  // Touch gesture → day rotation. Captures start on pointerdown,
  // resolves on pointerup: vertical-dominant swipe above threshold
  // rotates; horizontal-dominant swipe is ignored (driver-lane native
  // touch scroll handles it).
  useEffect(() => {
    if (viewMode !== "single") return
    const stage = stageRef.current
    if (!stage) return

    const onPointerDown = (e: PointerEvent) => {
      if (e.pointerType !== "touch") return
      touchStartRef.current = { x: e.clientX, y: e.clientY }
    }

    const onPointerUp = (e: PointerEvent) => {
      if (e.pointerType !== "touch") return
      const start = touchStartRef.current
      touchStartRef.current = null
      if (!start) return

      const deltaY = start.y - e.clientY  // positive = swipe up
      const deltaX = e.clientX - start.x

      if (Math.abs(deltaX) > Math.abs(deltaY)) return
      if (Math.abs(deltaY) < SWIPE_THRESHOLD) return

      const sinceLast = Date.now() - lastRotationAtRef.current
      if (sinceLast < ROTATION_COOLDOWN_MS) return

      if (deltaY > 0) advanceTo(activeDayIndex + 1)
      else advanceTo(activeDayIndex - 1)
    }

    stage.addEventListener("pointerdown", onPointerDown)
    window.addEventListener("pointerup", onPointerUp)
    return () => {
      stage.removeEventListener("pointerdown", onPointerDown)
      window.removeEventListener("pointerup", onPointerUp)
    }
  }, [viewMode, activeDayIndex, advanceTo])

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

  // Phase 3.3.1 correction — empty driver columns hide by default,
  // reveal on drag. Surface shows what IS; interaction reveals
  // affordances. User spec rejected the prior "always render all
  // drivers" approach in favor of this pattern.
  //
  //   Resting:   only drivers with >= 1 delivery render as columns.
  //   Dragging:  all active drivers render, alphabetically ordered,
  //              revealed via smooth max-width + opacity transition.
  //   Drag end:  isDragging → false; collapse back to active-only.
  //              If the card dropped on a previously-empty driver,
  //              that driver becomes active via optimistic update
  //              and stays visible naturally.
  const [isDragging, setIsDragging] = useState(false)

  const handleDragStart = useCallback(() => {
    setIsDragging(true)
  }, [])

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      // Collapse the reveal — drag is over. If the card landed on a
      // previously-empty driver, the optimistic update below adds that
      // driver to the "has deliveries" set so its column persists.
      setIsDragging(false)
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

  const handleDragCancel = useCallback(() => {
    // Drag cancelled (ESC or drop outside any target) — collapse
    // reveal. No state update needed otherwise.
    setIsDragging(false)
  }, [])

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

  // Keyboard navigation in single mode — arrow keys + j/k for
  // dispatchers on keyboards. Funnels through `advanceTo` (same entry
  // point as wheel/touch/dot clicks).
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
        advanceTo(activeDayIndex + 1)
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault()
        advanceTo(activeDayIndex - 1)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [viewMode, activeDayIndex, advanceTo])

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
      data-slot="dispatch-funeral-schedule-page"
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
            Funeral Schedule
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
              data-slot="dispatch-fs-view-single"
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
              data-slot="dispatch-fs-view-all"
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
            data-slot="dispatch-fs-refresh"
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
          data-slot="dispatch-fs-loading"
          className="py-16 text-center text-body-sm text-content-muted"
        >
          Loading schedule…
        </div>
      )}
      {error && (
        <div
          role="alert"
          data-slot="dispatch-fs-error"
          className={cn(
            "mb-4 rounded border p-3",
            "bg-status-error-muted border-status-error/30 text-status-error",
          )}
        >
          {error}
        </div>
      )}

      {!loading && !error && days.length > 0 && (
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          {viewMode === "single" ? (
            <div className="flex items-stretch gap-3">
              {/* Dots indicator column — left rail, one per day.
                  Clicks route through advanceTo (same entry point as
                  wheel/touch/keyboard). */}
              <nav
                aria-label="Day navigation"
                data-slot="dispatch-fs-dots"
                className="sticky top-4 flex flex-col items-center gap-1.5 self-start"
              >
                <button
                  type="button"
                  onClick={() => advanceTo(activeDayIndex - 1)}
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
                    onClick={() => advanceTo(idx)}
                    data-slot="dispatch-fs-day-dot"
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
                  onClick={() => advanceTo(activeDayIndex + 1)}
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

              {/* Rotation stage — fixed height, relative-positioned
                  container holding every day as an absolute-positioned
                  layer. Active day sits at translateY(0); siblings
                  sit at translateY(±100%) with opacity 0. Changing
                  `activeDayIndex` triggers the CSS transition on
                  every layer simultaneously: prior active slides out,
                  new active slides in. iOS Smart Stack pattern —
                  content rotates, page does not scroll.

                  `overflow-hidden` clips the offscreen layers.
                  Horizontal scroll within a day (driver lanes) works
                  because each lane container carries its own
                  `overflow-x-auto`; the stage's overflow clip doesn't
                  interfere with child scroll regions. */}
              <div
                ref={stageRef}
                data-slot="dispatch-fs-stack"
                data-active-day-index={activeDayIndex}
                className="relative flex-1 overflow-hidden touch-pan-x"
                style={{
                  // Stage height: tall enough to hold a day's
                  // full-viewport kanban. Calc leaves room for the
                  // page header + padding above.
                  height: "calc(100vh - 12rem)",
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
                  const offset = idx - activeDayIndex
                  const isActive = offset === 0
                  return (
                    <div
                      key={dateStr}
                      data-slot="dispatch-fs-day-pane"
                      data-day-index={idx}
                      data-day-date={dateStr}
                      data-active={isActive ? "true" : "false"}
                      className={cn(
                        // Phase 3.3.1 rotation physics tune — iOS
                        // Smart Stack approximation. 380ms duration
                        // gives the card more physical weight than
                        // the 300ms canonical arrival; cubic-bezier
                        // (0.32, 0.72, 0, 1) has momentum-settle
                        // character matching iOS widget rotation
                        // (starts with more initial speed, decelerates
                        // into place) vs the canonical ease-settle
                        // (0.2, 0, 0.1, 1) which reads as more
                        // mechanical/UI-toolkit at this scale of
                        // motion. Localized to this component; not
                        // promoted to a platform token yet (single
                        // consumer, tune further if new surfaces
                        // adopt).
                        "absolute inset-0",
                        "transition-[transform,opacity] duration-[380ms]",
                        "ease-[cubic-bezier(0.32,0.72,0,1)]",
                      )}
                      style={{
                        transform: `translateY(${offset * 100}%)`,
                        opacity: isActive ? 1 : 0,
                        // Inactive layers don't intercept pointer
                        // events — only the active day responds to
                        // clicks, drags, hole-dug toggles, etc.
                        pointerEvents: isActive ? "auto" : "none",
                      }}
                      // aria-hidden on inactive layers keeps screen
                      // readers focused on the active day.
                      aria-hidden={!isActive}
                    >
                      <FuneralScheduleDayColumn
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
                        isDragging={isDragging}
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
              data-slot="dispatch-fs-all-days"
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
                  <FuneralScheduleDayColumn
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
                    isDragging={isDragging}
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
