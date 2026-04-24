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
 *     assigned_driver_id; optimistic UI + reload on completion.
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
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import { CheckCircle2Icon, ChevronDownIcon, XIcon } from "lucide-react"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useSearchParams } from "react-router-dom"

import { DeliveryCard } from "@/components/dispatch/DeliveryCard"
import { Button } from "@/components/ui/button"
import { useFocus } from "@/contexts/focus-context"
import { cn } from "@/lib/utils"
import {
  fetchDeliveriesForRange,
  fetchDrivers,
  fetchSchedule,
  fetchTenantTime,
  finalizeSchedule,
  updateDelivery,
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

  // Group deliveries by driver (kanban-scheduling only; ancillary +
  // direct-ship are out of scope for 4.2).
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

  const handleDragEnd = useCallback(
    async (ev: DragEndEvent) => {
      const { active, over } = ev
      if (!over) return
      const deliveryId = String(active.id).replace(/^delivery:/, "")
      const laneKey = String(over.id)
      // Lane format: "YYYY-MM-DD:<driverId | __UNASSIGNED__>"
      const sep = laneKey.indexOf(":")
      if (sep === -1) return
      const targetDriverRaw = laneKey.slice(sep + 1)
      const nextDriverId =
        targetDriverRaw === UNASSIGNED_LANE_ID ? null : targetDriverRaw
      const delivery = deliveries.find((d) => d.id === deliveryId)
      if (!delivery) return
      if (delivery.assigned_driver_id === nextDriverId) return

      // Optimistic UI
      setDeliveries((prev) =>
        prev.map((d) =>
          d.id === deliveryId
            ? { ...d, assigned_driver_id: nextDriverId }
            : d,
        ),
      )
      try {
        await updateDelivery(deliveryId, {
          assigned_driver_id: nextDriverId,
        })
        reload()
      } catch (e) {
        console.error("scheduling focus drag failed:", e)
        reload() // reload will re-fetch authoritative state
      }
    },
    [deliveries, reload],
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
        <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
          <div
            data-slot="scheduling-focus-kanban"
            className={cn(
              "flex flex-1 flex-row gap-6 overflow-x-auto overflow-y-hidden",
              "px-1 pb-2",
              "scroll-smooth",
            )}
          >
            {/* Unassigned column — leftmost per user spec. Decide
                surface's needs-a-driver pile. */}
            <SchedulingLane
              laneKey={`${targetDate}:${UNASSIGNED_LANE_ID}`}
              laneLabel="Unassigned"
              laneSubLabel="needs a driver"
              deliveries={unassignedKanban}
              scheduleFinalized={isFinalized}
              isUnassignedLane
            />

            {/* Driver columns — alphabetical. All render, even empty
                (this IS the decide surface; all options visible). */}
            {sortedDrivers.map((driver) => {
              const laneDeliveries = kanbanByDriver.get(driver.id) ?? []
              return (
                <SchedulingLane
                  key={driver.id}
                  laneKey={`${targetDate}:${driver.id}`}
                  laneLabel={
                    driver.display_name ??
                    `Driver ${driver.license_number ?? "—"}`
                  }
                  deliveries={laneDeliveries}
                  scheduleFinalized={isFinalized}
                />
              )
            })}
          </div>
        </DndContext>
      )}
    </div>
  )
}


// ── Scheduling lane ─────────────────────────────────────────────────


interface SchedulingLaneProps {
  laneKey: string
  laneLabel: string
  laneSubLabel?: string
  deliveries: DeliveryDTO[]
  scheduleFinalized: boolean
  isUnassignedLane?: boolean
}


function SchedulingLane({
  laneKey,
  laneLabel,
  laneSubLabel,
  deliveries,
  scheduleFinalized,
  isUnassignedLane,
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
        "flex-none w-[280px] flex flex-col",
        // Drop-target affordance — brass ring on active drag. No
        // resting-state chrome.
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
          "flex items-baseline gap-2 px-1 pb-3",
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
        <span
          className={cn(
            "flex-none text-caption text-content-muted tabular-nums",
            "font-plex-mono",
            deliveries.length === 0 && "text-content-subtle",
          )}
        >
          {deliveries.length}
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
          "flex-1 space-y-3 pb-2 overflow-y-auto",
          "min-h-[120px]",
        )}
      >
        {deliveries.length === 0 && (
          <div
            data-slot="scheduling-focus-lane-empty"
            className={cn(
              "flex h-24 items-center justify-center",
              "rounded-md border border-dashed border-border-subtle/60",
              "text-caption text-content-subtle italic",
            )}
          >
            drop here
          </div>
        )}
        {deliveries.map((d) => (
          <DeliveryCard
            key={d.id}
            delivery={d}
            scheduleFinalized={scheduleFinalized}
          />
        ))}
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
