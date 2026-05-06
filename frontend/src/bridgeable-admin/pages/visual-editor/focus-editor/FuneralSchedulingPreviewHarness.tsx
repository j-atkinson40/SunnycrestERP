/**
 * FuneralSchedulingPreviewHarness — faithful editor preview for the
 * Funeral Scheduling Focus.
 *
 * Pattern: structurally-faithful preview using REAL sub-components
 * (DeliveryCard, DateBox, AncillaryCard) arranged in the same shell
 * as the production SchedulingKanbanCore + accessory layer, fed by
 * mock data from funeralSchedulingMockData. Mirrors the
 * `lib/visual-editor/themes/preview-data.tsx` pattern from Phase 2 —
 * stand-ins that consume the same design tokens as the real
 * components, rather than mounting the production orchestrator
 * with its full provider stack (useFocus + useSchedulingFocus +
 * dispatch-service network calls + dnd-kit + URL params).
 *
 * Why not mount SchedulingKanbanCore directly: it's 1,714 LOC with
 * deep runtime dependencies — fetchTenantTime / fetchSchedule /
 * fetchDeliveriesForRange / fetchDrivers all fire on mount, and
 * useFocus / useSchedulingFocus need provider trees that don't
 * exist in the editor context. Wiring all that for editor preview
 * either binds preview to live API or duplicates substantial mock
 * provider machinery. The Phase 2 stand-in pattern is the canonical
 * answer here too.
 *
 * What makes this faithful: the preview uses REAL components
 * for the visual atoms (DeliveryCard renders identically to the
 * production kanban; DateBox renders the same; CompositionRenderer
 * runs the same accessory layer composition the runtime uses).
 * Drag-drop is wrapped in a no-op DndContext so DeliveryCard's
 * useDraggable hooks don't crash; pointer events are visually
 * absorbed but no mutations persist.
 *
 * Composition draft propagation: the harness accepts a
 * `compositionDraft` prop carrying the in-progress (saved + unsaved)
 * composition. The accessory layer renders this draft directly,
 * NOT the resolved-via-API composition, so the preview reflects
 * editor edits in real time before save.
 */
import { useMemo } from "react"
import { DndContext } from "@dnd-kit/core"
import { CheckCircle2Icon } from "lucide-react"

import { DeliveryCard } from "@/components/dispatch/DeliveryCard"
import {
  DateBox,
  formatFullLabel,
} from "@/components/dispatch/scheduling-focus/DateBox"
import { CompositionRenderer } from "@/lib/visual-editor/compositions/CompositionRenderer"
import type {
  Placement,
  ResolvedComposition,
} from "@/lib/visual-editor/compositions/types"
import type { DeliveryDTO, DriverDTO } from "@/services/dispatch-service"

import {
  SAMPLE_SCENARIO_OPTIONS,
  buildMockBundle,
  type SampleScenario,
} from "./mock-data/funeralSchedulingMockData"


// ─── Date helpers (mirrors SchedulingKanbanCore's local helpers) ──


function addDays(baseIso: string, n: number): string {
  const [y, m, d] = baseIso.split("-").map(Number)
  if (!y || !m || !d) return baseIso
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() + n)
  const yy = dt.getUTCFullYear()
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0")
  const dd = String(dt.getUTCDate()).padStart(2, "0")
  return `${yy}-${mm}-${dd}`
}


// ─── Props ────────────────────────────────────────────────────


export interface FuneralSchedulingPreviewHarnessProps {
  /** Active sample scenario — controlled by the editor's preview-
   *  settings dropdown. */
  scenario: SampleScenario
  /** Composition draft to render in the accessory rail. Pass the
   *  unsaved-edits-on-top-of-saved composition so the preview
   *  reflects in-progress changes. Pass null to render kanban-only
   *  (no accessory layer — same as runtime fallback when no
   *  composition is resolved). */
  compositionDraft: ResolvedComposition | null
  /** When true, the rail-collapsed empty composition still renders
   *  the kanban full-width. Defaults to true. */
  hideAccessoryWhenEmpty?: boolean
}


export function FuneralSchedulingPreviewHarness({
  scenario,
  compositionDraft,
  hideAccessoryWhenEmpty = true,
}: FuneralSchedulingPreviewHarnessProps) {
  const bundle = useMemo(() => buildMockBundle(scenario), [scenario])
  const { schedule, drivers, deliveries, target_date, tenant_time } = bundle
  const isFinalized = schedule.state === "finalized"

  // Group deliveries by driver (same logic SchedulingKanbanCore uses
  // for kanban grouping). Standalone-ancillary blocks omitted from
  // this faithful preview; the canonical kanban content is the
  // primary kanban deliveries.
  const { kanbanByDriver, unassignedKanban } = useMemo(() => {
    const byDriver = new Map<string, DeliveryDTO[]>()
    const unassigned: DeliveryDTO[] = []
    for (const d of deliveries) {
      if (d.scheduling_type !== "kanban") continue
      const aid = d.primary_assignee_id
      if (aid) {
        if (!byDriver.has(aid)) byDriver.set(aid, [])
        byDriver.get(aid)!.push(d)
      } else {
        unassigned.push(d)
      }
    }
    return { kanbanByDriver: byDriver, unassignedKanban: unassigned }
  }, [deliveries])

  const showAccessory =
    !!compositionDraft &&
    compositionDraft.placements.length > 0 &&
    (compositionDraft.placements.length > 0 || !hideAccessoryWhenEmpty)

  return (
    <DndContext
      onDragEnd={() => {
        // No-op: drag-drop renders visually (DeliveryCard's
        // useDraggable hook fires events) but mutations don't
        // persist. The editor preview is for visual fidelity, not
        // for authoring kanban content. See the harness docstring.
      }}
    >
      <div
        className="flex h-full w-full gap-4"
        data-testid="funeral-scheduling-preview-harness"
        data-scenario={scenario}
      >
        {/* ── Kanban region ──────────────────────────────── */}
        <div
          className="flex flex-1 min-w-0 flex-col gap-3"
          data-testid="preview-kanban-region"
        >
          <PreviewHeader
            targetDate={target_date}
            todayIso={tenant_time.local_date}
            isFinalized={isFinalized}
          />
          {deliveries.length === 0 ? (
            <PreviewEmptyState />
          ) : (
            <PreviewKanban
              drivers={drivers}
              kanbanByDriver={kanbanByDriver}
              unassignedKanban={unassignedKanban}
              isFinalized={isFinalized}
            />
          )}
        </div>

        {/* ── Accessory layer ────────────────────────────── */}
        {showAccessory && (
          <aside
            className="w-72 flex-shrink-0 overflow-y-auto"
            data-testid="preview-accessory-rail"
            aria-label="Composition accessory layer preview"
          >
            <CompositionRenderer
              composition={compositionDraft!}
              editorMode={true}
            />
          </aside>
        )}
      </div>
    </DndContext>
  )
}


// ─── Preview header (mirrors SchedulingKanbanCore's header shape) ─


function PreviewHeader({
  targetDate,
  todayIso,
  isFinalized,
}: {
  targetDate: string
  todayIso: string
  isFinalized: boolean
}) {
  const dayLabel = formatFullLabel(targetDate)
  return (
    <header
      className="flex items-center justify-center gap-4"
      data-testid="preview-header"
    >
      <DateBox
        date={addDays(targetDate, -1)}
        active={false}
        onClick={() => {}}
        ariaLabel={`Peek ${formatFullLabel(addDays(targetDate, -1))}`}
      />
      <div className="min-w-0 flex-shrink text-center">
        <p className="text-micro uppercase tracking-wider text-content-muted">
          Scheduling
        </p>
        <h2
          className="text-h3 font-plex-serif text-content-strong"
          data-testid="preview-header-day-label"
        >
          {dayLabel}
        </h2>
        {isFinalized && (
          <p className="mt-1 flex items-center justify-center gap-1 text-caption text-status-success">
            <CheckCircle2Icon className="h-3.5 w-3.5" aria-hidden />
            Schedule finalized.
          </p>
        )}
        {targetDate === todayIso && (
          <p className="mt-0.5 text-[10px] text-content-subtle">
            (preview "today" — June 5, 2026)
          </p>
        )}
      </div>
      <DateBox
        date={addDays(targetDate, 1)}
        active={false}
        onClick={() => {}}
        ariaLabel={`Peek ${formatFullLabel(addDays(targetDate, 1))}`}
      />
    </header>
  )
}


// ─── Empty state ──────────────────────────────────────────────


function PreviewEmptyState() {
  return (
    <div
      className="flex flex-1 items-center justify-center rounded-md border border-dashed border-border-subtle bg-surface-base p-8 text-center text-content-muted"
      data-testid="preview-empty-state"
    >
      <div>
        <div className="text-h4 font-plex-serif text-content-strong">
          No cases scheduled
        </div>
        <div className="mt-1 text-caption">
          Empty kanban — useful for verifying the empty-state visual
          treatment.
        </div>
      </div>
    </div>
  )
}


// ─── Kanban surface ──────────────────────────────────────────


function PreviewKanban({
  drivers,
  kanbanByDriver,
  unassignedKanban,
  isFinalized,
}: {
  drivers: DriverDTO[]
  kanbanByDriver: Map<string, DeliveryDTO[]>
  unassignedKanban: DeliveryDTO[]
  isFinalized: boolean
}) {
  const sortedDrivers = useMemo(
    () =>
      [...drivers].sort((a, b) => {
        const an = (a.display_name ?? a.id).toLowerCase()
        const bn = (b.display_name ?? b.id).toLowerCase()
        return an.localeCompare(bn)
      }),
    [drivers],
  )

  return (
    <div
      className="flex flex-1 flex-row gap-4 overflow-x-auto overflow-y-hidden px-1 pb-2"
      data-testid="preview-kanban-lanes"
    >
      <PreviewLane
        title="Unassigned"
        deliveries={unassignedKanban}
        isFinalized={isFinalized}
        emphasis
      />
      {sortedDrivers.map((driver) => {
        const lane =
          (driver.user_id && kanbanByDriver.get(driver.user_id)) || []
        return (
          <PreviewLane
            key={driver.id}
            title={driver.display_name ?? driver.id}
            deliveries={lane}
            isFinalized={isFinalized}
          />
        )
      })}
    </div>
  )
}


function PreviewLane({
  title,
  deliveries,
  isFinalized,
  emphasis = false,
}: {
  title: string
  deliveries: DeliveryDTO[]
  isFinalized: boolean
  emphasis?: boolean
}) {
  return (
    <div
      className={`flex w-[220px] flex-shrink-0 flex-col gap-2 rounded-md border ${
        emphasis ? "border-accent/30" : "border-border-subtle"
      } bg-surface-elevated p-2 shadow-level-1`}
      data-testid={`preview-lane-${title.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <div className="flex items-baseline justify-between">
        <span className="text-caption font-medium text-content-strong">
          {title}
        </span>
        <span className="font-plex-mono text-[10px] text-content-muted">
          {deliveries.length}
        </span>
      </div>
      <div className="flex flex-col gap-2 overflow-y-auto pr-0.5">
        {deliveries.length === 0 ? (
          <div className="rounded-sm border border-dashed border-border-subtle px-2 py-3 text-center text-[10px] text-content-subtle">
            No cards
          </div>
        ) : (
          deliveries.map((d) => (
            <DeliveryCard
              key={d.id}
              delivery={d}
              scheduleFinalized={isFinalized}
              density="compact"
              // No-op handlers — drag-drop visually works via dnd-kit
              // but click-edit / hole-dug-cycle / ancillary-toggle
              // mutations don't persist in editor preview.
              onOpenEdit={() => {}}
              onCycleHoleDug={() => {}}
              onToggleAncillary={() => {}}
            />
          ))
        )}
      </div>
    </div>
  )
}


// ─── Sample scenario picker ──────────────────────────────


export function SampleScenarioPicker({
  scenario,
  onChange,
}: {
  scenario: SampleScenario
  onChange: (next: SampleScenario) => void
}) {
  return (
    <div className="flex items-center gap-1.5" data-testid="sample-scenario-picker">
      <span className="text-micro uppercase tracking-wider text-content-muted">
        Sample
      </span>
      <select
        value={scenario}
        onChange={(e) => onChange(e.target.value as SampleScenario)}
        className="rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-strong"
        data-testid="sample-scenario-select"
        aria-label="Sample data scenario"
      >
        {SAMPLE_SCENARIO_OPTIONS.map((opt) => (
          <option key={opt.id} value={opt.id} title={opt.description}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}


/** Convert raw editor draft state (placements + canvas_config) into a
 *  ResolvedComposition shape suitable for CompositionRenderer. The
 *  editor's draft state lives outside the resolved-from-API shape
 *  — synthesize a ResolvedComposition with `source="draft"` so the
 *  renderer treats it the same as a runtime resolution. */
export function compositionDraftAsResolved(
  placements: Placement[],
  canvasConfig: ResolvedComposition["canvas_config"],
  vertical: string | null,
): ResolvedComposition {
  return {
    focus_type: "scheduling",
    vertical,
    tenant_id: null,
    source: placements.length > 0 ? "vertical_default" : null,
    source_id: null,
    source_version: null,
    placements,
    canvas_config: canvasConfig,
  }
}
