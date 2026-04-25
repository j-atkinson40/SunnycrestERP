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
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { CheckCircle2Icon, ChevronDownIcon, XIcon } from "lucide-react"
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
import {
  QuickEditDialog,
  type QuickEditSavePayload,
} from "@/components/dispatch/QuickEditDialog"
import { Button } from "@/components/ui/button"
import { useFocus } from "@/contexts/focus-context"
import { cn } from "@/lib/utils"
import {
  assignAncillaryStandalone,
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

  const reload = useCallback(() => {
    setRefreshTick((n) => n + 1)
  }, [])

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

  // Drag sensors — 8px activation matches the Monitor widget.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

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

  const handleDragStart = useCallback((ev: DragStartEvent) => {
    const id = String(ev.active.id).replace(/^delivery:/, "")
    setActiveDeliveryId(id)
  }, [])

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      // Clear the overlay preview regardless of drop validity.
      setActiveDeliveryId(null)
      const { active, over } = ev
      if (!over) return
      const deliveryId = String(active.id).replace(/^delivery:/, "")
      const laneKey = String(over.id)
      // Lane format: "YYYY-MM-DD:<driverId | __UNASSIGNED__>"
      const sep = laneKey.indexOf(":")
      if (sep === -1) return
      const targetDriverRaw = laneKey.slice(sep + 1)
      // Phase 4.3.2 (r56) — lane keys carry user_id (users.id) values,
      // not driver.id. The parsed raw value is ready to ship to the
      // backend's primary_assignee_id field.
      const nextAssigneeId =
        targetDriverRaw === UNASSIGNED_LANE_ID ? null : targetDriverRaw
      const delivery = deliveries.find((d) => d.id === deliveryId)
      if (!delivery) return
      if (delivery.primary_assignee_id === nextAssigneeId) return

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
      const isAncillary = delivery.scheduling_type === "ancillary"

      // Optimistic UI — local state reflects the new assignment
      // immediately. Backend PATCH runs in the background; only
      // the error path re-fetches authoritative state.
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
      try {
        if (isAncillary && nextAssigneeId === null) {
          await returnAncillaryToPool(deliveryId)
        } else if (isAncillary && targetDate) {
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
    [deliveries, reload, targetDate],
  )

  const handleDragCancel = useCallback(() => {
    // Drop outside any droppable OR Esc cancels — clear overlay
    // without mutating state.
    setActiveDeliveryId(null)
  }, [])

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
  const activeDelivery = useMemo(
    () =>
      activeDeliveryId
        ? deliveries.find((d) => d.id === activeDeliveryId) ?? null
        : null,
    [activeDeliveryId, deliveries],
  )

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
      className="flex h-full flex-col gap-4"
    >
      {/* Header — day label + day selector + finalize action */}
      <header
        data-slot="scheduling-focus-header"
        className="flex items-start justify-between gap-4"
      >
        <div className="min-w-0">
          <p className="text-micro uppercase tracking-wider text-content-muted">
            Scheduling
          </p>
          <div className="mt-0.5 flex items-center gap-2">
            <h2
              className={cn(
                "text-h2 font-medium leading-none text-content-strong",
                "font-plex-sans tracking-tight",
              )}
            >
              {dayLabel}
            </h2>
            <DaySelectorButton
              targetDate={targetDate}
              todayIso={tenantTime.local_date}
              open={daySelectorOpen}
              onToggle={() => setDaySelectorOpen((v) => !v)}
              onSelect={handleSelectDay}
              onDismiss={() => setDaySelectorOpen(false)}
            />
          </div>
          {isFinalized && schedule?.finalized_at && (
            <p className="mt-1 flex items-center gap-1 text-caption text-status-success">
              <CheckCircle2Icon className="h-3.5 w-3.5" aria-hidden />
              Schedule finalized. Drag-rearrange will revert to draft.
            </p>
          )}
        </div>

        <div className="flex flex-none items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={close}
            data-slot="scheduling-focus-close"
            aria-label="Close scheduling Focus"
          >
            <XIcon className="h-4 w-4" aria-hidden />
            Close
          </Button>
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
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
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
        </DndContext>
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
                  {attached.map((a) => {
                    const tc = a.type_config ?? {}
                    const family =
                      (tc.family_name as string | undefined) ?? "—"
                    const stype =
                      (tc.service_type as string | undefined) ?? ""
                    return (
                      <button
                        key={a.id}
                        type="button"
                        data-slot="dispatch-ancillary-expanded-item"
                        data-ancillary-id={a.id}
                        onClick={() => onOpenEdit?.(a)}
                        className={cn(
                          "w-full text-left text-caption",
                          "text-content-base hover:text-content-strong",
                          "focus-ring-brass outline-none rounded",
                          "px-1 py-0.5",
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
                  })}
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


// ── Day selector (compact popover) ──────────────────────────────────


interface DaySelectorButtonProps {
  targetDate: string
  todayIso: string
  open: boolean
  onToggle: () => void
  onSelect: (iso: string) => void
  onDismiss: () => void
}


function DaySelectorButton({
  targetDate,
  todayIso,
  open,
  onToggle,
  onSelect,
  onDismiss,
}: DaySelectorButtonProps) {
  // Offer Today through +6 days — a dispatcher's typical planning
  // horizon. Rendered as a simple menu; no external popover library
  // dependency (keeps this core self-contained for 4.2).
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

  // Click-outside to dismiss — same pattern as the legacy ad-hoc
  // dropdowns in ancillary-panel. For 4.2 this is inline; if we grow
  // more menu-like affordances in the Focus we'll refactor onto the
  // Popover primitive.
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
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={onToggle}
        data-slot="scheduling-focus-day-selector"
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          "inline-flex items-center gap-1 rounded-sm px-1.5 py-1 -my-1",
          "text-caption font-medium text-brass hover:text-brass-hover",
          "hover:bg-brass-subtle/40",
          "transition-colors duration-quick ease-settle",
          "focus-ring-brass outline-none",
        )}
      >
        Change day
        <ChevronDownIcon
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-quick",
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
