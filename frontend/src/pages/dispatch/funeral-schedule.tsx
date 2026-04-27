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
 * dimension.
 *
 * **Phase 3.3.2 wheel capture correction (2026-04-24)**: the 3.2.1
 * wheel handler walked DOM ancestors looking for a vertically-
 * scrollable child to yield to (boundary-escalation). At resting
 * state the stage has no such children — the walk fell through to
 * preventDefault correctly. But `<main>` (AppLayout's content
 * region) has `overflow-y-auto`, and in some traversal cases the
 * page scroll was being triggered before the stage handler fired.
 * Fixed: removed the vertical-wheel ancestor walk entirely. Stage
 * captures ALL vertical wheel within its bounds regardless of cursor
 * target (card, lane, header, empty — all rotate). Horizontal wheel
 * still yields so lane overflow-x-auto works natively.
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
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"
import { useSearchParams } from "react-router-dom"

import { useFocus } from "@/contexts/focus-context"
import {
  ChevronDownIcon,
  ChevronUpIcon,
  LayersIcon,
  RefreshCwIcon,
  RowsIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { DeliveryCard } from "@/components/dispatch/DeliveryCard"
import { FuneralScheduleDayColumn } from "@/components/dispatch/FuneralScheduleDayColumn"
import {
  QuickEditDialog,
  type QuickEditSavePayload,
} from "@/components/dispatch/QuickEditDialog"
import {
  fetchDeliveriesForRange,
  detachAncillary,
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
  const [searchParams, setSearchParams] = useSearchParams()
  // Phase B Session 4 Phase 4.2 — "Open scheduling" launches the
  // Scheduling Focus (the Decide primitive for dispatch) instead of
  // navigating away. Prior (Phase 3) code called
  // `navigate('/delivery/scheduling-board?date=...')` — a route that
  // doesn't exist in App.tsx (pre-existing 404). Fixed as part of
  // 4.2 by routing through useFocus().open so the Focus overlays the
  // Monitor widget and the user returns here on close.
  const focus = useFocus()

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
  //
  // Phase 4.3.2 (r56, Item 7) — ancillary badge counts switched
  // from `order_id` inference to the canonical
  // `attached_to_delivery_id` FK. Three reasons the FK-based path
  // is correct:
  //
  //   1. Accuracy. The old inference picked `[0]` of the kanban
  //      deliveries sharing an order_id, which was arbitrary when
  //      a single order had multiple kanban shipments (split, multi-
  //      stop). The FK points at THE parent the ancillary is
  //      physically paired with.
  //
  //   2. Standalone exclusion by construction. Phase 4.3 standalone
  //      ancillaries have `attached_to_delivery_id = NULL` + a
  //      primary_assignee_id + date — they're assigned to a driver
  //      but not physically riding with a specific parent delivery.
  //      They must NOT count toward any parent's badge. The `if
  //      (d.attached_to_delivery_id)` guard accomplishes this
  //      naturally.
  //
  //   3. Pool exclusion too. Pool ancillaries have null
  //      attached_to_delivery_id + null primary_assignee_id; same
  //      guard filters them out.
  const { deliveriesByDate, ancillaryCountsByDate, ancillariesByParent } =
    useMemo(() => {
      const byDate = new Map<string, DeliveryDTO[]>()
      const parentCounts = new Map<string, number>()
      const parentMap = new Map<string, DeliveryDTO[]>()
      for (const d of deliveries) {
        if (!d.requested_date) continue
        if (!byDate.has(d.requested_date)) byDate.set(d.requested_date, [])
        byDate.get(d.requested_date)!.push(d)
        // Attached ancillaries count against their parent's badge.
        // direct_ship retains the order_id inference path for now —
        // direct_ship doesn't use the new attached_to_delivery_id
        // model (it ships via Wilbert, not paired with a kanban
        // delivery). Phase 4.3 does not migrate direct_ship.
        if (d.scheduling_type === "ancillary") {
          if (d.attached_to_delivery_id) {
            const parent = deliveries.find(
              (p) => p.id === d.attached_to_delivery_id,
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
          // else: pool or standalone — no parent badge contribution
        } else if (d.scheduling_type === "direct_ship") {
          // direct_ship uses legacy order_id inference (unchanged
          // from Phase 3); no parent FK exists for this path.
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

  // ── Stage gesture listeners (Phase 3.3.3 — callback ref) ─────────
  //
  // Pre-3.3.3 attached wheel + pointer listeners via `useEffect` that
  // read a `stageRef` created with `useRef`. In the running dev build
  // the effect was not attaching the wheel listener to the live stage
  // DOM element (reason indeterminate after deep DevTools inspection —
  // the fiber's ref slot had the correct element, the effect body was
  // correct when replicated manually, but `preventDefault` never
  // fired on wheel events reaching the stage in bubble phase). This
  // produced the symptom: wheel over cards/lanes within the stage
  // caused the page (`<main>` has `overflow-y-auto`) to scroll
  // instead of rotating days.
  //
  // Fix: switch to **callback ref**. The callback fires synchronously
  // when React commits the DOM — the listener is attached atomically
  // with the ref being set. No useEffect lifecycle, no dep-array
  // timing, no way to race. This is the architecturally correct shape
  // for DOM-listener-tied-to-element-lifetime side effects.
  //
  // Handler closures read current values (`advanceTo`, `activeDay
  // Index`, `viewMode`) via latest-refs so the callback doesn't need
  // to re-subscribe when those change.
  //
  // Wheel semantics (unchanged from 3.3.2):
  //   - Horizontal-dominant wheel → return, let driver-lane
  //     overflow-x-auto scroll natively.
  //   - Vertical-dominant wheel → preventDefault + accumulate + rotate
  //     on threshold. Stage is authoritative; no ancestor-walk.
  //
  // Touch semantics (unchanged from 3.3.2):
  //   - pointerdown (touch) captures start.
  //   - pointerup vertical-dominant above threshold rotates.
  const advanceToRef = useRef(advanceTo)
  useEffect(() => {
    advanceToRef.current = advanceTo
  })
  const activeDayIndexRef = useRef(activeDayIndex)
  useEffect(() => {
    activeDayIndexRef.current = activeDayIndex
  })
  const viewModeRef = useRef(viewMode)
  useEffect(() => {
    viewModeRef.current = viewMode
  })

  const stageCleanupRef = useRef<(() => void) | null>(null)

  const setStageNode = useCallback((node: HTMLDivElement | null) => {
    // Detach from prior node (if any).
    if (stageCleanupRef.current) {
      stageCleanupRef.current()
      stageCleanupRef.current = null
    }
    if (!node) return

    // ── Wheel handler (non-passive so preventDefault actually
    // blocks the default scroll action).
    const onWheel = (e: WheelEvent) => {
      if (viewModeRef.current !== "single") return
      const absY = Math.abs(e.deltaY)
      const absX = Math.abs(e.deltaX)
      if (absX > absY) return

      e.preventDefault()

      const sinceLast = Date.now() - lastRotationAtRef.current
      if (sinceLast < ROTATION_COOLDOWN_MS) return

      wheelAccumRef.current += e.deltaY
      if (Math.abs(wheelAccumRef.current) >= WHEEL_THRESHOLD) {
        const next =
          wheelAccumRef.current > 0
            ? activeDayIndexRef.current + 1
            : activeDayIndexRef.current - 1
        advanceToRef.current(next)
        wheelAccumRef.current = 0
      }

      if (wheelEndTimerRef.current !== null) {
        clearTimeout(wheelEndTimerRef.current)
      }
      wheelEndTimerRef.current = window.setTimeout(() => {
        wheelAccumRef.current = 0
      }, 200)
    }
    node.addEventListener("wheel", onWheel, { passive: false })

    // ── Touch handlers.
    const onPointerDown = (e: PointerEvent) => {
      if (viewModeRef.current !== "single") return
      if (e.pointerType !== "touch") return
      touchStartRef.current = { x: e.clientX, y: e.clientY }
    }
    const onPointerUp = (e: PointerEvent) => {
      if (viewModeRef.current !== "single") return
      if (e.pointerType !== "touch") return
      const start = touchStartRef.current
      touchStartRef.current = null
      if (!start) return

      const deltaY = start.y - e.clientY
      const deltaX = e.clientX - start.x
      if (Math.abs(deltaX) > Math.abs(deltaY)) return
      if (Math.abs(deltaY) < SWIPE_THRESHOLD) return

      const sinceLast = Date.now() - lastRotationAtRef.current
      if (sinceLast < ROTATION_COOLDOWN_MS) return

      if (deltaY > 0) advanceToRef.current(activeDayIndexRef.current + 1)
      else advanceToRef.current(activeDayIndexRef.current - 1)
    }
    node.addEventListener("pointerdown", onPointerDown)
    window.addEventListener("pointerup", onPointerUp)

    stageCleanupRef.current = () => {
      node.removeEventListener("wheel", onWheel)
      node.removeEventListener("pointerdown", onPointerDown)
      window.removeEventListener("pointerup", onPointerUp)
      if (wheelEndTimerRef.current !== null) {
        clearTimeout(wheelEndTimerRef.current)
        wheelEndTimerRef.current = null
      }
    }
  }, [])

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
      focus.open("funeral-scheduling", { params: { date: dateStr } })
    },
    [focus],
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
          // Phase 4.3.2 (r56) — QuickEdit continues to collect a
          // driver.id via its dropdown; backend helper translates
          // driver.id → users.id via Driver.employee_id. Phase 4.3.3
          // can migrate QuickEditDialog to use user_id directly.
          primary_assignee_id: payload.assignedDriverId,
          // Phase 4.3.3 — helper + start time now round-trip
          // through QuickEdit. Helper is users.id (or null).
          // driver_start_time is "HH:MM" or null (use tenant
          // default).
          helper_user_id: payload.helperUserId,
          driver_start_time: payload.driverStartTime,
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

  // Phase 4.3.3.1 — detach an attached ancillary from its parent.
  // Backend `/ancillary/{id}/detach` clears attached_to_delivery_id +
  // sets ancillary_is_floating=false + retains primary_assignee +
  // requested_date (defaults to standalone, single-path per Flag 2).
  // We close the dialog + reload after the call resolves.
  const handleDetachFromQuickEdit = useCallback(
    async (deliveryId: string) => {
      try {
        await detachAncillary(deliveryId)
        setEditTarget(null)
        reload()
      } catch (e) {
        console.error("ancillary detach failed:", e)
        alert("Couldn't detach the ancillary. Try again.")
      }
    },
    [reload],
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

  // Phase 4.2.6 — DragOverlay active-id (matches Focus's
  // SchedulingKanbanCore pattern from Phase 4.2.2). When set, the
  // card at that id renders as a ghost in its origin lane while a
  // floating preview (portaled to document.body) tracks the cursor.
  // Fixes the "dragged card renders behind adjacent column" symptom:
  // each lane's `overflow-y-auto` body establishes its own stacking
  // context, so the default in-place `transform: translate` drag
  // would paint the card beneath sibling columns. Portaling to
  // document.body via DragOverlay lifts the preview above every
  // stacking context.
  const [activeDeliveryId, setActiveDeliveryId] = useState<string | null>(null)

  const handleDragStart = useCallback((ev: DragStartEvent) => {
    setIsDragging(true)
    const id = String(ev.active.id).replace(/^delivery:/, "")
    setActiveDeliveryId(id)
  }, [])

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      // Collapse the reveal — drag is over. If the card landed on a
      // previously-empty driver, the optimistic update below adds that
      // driver to the "has deliveries" set so its column persists.
      setIsDragging(false)
      setActiveDeliveryId(null)
      const { active, over } = ev
      if (!over) return
      const deliveryId = String(active.id).replace(/^delivery:/, "")
      const laneKey = String(over.id)
      const sep = laneKey.indexOf(":")
      if (sep === -1) return
      const targetDriverRaw = laneKey.slice(sep + 1)
      // Phase 4.3.2 (r56) — lane keys now carry user_id values (see
      // FuneralScheduleDayColumn laneKey construction). The parsed
      // raw value is a users.id (or UNASSIGNED sentinel), ready for
      // the backend's primary_assignee_id field.
      const targetAssigneeId =
        targetDriverRaw === "__UNASSIGNED__" ? null : targetDriverRaw
      const delivery = deliveries.find((d) => d.id === deliveryId)
      if (!delivery) return
      if (delivery.primary_assignee_id === targetAssigneeId) return
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === deliveryId
            ? { ...d, primary_assignee_id: targetAssigneeId }
            : d,
        ),
      )
      try {
        await updateDelivery(deliveryId, {
          primary_assignee_id: targetAssigneeId,
        })
        // Phase 4.2.4 — success-path reload removed (caused screen
        // flash after every drop because reload → setLoading(true)
        // in the parent useEffect). Optimistic update above already
        // reflects intended state; no reload needed on success.
      } catch (e) {
        console.error("driver reassign failed:", e)
        reload() // error-path reload restores authoritative state
      }
    },
    [deliveries, reload],
  )

  const handleDragCancel = useCallback(() => {
    // Drag cancelled (ESC or drop outside any target) — collapse
    // reveal. No state update needed otherwise.
    setIsDragging(false)
    setActiveDeliveryId(null)
  }, [])

  // Preview delivery for the DragOverlay (derived fresh each render
  // from authoritative `deliveries` state — stays in sync with
  // optimistic updates). Matches SchedulingKanbanCore's pattern.
  const activeDelivery = useMemo(
    () =>
      activeDeliveryId
        ? deliveries.find((d) => d.id === activeDeliveryId) ?? null
        : null,
    [activeDeliveryId, deliveries],
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
        "font-sans text-content-base",
      )}
    >
      {/* Header */}
      <header className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-h2 font-medium text-content-strong font-display">
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
                "focus-ring-accent outline-none transition-colors duration-quick",
                viewMode === "single"
                  ? "bg-accent text-content-on-accent"
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
                "focus-ring-accent outline-none transition-colors duration-quick",
                viewMode === "all"
                  ? "bg-accent text-content-on-accent"
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
                    "focus-ring-accent outline-none",
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
                        ? "bg-accent"
                        : "bg-border-subtle hover:bg-content-muted",
                      "focus-ring-accent outline-none",
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
                    "focus-ring-accent outline-none",
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
                ref={setStageNode}
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
                    activeDeliveryId={activeDeliveryId}
                  />
                )
              })}
            </div>
          )}

          {/* Phase 4.2.6 — DragOverlay pattern lifted from
              SchedulingKanbanCore (Phase 4.2.2). Portaled to
              document.body so the dragged card floats above every
              sibling-column stacking context. Each lane's
              `overflow-y-auto` body creates its own stacking
              context; without the portal, @dnd-kit's default
              in-place `transform: translate` would render the
              card behind adjacent columns.

              No containing-block trap here (Monitor isn't inside
              the Focus positioner), but we portal anyway for
              consistency with Focus and to future-proof against
              any transform-bearing ancestor landing above. */}
          {createPortal(
            <DragOverlay
              dropAnimation={{
                duration: 180,
                easing: "cubic-bezier(0.18, 0.67, 0.6, 1.22)",
              }}
            >
              {activeDelivery && (
                // Phase 4.2.7 — `w-full` instead of `w-[280px]`.
                // @dnd-kit's PositionedOverlay (the DragOverlay root
                // element) sets `width: rect.width` from the active
                // card's getBoundingClientRect at drag-start, which
                // for Monitor Sunday through Thursday is 274.4px
                // (lane width minus rendering nuance), not the 280px
                // the lane nominally claims. A hard 280px inner
                // child overflowed 5.6px to the right, and combined
                // with `scale-[1.02]` drew the preview visibly off
                // from the cursor's grip point. Using `w-full`
                // matches the Popup's measured width exactly so the
                // preview tracks the cursor with grip-point fidelity.
                <div
                  data-slot="funeral-schedule-drag-preview"
                  className="scale-[1.02] shadow-level-3 rounded-md w-full"
                >
                  <DeliveryCard
                    delivery={activeDelivery}
                    scheduleFinalized={
                      schedules.get(activeDelivery.requested_date ?? "")
                        ?.state === "finalized"
                    }
                  />
                </div>
              )}
            </DragOverlay>,
            document.body,
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
        onDetach={handleDetachFromQuickEdit}
      />
    </div>
  )
}


// Side-effect export — marking that a delivery update on a finalized
// day triggers a server-side revert in `delivery_service.update_
// delivery`.
export { revertSchedule }
