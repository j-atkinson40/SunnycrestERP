/**
 * SchedulingKanbanCore — the Decide surface for funeral dispatch.
 *
 * Phase B Session 4 Phase 4.2. First vertical-specific Focus core
 * built on the Phase A Focus primitive foundation per
 * PLATFORM_ARCHITECTURE.md §5 (Focus = Decide) and the three-primitive
 * architecture (Monitor via Funeral Schedule widget, Act via Command
 * Bar, Decide here).
 *
 * What this surface is:
 *   The dispatcher's dedicated planning workspace. Enter, plan
 *   tomorrow's schedule, exit. Bounded-decision primitive per §5.1 —
 *   not a page, not a modal, not a panel. Distinct from the Monitor
 *   (read-mostly visibility) and Command bar (single-action).
 *
 * Registered as: `{ id: "funeral-scheduling", mode: "kanban",
 * coreComponent: SchedulingKanbanCore }` via the Session 4 extension
 * point on FocusConfig. The mode-dispatcher prefers coreComponent
 * over MODE_RENDERERS["kanban"] (the generic stub used by Phase A's
 * dev test page). See focus-registry.ts + mode-dispatcher.tsx for
 * the extension mechanism.
 *
 * Scope of Phase 4.2:
 *   - Core kanban: Unassigned as leftmost column, then alphabetical
 *     driver columns. ALL drivers render (not hide-by-default like
 *     the Monitor widget — this IS the decide surface; showing all
 *     options is correct here per PLATFORM_PRODUCT_PRINCIPLES
 *     "Surface At Rest vs On Interaction").
 *   - @dnd-kit drag between any two columns (including from/to
 *     Unassigned). Drop fires PATCH /delivery/:id with new
 *     primary_assignee_id; optimistic UI + reload on completion.
 *   - Target-day from URL ?day=YYYY-MM-DD (via FocusState.params
 *     seeded from openFocus options). Defaults to tomorrow if
 *     absent.
 *   - Day selector in header — compact popover with Today /
 *     Tomorrow / +2 / +3.
 *   - Finalize button — calls finalizeSchedule + closes Focus.
 *   - Close without finalize — draft preserved, return pill picks
 *     it up via the Focus primitive's standard re-entry path.
 *   - Reuses the DeliveryCard component from the Monitor widget
 *     (no duplication; Phase 3.3 card surface polish applies
 *     uniformly).
 *
 * Out of scope for 4.2 (land in later phases):
 *   - Ancillary pin + drag-onto-parent (Phase 4.3, with new
 *     attached_to_delivery_id FK schema change per user's 4.3 spec)
 *   - Helper assignment (4.3b)
 *   - Adjacent-day peek/slide pattern (Phase 4.4)
 *   - DnD migration of legacy scheduling-board (Phase 4.5)
 *   - Context-aware pins (cemeteries, drive-time, staff
 *     availability) per PA §5.4
 */

import {
  DragOverlay,
  useDndMonitor,
  useDraggable,
  useDroppable,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { CheckCircle2Icon, ChevronDownIcon } from "lucide-react"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"
import { useSearchParams } from "react-router-dom"

import { AncillaryCard } from "@/components/dispatch/AncillaryCard"
import { DeliveryCard } from "@/components/dispatch/DeliveryCard"
import { ANCILLARY_POOL_DROPPABLE_ID } from "@/components/dispatch/scheduling-focus/AncillaryPoolPin"
import { DateBox } from "@/components/dispatch/scheduling-focus/DateBox"
import {
  QuickEditDialog,
  type QuickEditSavePayload,
} from "@/components/dispatch/QuickEditDialog"
import { Button } from "@/components/ui/button"
import { useFocus } from "@/contexts/focus-context"
import { useSchedulingFocusOptional } from "@/contexts/scheduling-focus-context"
import { cn } from "@/lib/utils"
import {
  assignAncillaryStandalone,
  attachAncillary,
  detachAncillary,
  fetchDeliveriesForRange,
  fetchDrivers,
  fetchSchedule,
  fetchTenantTime,
  finalizeSchedule,
  returnAncillaryToPool,
  updateDelivery,
  updateHoleDug,
  type DeliveryDTO,
  type DriverDTO,
  type ScheduleStateDTO,
  type TenantTimeDTO,
} from "@/services/dispatch-service"

import type { FocusConfig } from "@/contexts/focus-registry"


const UNASSIGNED_LANE_ID = "__UNASSIGNED__"


export interface SchedulingKanbanCoreProps {
  focusId: string
  config: FocusConfig
}


// ── Date helpers ────────────────────────────────────────────────────


function isoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}


function addDays(baseIso: string, n: number): string {
  const [y, m, d] = baseIso.split("-").map(Number)
  const dt = new Date(y, (m ?? 1) - 1, (d ?? 1) + n)
  return isoDate(dt)
}


function formatDayLabel(targetIso: string, todayIso: string): string {
  const [ty, tm, td] = targetIso.split("-").map(Number)
  const dt = new Date(ty, (tm ?? 1) - 1, td ?? 1)
  const weekday = dt.toLocaleDateString(undefined, { weekday: "long" })
  const monthDay = dt.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
  })
  if (targetIso === todayIso) return `Today, ${monthDay}`
  if (targetIso === addDays(todayIso, 1)) return `Tomorrow, ${monthDay}`
  return `${weekday}, ${monthDay}`
}


// ── Core renderer ───────────────────────────────────────────────────


export function SchedulingKanbanCore({ focusId }: SchedulingKanbanCoreProps) {
  void focusId  // reserved — could inform logging / telemetry later

  const { currentFocus, close } = useFocus()
  const [searchParams] = useSearchParams()
  // Target-date source priority:
  //   1. focus.params.date (set when someone called `useFocus().open(
  //      "funeral-scheduling", { params: { date } })`)
  //   2. URL `?day=<iso>` (supports deep-linking + Cmd+K route-based
  //      launch)
  //   3. tenant-local tomorrow (computed once tenantTime resolves)
  const paramsDate =
    (currentFocus?.params["date"] as string | undefined) ??
    searchParams.get("day") ??
    undefined

  // Tenant time — resolves "today" server-side so we can compute the
  // default target (tomorrow) without relying on the browser clock.
  const [tenantTime, setTenantTime] = useState<TenantTimeDTO | null>(null)
  useEffect(() => {
    let cancelled = false
    fetchTenantTime()
      .then((t) => {
        if (!cancelled) setTenantTime(t)
      })
      .catch((e) => {
        console.warn("tenant-time fetch failed, using browser clock", e)
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

  // Resolve the target date. Priority: URL/focus-params `date` →
  // tenant-local tomorrow → null (show loading).
  const [targetDate, setTargetDate] = useState<string | null>(null)
  useEffect(() => {
    if (targetDate !== null) return
    if (paramsDate) {
      setTargetDate(paramsDate)
      return
    }
    if (tenantTime) {
      setTargetDate(addDays(tenantTime.local_date, 1))
    }
  }, [targetDate, paramsDate, tenantTime])

  // Data state
  const [schedule, setSchedule] = useState<ScheduleStateDTO | null>(null)
  const [deliveries, setDeliveries] = useState<DeliveryDTO[]>([])
  const [drivers, setDrivers] = useState<DriverDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const [finalizing, setFinalizing] = useState(false)
  const [daySelectorOpen, setDaySelectorOpen] = useState(false)

  // Phase B Session 4.4.3 — adjacent-day peek/slide state. Each date
  // box (today / day-after) toggles its own boolean. Phase 4.4.3 is
  // state-tracking only; visual feedback is the brass-on-active
  // affordance on the box. Phase 4.4.4 wires these flags to the
  // multi-day rendering + slide animation. Both can be active
  // independently (allowing a future 3-day expanded view) — the
  // exclusivity decision waits for Phase 4.4.4 layout design.
  const [prevExpanded, setPrevExpanded] = useState(false)
  const [nextExpanded, setNextExpanded] = useState(false)

  // Phase 4.3b.3 — pool ancillaries live in SchedulingFocusContext
  // (provider mounted at Focus.tsx level when active focus is
  // funeral-scheduling). Kanban core reads via the optional hook so
  // existing tests that don't wrap with the provider continue to
  // render. When null (test path or non-funeral-scheduling focus),
  // pool-related drag routing falls through to the no-op branch.
  const schedulingFocus = useSchedulingFocusOptional()

  const reload = useCallback(() => {
    setRefreshTick((n) => n + 1)
    // Also refresh the pool — drag operations that move items into
    // the pool (return-to-pool) need both kanban + pool to reload.
    schedulingFocus?.reloadPool()
  }, [schedulingFocus])

  // Fetch deliveries + drivers + schedule state for the target date.
  useEffect(() => {
    if (!targetDate) return
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      fetchSchedule(targetDate),
      fetchDeliveriesForRange({ start: targetDate, end: targetDate }),
      fetchDrivers(),
    ])
      .then(([sched, dels, drvs]) => {
        if (cancelled) return
        setSchedule(sched)
        setDeliveries(dels)
        setDrivers(drvs)
      })
      .catch((e) => {
        if (cancelled) return
        console.error("scheduling focus load failed:", e)
        setError("Couldn't load the scheduling data. Try again.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [targetDate, refreshTick])

  // Group deliveries by driver.
  //
  // Phase 4.3.2 (r56) — grouping key is `primary_assignee_id`
  // (users.id). Compare lane membership via driver.user_id below.
  //
  // Phase 4.3.3 — extended to include STANDALONE ancillaries
  // (scheduling_type='ancillary' AND attached_to_delivery_id=null
  // AND primary_assignee_id set). These render in driver lanes
  // alongside primary kanban deliveries via AncillaryCard. ATTACHED
  // ancillaries (attached_to_delivery_id set) are NOT rendered in
  // lanes — they show as a +N badge on the parent's DeliveryCard,
  // expandable to inline slots (4.3.3.1 ships Focus parity with
  // Monitor's expansion behavior; 4.3b adds drag-to-detach on the
  // expanded slots themselves). POOL ancillaries (no driver,
  // floating) render in the Phase 4.3b pool pin widget — out of
  // 4.3.3 scope.
  //
  // Direct-ship is also out of scope for the kanban view.
  const {
    kanbanByDriver,
    unassignedKanban,
    standaloneAncillariesByDriver,
    attachedAncillariesByParent,
  } = useMemo(() => {
    const byDriver = new Map<string, DeliveryDTO[]>()
    const standaloneByDriver = new Map<string, DeliveryDTO[]>()
    const attachedByParent = new Map<string, DeliveryDTO[]>()
    const unassigned: DeliveryDTO[] = []
    for (const d of deliveries) {
      if (d.scheduling_type === "kanban") {
        const assigneeId = d.primary_assignee_id
        if (assigneeId) {
          if (!byDriver.has(assigneeId)) byDriver.set(assigneeId, [])
          byDriver.get(assigneeId)!.push(d)
        } else {
          unassigned.push(d)
        }
        continue
      }
      if (d.scheduling_type === "ancillary") {
        // Phase 4.3.3.1 — capture attached ancillaries keyed by parent
        // so DeliveryCard can render the +N count badge AND so the
        // expansion drawer can iterate the children. Mirrors Monitor's
        // pattern in funeral-schedule.tsx.
        if (d.attached_to_delivery_id) {
          const parentId = d.attached_to_delivery_id
          if (!attachedByParent.has(parentId)) {
            attachedByParent.set(parentId, [])
          }
          attachedByParent.get(parentId)!.push(d)
          continue
        }
        // Standalone: assigned + not attached to a parent.
        const assigneeId = d.primary_assignee_id
        if (assigneeId) {
          if (!standaloneByDriver.has(assigneeId)) {
            standaloneByDriver.set(assigneeId, [])
          }
          standaloneByDriver.get(assigneeId)!.push(d)
        }
        // Pool ancillaries (floating, no assignee, no parent): skipped.
      }
      // direct_ship: skipped — handled by separate dispatch UI.
    }
    return {
      kanbanByDriver: byDriver,
      unassignedKanban: unassigned,
      standaloneAncillariesByDriver: standaloneByDriver,
      attachedAncillariesByParent: attachedByParent,
    }
  }, [deliveries])

  // Phase 4.3.3.1 — expanded-parent state (Set of parent delivery_ids
  // whose attached-ancillary drawer is currently open). Mirrors Monitor's
  // expansion pattern in FuneralScheduleDayColumn.tsx. Click on the
  // ancillary IconTooltip badge toggles membership.
  const [expandedAncillaryParents, setExpandedAncillaryParents] = useState<
    Set<string>
  >(() => new Set())
  const toggleAncillaryExpansion = useCallback((parentId: string) => {
    setExpandedAncillaryParents((prev) => {
      const next = new Set(prev)
      if (next.has(parentId)) {
        next.delete(parentId)
      } else {
        next.add(parentId)
      }
      return next
    })
  }, [])

  // Full roster sorted alphabetically — ALL drivers render (this is
  // the decide surface, all options visible is correct).
  const sortedDrivers = useMemo(
    () =>
      [...drivers].sort((a, b) => {
        const na = (a.display_name ?? a.license_number ?? "").toLowerCase()
        const nb = (b.display_name ?? b.license_number ?? "").toLowerCase()
        return na.localeCompare(nb)
      }),
    [drivers],
  )

  // Phase B Session 4.3b D-1 elevation. Pre-4.3b SchedulingKanbanCore
  // owned its own `<DndContext>` with a local PointerSensor. Phase
  // 4.3b moved DndContext + sensors up to FocusDndProvider so cross-
  // context drag (canvas pin item → kanban lane) becomes possible.
  // Sensors are now provider-owned (same `distance: 8` activation
  // constraint as before, no behavioral change). This component
  // subscribes to drag events via `useDndMonitor` (registered later
  // in this function) — handler gates on the `delivery:` and
  // `ancillary:` id prefixes; widget: drags are no-ops here and
  // routed by Canvas's own listener.

  // Phase 4.2.2 — track the active drag id so the DragOverlay can
  // render a floating preview at document level (portaled above every
  // sibling stacking context). Fixes the prior "dragged card rendered
  // behind adjacent columns" bug where the card's `transform` placed
  // it visually across columns but its DOM position kept it beneath
  // siblings that had their own stacking context (the adjacent lane's
  // `overflow-y-auto` body establishes one).
  const [activeDeliveryId, setActiveDeliveryId] = useState<string | null>(null)

  // Phase 4.2.5 — QuickEdit dialog state. Focus didn't wire
  // `onOpenEdit` on DeliveryCard pre-4.2.5, so short-clicks on cards
  // did nothing visible even though the click event fired. Adding
  // the Monitor's QuickEdit pattern here makes clicks open the edit
  // dialog consistently across both surfaces. Save handler mirrors
  // Monitor's handleSaveEdit but trims down: Focus doesn't apply
  // the schedule-revert confirmation UI (Focus is already the
  // full-screen plan-all-day surface, so mid-session edits don't
  // surprise anyone).
  const [editTarget, setEditTarget] = useState<DeliveryDTO | null>(null)

  // Phase 4.3b D-1 elevation. Listeners filter by id prefix; drags
  // for canvas widgets (`widget:`) flow through Canvas's listener,
  // not this one. Two prefixes are claimed here: `delivery:` (primary
  // kanban + standalone ancillary cards in lanes) and `ancillary:`
  // (Phase 4.3b pool pin items + drawer detach drags). Returning
  // early on non-matching prefixes is the discriminator contract;
  // multiple useDndMonitor consumers coexist on the elevated context.
  const handleDragStart = useCallback((ev: DragStartEvent) => {
    const raw = String(ev.active.id)
    if (!raw.startsWith("delivery:") && !raw.startsWith("ancillary:")) return
    const id = raw.replace(/^(delivery|ancillary):/, "")
    setActiveDeliveryId(id)
  }, [])

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      const rawId = String(ev.active.id)
      // Phase 4.3b D-1 — early return on non-matching prefixes
      // (canvas widget drags are routed by Canvas's listener).
      if (!rawId.startsWith("delivery:") && !rawId.startsWith("ancillary:")) {
        return
      }
      // Clear the overlay preview regardless of drop validity.
      setActiveDeliveryId(null)
      const { active, over } = ev
      if (!over) return
      const deliveryId = String(active.id).replace(/^(delivery|ancillary):/, "")
      const overId = String(over.id)

      // Phase 4.3b.3 — drop target taxonomy:
      //   "delivery-as-parent:<id>" → attach branch (pool/standalone
      //                                ancillary onto a kanban parent
      //                                delivery card)
      //   "<date>:<driverId|__UNASSIGNED__>" → lane branch (standard
      //                                drag-to-reassign)
      // Branch first on parent-drop because lane-key format expects
      // a colon-separated date:driver shape that doesn't match the
      // delivery-as-parent: discriminator.
      const isParentDrop = overId.startsWith("delivery-as-parent:")
      // Phase 4.3b.4 — pin drop target. AncillaryPoolPin's outer
      // container exposes a useDroppable with id =
      // ANCILLARY_POOL_DROPPABLE_ID. Standalone + attached
      // ancillaries dropping here return-to-pool; pool-source
      // drops are no-ops (already in pool).
      const isPoolDrop = overId === ANCILLARY_POOL_DROPPABLE_ID

      // Source resolution. Phase 4.3b.3 — sources can come from EITHER
      // the day's deliveries (kanban primaries, standalone ancillaries,
      // attached drawer items) OR the pool pin (date-less pool
      // ancillaries). The pool list lives in SchedulingFocusContext.
      const fromDeliveries = deliveries.find((d) => d.id === deliveryId)
      const fromPool = schedulingFocus?.poolAncillaries.find(
        (d) => d.id === deliveryId,
      )
      const sourceDelivery = fromDeliveries ?? fromPool ?? null
      if (!sourceDelivery) return
      const isFromPool = fromDeliveries === undefined && fromPool !== undefined

      // ── Pin-drop branch (Phase 4.3b.4) ──────────────────────────
      if (isPoolDrop) {
        // Only ancillaries belong in the pool.
        if (sourceDelivery.scheduling_type !== "ancillary") return
        // Pool→pool no-op.
        if (isFromPool) return

        // Optimistic update — remove from deliveries; pool will
        // refresh after API call. Brief flash where the ancillary
        // disappears from the kanban before the pin updates is
        // acceptable because the dispatcher's attention is on the
        // pin (drop target).
        setDeliveries((prev) => prev.filter((d) => d.id !== deliveryId))
        try {
          await returnAncillaryToPool(deliveryId)
          // Refresh pool so the now-pool item appears in the pin.
          schedulingFocus?.reloadPool()
        } catch (e) {
          console.error("scheduling focus return-to-pool failed:", e)
          reload() // restore authoritative state
        }
        return
      }

      // ── Parent-drop branch ─────────────────────────────────────
      if (isParentDrop) {
        const parentId = overId.replace(/^delivery-as-parent:/, "")
        // Only ancillaries can attach. Primary kanban cards dropping
        // on each other are no-ops (no semantic for "delivery as
        // parent of delivery").
        if (sourceDelivery.scheduling_type !== "ancillary") return
        // Already attached to this parent → no-op (client-side
        // guard; server would 409 anyway).
        if (sourceDelivery.attached_to_delivery_id === parentId) return

        // Validate parent: must be kanban + assigned. Server would
        // reject otherwise; client guard avoids the API roundtrip
        // for invalid drops.
        const parent = deliveries.find((d) => d.id === parentId)
        if (
          !parent ||
          parent.scheduling_type !== "kanban" ||
          !parent.primary_assignee_id
        ) {
          return
        }

        // Optimistic update.
        // From pool: remove from pool + add to deliveries with
        //            attached state.
        // From deliveries (standalone or different-parent attached):
        //            mutate to attached state; no list-shape change.
        if (isFromPool) {
          schedulingFocus?.removeFromPoolOptimistic(deliveryId)
          setDeliveries((prev) => [
            ...prev,
            {
              ...sourceDelivery,
              attached_to_delivery_id: parentId,
              primary_assignee_id: parent.primary_assignee_id,
              helper_user_id: parent.helper_user_id,
              requested_date: parent.requested_date,
              ancillary_is_floating: false,
              ancillary_fulfillment_status: "assigned_to_driver",
              attached_to_family_name:
                (parent.type_config?.family_name as string | undefined) ??
                null,
            },
          ])
        } else {
          setDeliveries((prev) =>
            prev.map((d) =>
              d.id === deliveryId
                ? {
                    ...d,
                    attached_to_delivery_id: parentId,
                    primary_assignee_id: parent.primary_assignee_id,
                    helper_user_id: parent.helper_user_id,
                    requested_date: parent.requested_date,
                    ancillary_is_floating: false,
                    ancillary_fulfillment_status: "assigned_to_driver",
                    attached_to_family_name:
                      (parent.type_config?.family_name as
                        | string
                        | undefined) ?? null,
                  }
                : d,
            ),
          )
        }
        try {
          await attachAncillary(deliveryId, parentId)
        } catch (e) {
          console.error("scheduling focus attach failed:", e)
          reload()
        }
        return
      }

      // ── Lane-drop branch (existing logic, extended for pool source) ──
      const sep = overId.indexOf(":")
      if (sep === -1) return
      const targetDriverRaw = overId.slice(sep + 1)
      // Phase 4.3.2 (r56) — lane keys carry user_id (users.id) values,
      // not driver.id. The parsed raw value is ready to ship to the
      // backend's primary_assignee_id field.
      const nextAssigneeId =
        targetDriverRaw === UNASSIGNED_LANE_ID ? null : targetDriverRaw
      // Same-assignee drops are no-ops (pool→Unassigned is the
      // null===null case, no API call needed).
      if (sourceDelivery.primary_assignee_id === nextAssigneeId) return

      // Phase 4.3.3 — branch on scheduling_type.
      //
      // PRIMARY (kanban): straight PATCH on primary_assignee_id.
      // ANCILLARY: route through the dedicated state-machine
      // endpoints so server-side fields (ancillary_is_floating,
      // ancillary_fulfillment_status, attached_to_delivery_id)
      // update correctly. Drag-to-Unassigned for an ancillary
      // calls return-to-pool (full reset to floating). Drag-to-
      // driver-column for an ancillary calls assign-standalone
      // (sets driver + date, ensures FK is null, clears floating).
      const isAncillary = sourceDelivery.scheduling_type === "ancillary"

      // Optimistic UI — local state reflects the new assignment
      // immediately. Backend PATCH runs in the background; only
      // the error path re-fetches authoritative state.
      //
      // Phase 4.3b.3 — pool source paths add to deliveries instead
      // of mutating in-place (the source isn't in the deliveries
      // array yet).
      if (isFromPool) {
        schedulingFocus?.removeFromPoolOptimistic(deliveryId)
        if (isAncillary && nextAssigneeId !== null && targetDate) {
          // Pool → driver lane → standalone
          setDeliveries((prev) => [
            ...prev,
            {
              ...sourceDelivery,
              primary_assignee_id: nextAssigneeId,
              requested_date: targetDate,
              attached_to_delivery_id: null,
              ancillary_is_floating: false,
              ancillary_fulfillment_status: "assigned_to_driver",
            },
          ])
        }
        // Pool → Unassigned: short-circuited above (same-assignee
        // null===null no-op); no setDeliveries needed.
      } else {
        setDeliveries((prev) =>
          prev.map((d) => {
            if (d.id !== deliveryId) return d
            if (isAncillary && nextAssigneeId === null) {
              // Ancillary → pool: clear assignment + date + FK,
              // mark floating. Mirrors return_ancillary_to_pool
              // server side.
              return {
                ...d,
                primary_assignee_id: null,
                attached_to_delivery_id: null,
                requested_date: null,
                ancillary_is_floating: true,
                ancillary_fulfillment_status: "unassigned",
              }
            }
            if (isAncillary) {
              // Ancillary → standalone: set assignee, ensure FK
              // null, clear floating. Date inherits the focus's
              // targetDate (the day this lane represents).
              return {
                ...d,
                primary_assignee_id: nextAssigneeId,
                attached_to_delivery_id: null,
                requested_date: targetDate,
                ancillary_is_floating: false,
                ancillary_fulfillment_status: "assigned_to_driver",
              }
            }
            // Primary delivery — just update assignee.
            return { ...d, primary_assignee_id: nextAssigneeId }
          }),
        )
      }

      try {
        if (isAncillary && nextAssigneeId === null) {
          // From-deliveries → pool: hit the endpoint. Pool source
          // can't reach this branch (early-returned above on
          // null===null).
          await returnAncillaryToPool(deliveryId)
          // Refresh pool so the now-pool item appears in the pin.
          schedulingFocus?.reloadPool()
        } else if (isAncillary && nextAssigneeId !== null && targetDate) {
          await assignAncillaryStandalone(
            deliveryId,
            nextAssigneeId,
            targetDate,
          )
        } else {
          await updateDelivery(deliveryId, {
            primary_assignee_id: nextAssigneeId,
          })
        }
        // Phase 4.2.4 — success-path reload removed. The optimistic
        // update above already reflects the backend's intended state;
        // a reload here would fire setLoading(true) on the parent
        // effect and render the loading shell → visible flash after
        // every drop. Trust optimistic state; the next manual
        // refresh (or user-initiated reload from the toolbar) picks
        // up concurrent edits from other dispatchers if any.
      } catch (e) {
        console.error("scheduling focus drag failed:", e)
        reload() // error-path reload restores authoritative state
      }
    },
    [deliveries, reload, schedulingFocus, targetDate],
  )

  const handleDragCancel = useCallback(() => {
    // Drop outside any droppable OR Esc cancels — clear overlay
    // without mutating state. Spurious clears for non-matching
    // drags (e.g. user cancels a canvas widget drag) are harmless
    // because activeDeliveryId is already null in that case.
    setActiveDeliveryId(null)
  }, [])

  // Phase 4.3b D-1 elevation. Subscribe to the elevated DndContext
  // (provided by FocusDndProvider). useDndMonitor must be called
  // inside a DndContext descendant — SchedulingKanbanCore mounts
  // inside Focus → FocusDndProvider, so the ancestor chain is
  // guaranteed in production. Tests wrap with FocusDndProvider in
  // their Harness. Listeners gate by id-prefix above; canvas
  // widget drags flow through Canvas's separate listener, not this
  // one.
  useDndMonitor({
    onDragStart: handleDragStart,
    onDragEnd: handleDragEnd,
    onDragCancel: handleDragCancel,
  })

  // Phase 4.2.5 — QuickEdit save handler. Parallels Monitor's
  // handleSaveEdit but trimmed for Focus context (no schedule-revert
  // confirmation modal; Focus dispatchers expect full control). Uses
  // optimistic-update pattern consistent with handleDragEnd:
  // updateDelivery + updateHoleDug in the background, local state
  // mutates immediately, error-path logs + closes dialog without
  // refetch.
  const handleSaveEdit = useCallback(
    async (payload: QuickEditSavePayload) => {
      const delivery = deliveries.find((d) => d.id === payload.deliveryId)
      if (!delivery) return
      const existingTc = delivery.type_config ?? {}
      const nextTc = {
        ...existingTc,
        service_time: payload.serviceTime,
      }
      // Optimistic local update so UI reflects the change before the
      // backend roundtrip finishes.
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === payload.deliveryId
            ? {
                ...d,
                primary_assignee_id: payload.assignedDriverId,
                helper_user_id: payload.helperUserId,
                driver_start_time: payload.driverStartTime
                  ? `${payload.driverStartTime}:00`
                  : null,
                special_instructions: payload.note,
                type_config: nextTc,
                hole_dug_status: payload.holeDugStatus,
              }
            : d,
        ),
      )
      setEditTarget(null)
      try {
        await updateDelivery(payload.deliveryId, {
          primary_assignee_id: payload.assignedDriverId,
          // Phase 4.3.3 — helper + start time round-trip via the
          // PATCH /delivery/deliveries/{id} endpoint. Backend
          // resolves helper_user_id through resolve_primary_
          // assignee_id (same translation contract).
          helper_user_id: payload.helperUserId,
          driver_start_time: payload.driverStartTime,
          special_instructions: payload.note,
          type_config: nextTc,
        })
        if (payload.holeDugStatus !== delivery.hole_dug_status) {
          await updateHoleDug(payload.deliveryId, payload.holeDugStatus)
        }
      } catch (e) {
        console.error("scheduling focus quick-edit save failed:", e)
        reload() // error-path only — restore authoritative state
      }
    },
    [deliveries, reload],
  )

  // Phase 4.3.3.1 — detach handler for the QuickEditDialog detach
  // button. Same shape as Monitor's handleDetachFromQuickEdit:
  // detachAncillary backend call + close dialog + reload. Optimistic
  // mutation here would have to mirror the backend's full state-
  // transition contract (clear FK, set is_floating=false, retain
  // assignee + date) which is duplicative; one round-trip + reload
  // keeps the source of truth on the server.
  const handleDetachFromQuickEdit = useCallback(
    async (deliveryId: string) => {
      try {
        await detachAncillary(deliveryId)
        setEditTarget(null)
        reload()
      } catch (e) {
        console.error("scheduling focus ancillary detach failed:", e)
        // Surface the failure inline so the user sees something
        // happened — alert is acceptable here because detach is
        // explicitly user-initiated (vs. background sync).
        // eslint-disable-next-line no-alert
        alert("Couldn't detach the ancillary. Try again.")
      }
    },
    [reload],
  )

  const handleCycleHoleDug = useCallback(
    async (delivery: DeliveryDTO, next: "unknown" | "yes" | "no") => {
      // Optimistic update — match the handleDragEnd pattern.
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === delivery.id ? { ...d, hole_dug_status: next } : d,
        ),
      )
      try {
        await updateHoleDug(delivery.id, next)
      } catch (e) {
        console.error("scheduling focus hole-dug cycle failed:", e)
        reload()
      }
    },
    [reload],
  )

  // Preview delivery for the DragOverlay (derived fresh each render
  // from authoritative `deliveries` state — stays in sync with
  // optimistic updates).
  //
  // Phase 4.3b.3.2 — also look up in pool ancillaries (drag source
  // can be the AncillaryPoolPin, whose items aren't in `deliveries`
  // until the optimistic update fires after drop). Without this
  // lookup, pool-source drags get no DragOverlay → preview renders
  // in-place via the source's transform → falls behind the kanban
  // (Phase 4.2.3 containing-block trap pattern: the source DOM
  // node is inside Canvas's transformed positioner ancestor; only
  // a `createPortal(document.body)` DragOverlay escapes it).
  //
  // The kanban's existing DragOverlay is already portaled to
  // document.body and renders a compact AncillaryCard preview when
  // `scheduling_type === "ancillary"`. Extending the lookup to
  // include the pool list means a single DragOverlay handles
  // every ancillary drag — pin source OR drawer source OR lane
  // source — with consistent visual + portal contract.
  const activeDelivery = useMemo(() => {
    if (!activeDeliveryId) return null
    const fromDeliveries = deliveries.find((d) => d.id === activeDeliveryId)
    if (fromDeliveries) return fromDeliveries
    const fromPool = schedulingFocus?.poolAncillaries.find(
      (d) => d.id === activeDeliveryId,
    )
    return fromPool ?? null
  }, [activeDeliveryId, deliveries, schedulingFocus])

  const handleFinalize = useCallback(async () => {
    if (!targetDate) return
    setFinalizing(true)
    try {
      await finalizeSchedule(targetDate)
      // Close the Focus — return pill picks up via the standard
      // Focus-primitive re-entry path.
      close()
    } catch (e) {
      console.error("finalize failed:", e)
      alert("Couldn't finalize. Try again.")
    } finally {
      setFinalizing(false)
    }
  }, [targetDate, close])

  const handleSelectDay = useCallback((iso: string) => {
    setTargetDate(iso)
    setDaySelectorOpen(false)
    // Phase 4.4.3 — date-box peek state is relative to the current
    // center date. Any-day jump resets both flags so the new center
    // date is unflanked by previously-engaged peeks.
    setPrevExpanded(false)
    setNextExpanded(false)
  }, [])

  // ── Render ────────────────────────────────────────────────────────

  if (!tenantTime || !targetDate) {
    return (
      <div
        data-slot="scheduling-focus-loading"
        className="flex h-full items-center justify-center text-body-sm text-content-muted"
      >
        Loading scheduling workspace…
      </div>
    )
  }

  const dayLabel = formatDayLabel(targetDate, tenantTime.local_date)
  const isFinalized = schedule?.state === "finalized"

  return (
    <div
      data-slot="scheduling-focus-core"
      data-target-date={targetDate}
      data-schedule-state={schedule?.state ?? "loading"}
      className="flex h-full flex-col gap-3"
    >
      {/* Header — Aesthetic Arc Session 1 (Phase 4.4.4-pre):
          [today_box] [eyebrow + H2 (clickable) + finalize-status] [day_after_box]   [Finalize]

          Aesthetic Arc Session 1 changes vs Phase 4.4.3:
          - Close button REMOVED entirely (Section 0 Restraint
            Translation Principle: backdrop click + Esc already
            dismiss; the button was decorative. Operator-respect
            says trust the user with platform conventions).
          - Header vertical rhythm tightened: gap-4 → gap-3 between
            header + body (Quietness — chrome subordinate to
            kanban primary work surface).
          - Finalize button subordinated in Commit B (brass-jewelry
            register without dominance — see step B for treatment).

          Date boxes flank the H2 cluster as primary peek/slide
          affordance (Phase 4.4.4 wires the slide animation). The H2
          itself is the popover trigger for any-day jump.
          The DaySelectorPopover wraps the H2 button, owning the
          popover open state + click-outside dismissal. */}
      <header
        data-slot="scheduling-focus-header"
        className="flex items-center justify-between gap-4"
      >
        <div className="flex flex-1 items-center gap-4 min-w-0">
          {/* Today date box — peek the day before centerDate. */}
          <DateBox
            date={addDays(targetDate, -1)}
            active={prevExpanded}
            onClick={() => setPrevExpanded((v) => !v)}
            ariaLabel={`Peek ${formatDayLabel(
              addDays(targetDate, -1),
              tenantTime.local_date,
            )}`}
          />

          {/* Center cluster — eyebrow + H2 (popover trigger) + finalize-
              status alert. min-w-0 keeps the H2 truncation working
              when the dayLabel is long (e.g. "Wednesday, December 31").

              Aesthetic Arc Session 1: H2 sized down from text-h2 to
              text-h3 — the day label is important but doesn't need
              to dominate. Section 0 British register: "the thing is
              good; you'll see if you look closely; we're not going
              to point at it." */}
          <div className="min-w-0 flex-shrink">
            <p className="text-micro uppercase tracking-wider text-content-muted">
              Scheduling
            </p>
            <DaySelectorPopover
              targetDate={targetDate}
              todayIso={tenantTime.local_date}
              open={daySelectorOpen}
              onToggle={() => setDaySelectorOpen((v) => !v)}
              onSelect={handleSelectDay}
              onDismiss={() => setDaySelectorOpen(false)}
              dayLabel={dayLabel}
            />
            {isFinalized && schedule?.finalized_at && (
              <p className="mt-1 flex items-center gap-1 text-caption text-status-success">
                <CheckCircle2Icon className="h-3.5 w-3.5" aria-hidden />
                Schedule finalized. Drag-rearrange will revert to draft.
              </p>
            )}
          </div>

          {/* Day-after date box — peek the day after centerDate. */}
          <DateBox
            date={addDays(targetDate, 1)}
            active={nextExpanded}
            onClick={() => setNextExpanded((v) => !v)}
            ariaLabel={`Peek ${formatDayLabel(
              addDays(targetDate, 1),
              tenantTime.local_date,
            )}`}
          />
        </div>

        <div className="flex flex-none items-center gap-2">
          {!isFinalized && (
            <Button
              size="sm"
              onClick={handleFinalize}
              disabled={finalizing || loading || deliveries.length === 0}
              data-slot="scheduling-focus-finalize"
            >
              {finalizing ? "Finalizing…" : `Finalize ${dayLabel.split(",")[0]}`}
            </Button>
          )}
        </div>
      </header>

      {/* Body — kanban. Unassigned leftmost; drivers alphabetical. */}
      {loading && (
        <div
          data-slot="scheduling-focus-body-loading"
          className="flex-1 flex items-center justify-center text-body-sm text-content-muted"
        >
          Loading…
        </div>
      )}
      {error && (
        <div
          role="alert"
          data-slot="scheduling-focus-error"
          className={cn(
            "rounded-md border border-status-error/30 bg-status-error-muted p-3",
            "text-body-sm text-status-error",
          )}
        >
          {error}
        </div>
      )}
      {!loading && !error && (
        // Phase 4.3b D-1 — DndContext elevated to FocusDndProvider.
        // Drag handlers registered above via useDndMonitor; this
        // fragment just renders the kanban surface + DragOverlay
        // (still portaled to body to escape the Focus positioner's
        // transform-translate3d containing block per Phase 4.2.3).
        <>
          <div
            data-slot="scheduling-focus-kanban"
            className={cn(
              "flex flex-1 flex-row gap-6 overflow-x-auto overflow-y-hidden",
              "px-1 pb-2",
              "scroll-smooth",
            )}
          >
            {/* Unassigned column — leftmost per user spec. Decide
                surface's needs-a-driver pile.
                Phase 4.3.3: Unassigned shows ONLY primary kanban
                deliveries that lack a driver. Pool ancillaries
                (no driver, floating) live in the Phase 4.3b pool
                pin widget — out of 4.3.3 scope. */}
            <SchedulingLane
              laneKey={`${targetDate}:${UNASSIGNED_LANE_ID}`}
              laneLabel="Unassigned"
              laneSubLabel="needs a driver"
              deliveries={unassignedKanban}
              scheduleFinalized={isFinalized}
              activeDeliveryId={activeDeliveryId}
              onOpenEdit={setEditTarget}
              onCycleHoleDug={handleCycleHoleDug}
              attachedAncillariesByParent={attachedAncillariesByParent}
              expandedAncillaryParents={expandedAncillaryParents}
              onToggleAncillaryExpansion={toggleAncillaryExpansion}
              isUnassignedLane
            />

            {/* Driver columns — alphabetical. All render, even empty
                (this IS the decide surface; all options visible).
                Phase 4.3.2 (r56) — laneKey + lane-match use
                driver.user_id (users.id, FK target). Portal-only
                drivers (user_id null) are skipped entirely — they
                appear nowhere on the kanban until the post-September
                follow-up lifts the portal-driver assignment gap. */}
            {sortedDrivers.map((driver) => {
              if (!driver.user_id) return null
              const laneDeliveries = kanbanByDriver.get(driver.user_id) ?? []
              const laneAncillaries =
                standaloneAncillariesByDriver.get(driver.user_id) ?? []
              return (
                <SchedulingLane
                  key={driver.id}
                  laneKey={`${targetDate}:${driver.user_id}`}
                  laneLabel={
                    driver.display_name ??
                    `Driver ${driver.license_number ?? "—"}`
                  }
                  deliveries={laneDeliveries}
                  ancillaries={laneAncillaries}
                  attachedAncillariesByParent={attachedAncillariesByParent}
                  expandedAncillaryParents={expandedAncillaryParents}
                  onToggleAncillaryExpansion={toggleAncillaryExpansion}
                  scheduleFinalized={isFinalized}
                  activeDeliveryId={activeDeliveryId}
                  onOpenEdit={setEditTarget}
                  onCycleHoleDug={handleCycleHoleDug}
                />
              )
            })}
          </div>

          {/* DragOverlay — must be portaled to document.body because
              the Focus core positioner (Focus.tsx Session 3.8.3)
              wraps the Popup subtree in `position: fixed; transform:
              translate3d(coreRect.x, coreRect.y, 0)`. A CSS transform
              on an ancestor becomes the containing block for
              `position: fixed` descendants (spec-mandated), so
              @dnd-kit's DragOverlay — which sets itself to `position:
              fixed; top: rect.top; left: rect.left` from the original
              card's `getBoundingClientRect()` (viewport coords) —
              renders offset by `(coreRect.x, coreRect.y)`: the
              "dragged card appears below-right of cursor" symptom.

              Fix: `createPortal` the DragOverlay to `document.body`.
              React context propagates through portals, so DndContext
              still reaches DragOverlay; the DOM mount at body level
              has no transformed ancestor, so fixed positioning is
              viewport-relative as intended.

              Scale 1.02 + shadow-level-3 matches PLATFORM_QUALITY_BAR
              §2 drag lift ("subtle scale 1.02-1.04; shadow-level-1 →
              shadow-level-2 typical; DragOverlay adds one more level
              because it's floating free of the lane chrome").

              The card inside DragOverlay is NOT draggable (no
              useDraggable) — it's a pure visual preview. @dnd-kit
              handles all pointer events at the context level while
              an activeId is set. */}
          {createPortal(
            <DragOverlay
              dropAnimation={{
                duration: 180,
                easing: "cubic-bezier(0.18, 0.67, 0.6, 1.22)",
              }}
              // zIndex falls back to @dnd-kit default (9999) which
              // exceeds the Focus --z-focus layer — correct; the
              // dragged card must float above the Focus chrome too.
            >
              {activeDelivery && (
                <div
                  data-slot="scheduling-focus-drag-preview"
                  data-card-type={
                    activeDelivery.scheduling_type === "ancillary"
                      ? "ancillary"
                      : "primary"
                  }
                  className="scale-[1.02] shadow-level-3 rounded-md w-[220px]"
                >
                  {/* Phase 4.3.3 — preview matches the source card
                      type (primary → DeliveryCard; standalone
                      ancillary → AncillaryCard). Lift physics +
                      width are identical so cursor grip-point
                      tracking stays accurate across both types. */}
                  {activeDelivery.scheduling_type === "ancillary" ? (
                    <AncillaryCard delivery={activeDelivery} />
                  ) : (
                    <DeliveryCard
                      delivery={activeDelivery}
                      scheduleFinalized={isFinalized}
                      density="compact"
                    />
                  )}
                </div>
              )}
            </DragOverlay>,
            document.body,
          )}
        </>
      )}

      {/* Phase 4.2.5 — QuickEdit dialog for Focus. Short-click on a
          card body calls onOpenEdit, which sets editTarget, which
          opens this dialog. Mirror of the Monitor's QuickEdit pattern
          (funeral-schedule.tsx). Rendered at the core level (outside
          the DndContext) so dialog lifecycle is independent of drag
          state. */}
      <QuickEditDialog
        delivery={editTarget}
        drivers={drivers}
        scheduleFinalized={isFinalized}
        onClose={() => setEditTarget(null)}
        onSave={handleSaveEdit}
        onDetach={handleDetachFromQuickEdit}
      />
    </div>
  )
}


// ── Scheduling lane ─────────────────────────────────────────────────


interface SchedulingLaneProps {
  laneKey: string
  laneLabel: string
  laneSubLabel?: string
  deliveries: DeliveryDTO[]
  /** Phase 4.3.3 — standalone ancillaries assigned to this driver
   *  (or to nobody, for the Unassigned lane) but NOT attached to
   *  a parent kanban delivery. Render as AncillaryCard alongside
   *  primary DeliveryCards. Empty array = no standalone ancillaries
   *  in this lane. */
  ancillaries?: DeliveryDTO[]
  /** Phase 4.3.3.1 — attached-ancillary lookup keyed by parent
   *  delivery id. Used by primary DeliveryCards to (a) render a
   *  +N count badge in the icon row and (b) render an inline
   *  expansion drawer beneath the card when the user clicks the
   *  badge. Same shape Monitor uses; Focus now mirrors it. */
  attachedAncillariesByParent?: Map<string, DeliveryDTO[]>
  /** Phase 4.3.3.1 — set of parent delivery ids whose attached-
   *  ancillary drawer is currently expanded. Threaded through from
   *  parent so state survives lane-prop reshuffles. */
  expandedAncillaryParents?: Set<string>
  /** Phase 4.3.3.1 — toggle a parent's expansion drawer. Lifted to
   *  parent so all lanes share one expansion-state set. */
  onToggleAncillaryExpansion?: (parentId: string) => void
  scheduleFinalized: boolean
  /** Phase 4.2.2 — id of the currently-dragging delivery, if any.
   *  When present AND matching a delivery in this lane, the in-lane
   *  card renders as a ghost (opacity-40 + pointer-events-none) so
   *  the user sees where the card "came from" while the DragOverlay
   *  follows the pointer. */
  activeDeliveryId?: string | null
  isUnassignedLane?: boolean
  /** Phase 4.2.5 — short-click on the card body opens QuickEdit. */
  onOpenEdit?: (delivery: DeliveryDTO) => void
  /** Phase 4.2.5 — hole-dug badge cycles via click. */
  onCycleHoleDug?: (delivery: DeliveryDTO, next: "unknown" | "yes" | "no") => void
}


function SchedulingLane({
  laneKey,
  laneLabel,
  laneSubLabel,
  deliveries,
  ancillaries = [],
  attachedAncillariesByParent,
  expandedAncillaryParents,
  onToggleAncillaryExpansion,
  scheduleFinalized,
  activeDeliveryId,
  isUnassignedLane,
  onOpenEdit,
  onCycleHoleDug,
}: SchedulingLaneProps) {
  const { setNodeRef, isOver } = useDroppable({
    id: laneKey,
    data: { laneKey },
  })

  return (
    <div
      ref={setNodeRef}
      data-slot="scheduling-focus-lane"
      data-lane={laneKey}
      data-unassigned={isUnassignedLane ? "true" : "false"}
      data-drop-over={isOver ? "true" : "false"}
      className={cn(
        // Phase 4.2.1 — 220px wide (down from 280px). Focus viewport
        // is constrained; tighter columns + compact cards show
        // more options at a glance without sacrificing readability.
        // No lane container chrome (no gray wrapper, no white box).
        // Typography-led headers + floating cards per Phase 3.3
        // canonical pattern — each card is its own material object
        // on the Focus Popup surface.
        "flex-none w-[220px] flex flex-col",
        // Drop-target affordance — brass ring on active drag. No
        // resting-state chrome per Phase 3.3.
        "transition-[box-shadow] duration-quick ease-settle",
        isOver && [
          "rounded-md",
          "ring-2 ring-brass ring-offset-4 ring-offset-surface-raised",
        ],
      )}
    >
      <div
        data-slot="scheduling-focus-lane-header"
        className={cn(
          // Typography-led header — no box, no background. Just
          // driver name + count. Reads as column label, not as
          // container chrome.
          "flex items-baseline gap-2 px-1 pb-2",
          isUnassignedLane && "italic",
        )}
      >
        <span
          className={cn(
            "text-body-sm font-medium text-content-strong truncate",
            isUnassignedLane && "text-status-warning",
          )}
          title={laneLabel}
        >
          {laneLabel}
        </span>
        {/* Phase 4.3.3 — count includes BOTH primary deliveries +
            standalone ancillaries so dispatchers see the driver's
            full stop count at a glance. Ancillary count is the
            second-class signal so it appears as "(+N)" suffix
            after the primary count when nonzero. */}
        <span
          className={cn(
            "flex-none text-caption text-content-muted tabular-nums",
            "font-plex-mono",
            deliveries.length === 0 && "text-content-subtle",
          )}
        >
          {deliveries.length}
          {ancillaries.length > 0 && (
            <span data-slot="scheduling-focus-lane-ancillary-count">
              {" + "}{ancillaries.length}
            </span>
          )}
        </span>
        {laneSubLabel && deliveries.length > 0 && (
          <span className="text-caption text-content-muted italic">
            · {laneSubLabel}
          </span>
        )}
      </div>
      <div
        data-slot="scheduling-focus-lane-body"
        className={cn(
          // space-y-2 (was space-y-3) — Phase 4.2.1 tighter card
          // rhythm pairs with the compact-density card interior.
          "flex-1 space-y-2 pb-2 overflow-y-auto",
          "min-h-[120px]",
        )}
      >
        {deliveries.length === 0 && (
          <div
            data-slot="scheduling-focus-lane-empty"
            className={cn(
              // Empty columns REMAIN VISIBLE in the Decide surface
              // (contrast with Monitor widget which hides empty
              // drivers at rest — this IS the decide workspace, all
              // options must be visible).
              //
              // Subtle drop placeholder: softer border, shorter
              // height. Reads as "open slot" not as "empty box."
              "flex h-16 items-center justify-center",
              "rounded-md border border-dashed border-border-subtle/40",
              "text-caption text-content-subtle italic",
              // Brass tint on drop hover to reinforce the lane ring.
              "data-[drop-over=true]:border-brass/40",
            )}
            data-drop-over={isOver ? "true" : "false"}
          >
            drop here
          </div>
        )}
        {deliveries.map((d) => {
          const isGhost = activeDeliveryId === d.id
          // Phase 4.3.3.1 — count + expansion state for the +N
          // ancillary badge. Same shape Monitor passes; null-safe so
          // older callers (tests with no expansion plumbing) still
          // render zero-count cards correctly.
          const attached = attachedAncillariesByParent?.get(d.id) ?? []
          const ancCount = attached.length
          const expanded = expandedAncillaryParents?.has(d.id) ?? false
          return (
            <div
              key={d.id}
              data-slot="scheduling-focus-card-slot"
              data-ghost={isGhost ? "true" : "false"}
              className={cn(
                "transition-opacity duration-quick ease-settle",
                // Phase 4.2.2 — the card at the drag origin renders
                // as a ghost while the DragOverlay handles the
                // floating preview. Opacity 40% keeps the "where it
                // came from" hint without stealing visual weight from
                // the overlay. pointer-events:none is belt-and-
                // suspenders — @dnd-kit already routes pointer events
                // to the overlay while dragging.
                isGhost && "opacity-40 pointer-events-none",
              )}
            >
              <DeliveryCard
                delivery={d}
                scheduleFinalized={scheduleFinalized}
                // Phase 4.2.1 — Focus surface uses compact density so
                // more cards fit the constrained viewport. Monitor
                // widget keeps the default density (no prop =
                // "default").
                density="compact"
                // Phase 4.2.5 — wire short-click → QuickEdit +
                // hole-dug cycle. Threaded from the core via lane
                // props. Pre-4.2.5 the Focus DeliveryCard had no
                // click handler at all — short-clicks were silent.
                onOpenEdit={onOpenEdit}
                onCycleHoleDug={onCycleHoleDug}
                // Phase 4.3.3.1 — attached-ancillary count + expansion
                // parity with Monitor.
                ancillaryCount={ancCount}
                ancillaryExpanded={expanded}
                onToggleAncillary={onToggleAncillaryExpansion}
              />
              {/* Phase 4.3.3.1 — expansion drawer below the parent card.
                  Mirrors Monitor's pattern (FuneralScheduleDayColumn).
                  Each attached ancillary is a click-to-edit button (NOT
                  a drag source — drag-to-detach is Phase 4.3b). */}
              {expanded && attached.length > 0 && (
                <div
                  data-slot="dispatch-ancillary-expanded"
                  className={cn(
                    "mt-1.5 ml-4 space-y-1 rounded-md border-l-2 border-brass/40",
                    "bg-surface-sunken/60 px-3 py-2",
                  )}
                >
                  {attached.map((a) => (
                    <DrawerAncillaryItem
                      key={a.id}
                      ancillary={a}
                      onOpenEdit={onOpenEdit}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}
        {/* Phase 4.3.3 — standalone ancillaries render after primary
            deliveries in the same lane. Visual hierarchy: primaries
            first (the dispatcher's main scheduling decisions),
            ancillaries second (independent stops). Same drag id
            format `delivery:${id}` so the parent's onDragEnd treats
            both card types uniformly. */}
        {ancillaries.map((a) => {
          const isGhost = activeDeliveryId === a.id
          return (
            <div
              key={a.id}
              data-slot="scheduling-focus-card-slot"
              data-card-type="ancillary"
              data-ghost={isGhost ? "true" : "false"}
              className={cn(
                "transition-opacity duration-quick ease-settle",
                isGhost && "opacity-40 pointer-events-none",
              )}
            >
              <AncillaryCard
                delivery={a}
                onOpenEdit={onOpenEdit}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ── Day selector popover ────────────────────────────────────────────
//
// Phase B Session 4.4.3 — refactored from `DaySelectorButton` (a
// separate "Change day" sub-button next to the H2) to
// `DaySelectorPopover` (a wrapper that makes the H2 itself the
// popover trigger). Per Section 0 Restraint Translation Principle:
// the standalone trigger button was decorative — H2 carries both
// the date display AND the interaction affordance, so the sub-
// button can come out without losing function.
//
// The popover content + click-outside + listbox semantics are
// preserved verbatim from the prior DaySelectorButton.


interface DaySelectorPopoverProps {
  targetDate: string
  todayIso: string
  open: boolean
  onToggle: () => void
  onSelect: (iso: string) => void
  onDismiss: () => void
  /** Pre-formatted full day label (e.g. "Wednesday, April 25") —
   *  rendered as the H2 button content. The parent already computes
   *  this for the finalize button copy ("Finalize Wednesday"); this
   *  prop avoids a duplicate computation. */
  dayLabel: string
}


function DaySelectorPopover({
  targetDate,
  todayIso,
  open,
  onToggle,
  onSelect,
  onDismiss,
  dayLabel,
}: DaySelectorPopoverProps) {
  // Offer Today through +6 days — a dispatcher's typical planning
  // horizon. Same options list the prior DaySelectorButton offered.
  const options = useMemo(() => {
    const out: Array<{ iso: string; label: string }> = []
    for (let i = 0; i <= 6; i++) {
      const iso = addDays(todayIso, i)
      out.push({
        iso,
        label: formatDayLabel(iso, todayIso),
      })
    }
    return out
  }, [todayIso])

  // Click-outside to dismiss — preserved from DaySelectorButton.
  const containerRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current) return
      if (containerRef.current.contains(e.target as Node)) return
      onDismiss()
    }
    window.addEventListener("mousedown", onClick)
    return () => window.removeEventListener("mousedown", onClick)
  }, [open, onDismiss])

  return (
    <div ref={containerRef} className="relative inline-block mt-0.5">
      {/* H2 button — the trigger surface. Typography-first: looks
          like a heading, behaves like a button. The chevron sits
          inline at heading scale to read as a visible-but-quiet
          "this is interactive" affordance without competing with
          the day label.

          Aesthetic Arc Session 1: heading sized down from text-h2
          to text-h3 — the day label is important but doesn't need
          to dominate the surface. Section 0 Quietness Translation
          Principle 5 + British register ("the thing is good;
          you'll see if you look closely; we're not going to point
          at it"). Kanban is the primary work surface; chrome
          subordinates to it. */}
      <button
        type="button"
        onClick={onToggle}
        data-slot="scheduling-focus-day-selector"
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "inline-flex items-baseline gap-1.5",
          "text-h3 font-medium leading-none text-content-strong",
          "font-plex-sans tracking-tight",
          // Subtle hover affordance — text shifts slightly toward
          // brass family. Restraint over loud color flip.
          "hover:text-brass-hover transition-colors duration-quick ease-settle",
          // Brass focus ring + slight padding so the ring has room
          // to render around the heading without cropping.
          "focus-ring-brass outline-none rounded-sm px-1 -mx-1",
        )}
      >
        <span>{dayLabel}</span>
        <ChevronDownIcon
          className={cn(
            "h-4 w-4 self-center text-content-muted",
            "transition-transform duration-quick",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {open && (
        <div
          role="listbox"
          data-slot="scheduling-focus-day-selector-menu"
          className={cn(
            "absolute left-0 top-full z-10 mt-1 min-w-[220px]",
            "rounded-md border border-border-subtle bg-surface-raised",
            "shadow-level-2 py-1",
            "duration-settle ease-settle animate-in fade-in-0 zoom-in-95",
          )}
        >
          {options.map((opt) => {
            const active = opt.iso === targetDate
            return (
              <button
                key={opt.iso}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => onSelect(opt.iso)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-body-sm",
                  "hover:bg-brass-subtle/40 transition-colors duration-quick",
                  "focus-ring-brass outline-none",
                  active && "bg-brass-subtle text-content-strong",
                )}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}


// ── Drawer ancillary item (Phase 4.3b.4) ─────────────────────────────


interface DrawerAncillaryItemProps {
  ancillary: DeliveryDTO
  onOpenEdit?: (delivery: DeliveryDTO) => void
}


/**
 * Expanded-drawer ancillary row — one entry per attached ancillary
 * inside a parent kanban delivery's expansion drawer (Phase 4.3.3.1
 * shipped the drawer; Phase 4.3.3.1 pre-positioned data-slot +
 * data-ancillary-id; Phase 4.3b.4 adds the drag wiring).
 *
 * Drag source: id = `ancillary:<id>` matching the AncillaryPoolPin
 * + standalone-card drag sources. SchedulingKanbanCore's drag
 * handler routes the drop:
 *   - Driver lane (different driver) → assignAncillaryStandalone
 *     (FK clears, new assignee + parent's date)
 *   - Driver lane (same driver as parent) → assignAncillaryStandalone
 *     ("detach but keep with this driver")
 *   - Unassigned lane → returnAncillaryToPool
 *   - Pin (ancillary-pool droppable) → returnAncillaryToPool
 *   - Different parent card → attachAncillary (re-attach)
 *
 * Click vs drag: PointerSensor activation constraint (distance: 8)
 * separates them. Quick click (release within 8px) fires
 * onOpenEdit. Press + drag past 8px activates drag, suppresses
 * click. Same pattern as DeliveryCard / AncillaryCard / PoolItem.
 *
 * Whole-element drag per PRODUCT_PRINCIPLES "Drag interactions:
 * whole-element drag, no handles" — useDraggable listeners spread
 * on the entire button. No grip icon.
 */
function DrawerAncillaryItem({
  ancillary,
  onOpenEdit,
}: DrawerAncillaryItemProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `ancillary:${ancillary.id}`,
      data: { ancillaryId: ancillary.id, source: "drawer" },
    })
  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  const tc = ancillary.type_config ?? {}
  const family = (tc.family_name as string | undefined) ?? "—"
  const stype = (tc.service_type as string | undefined) ?? ""

  return (
    <button
      ref={setNodeRef}
      style={dragStyle}
      type="button"
      data-slot="dispatch-ancillary-expanded-item"
      data-ancillary-id={ancillary.id}
      data-dragging={isDragging ? "true" : "false"}
      {...attributes}
      {...listeners}
      onClick={() => onOpenEdit?.(ancillary)}
      className={cn(
        "w-full text-left text-caption",
        "text-content-base hover:text-content-strong",
        "focus-ring-brass outline-none rounded",
        "px-1 py-0.5",
        "cursor-grab active:cursor-grabbing",
        // Phase 4.3b.4 drag lift — subtle scale + opacity dim per
        // PQB §2 canonical drag-source contract. Smaller scale than
        // DeliveryCard (1.01 vs 1.02) because drawer items are
        // already compact + indented; bigger scale would feel
        // disproportionate.
        isDragging && "opacity-95 scale-[1.01] bg-brass-subtle/60",
      )}
    >
      <span className="font-medium">{family}</span>
      {stype && (
        <span className="ml-2 text-content-muted">
          · {stype.replace(/_/g, " ")}
        </span>
      )}
    </button>
  )
}
