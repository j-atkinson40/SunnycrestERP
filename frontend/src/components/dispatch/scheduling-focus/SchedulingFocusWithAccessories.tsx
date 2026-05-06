/**
 * SchedulingFocusWithAccessories — composition-runtime wrapper around
 * the bespoke `SchedulingKanbanCore`.
 *
 * Implements the **accessory layer pattern** for the May 2026
 * composition runtime integration phase. The bespoke kanban core
 * (1,714 LOC of dispatcher operational behavior — drag-drop, finalize,
 * date selection, ancillary pin, QuickEdit dialog) renders unchanged
 * in the primary content area. A composition-driven accessory region
 * mounts to the right when the active composition (looked up by
 * `compositionFocusType="scheduling"` + tenant vertical) has any
 * placements.
 *
 *   ┌── Focus surface ──────────────────────────────────────────┐
 *   │ ┌── kanban region (flex-1) ──┐ ┌── accessory rail ──────┐ │
 *   │ │                             │ │                         │ │
 *   │ │   <SchedulingKanbanCore />  │ │  <CompositionRenderer/> │ │
 *   │ │   (unchanged operational    │ │  editorMode={false}     │ │
 *   │ │    surface — drag, finalize,│ │  → real widgets via     │ │
 *   │ │    date select, scribe, etc.)│ │   getWidgetRenderer    │ │
 *   │ │                             │ │                         │ │
 *   │ └─────────────────────────────┘ └─────────────────────────┘ │
 *   └────────────────────────────────────────────────────────────┘
 *
 * Fallback semantics:
 *   - Composition resolution loading → render kanban only (avoid
 *     flash of accessory rail showing-then-hiding).
 *   - No composition exists at any inheritance scope → render kanban
 *     only, full width.
 *   - Composition exists but is empty (zero placements) → render
 *     kanban only, full width.
 *   - Composition exists with placements → render kanban + accessory
 *     rail.
 *
 * Hard constraint: the kanban core's operational behavior is preserved
 * exactly. Drag-drop spans `<FocusDndProvider>` mounted at Focus.tsx
 * level, so accessory widgets cannot accidentally hijack a drag (their
 * sibling DOM positioning leaves dnd-kit's pointer sensor focused on
 * the kanban region naturally). The accessory rail is `pointer-events:
 * auto` for its own interactions but never wraps the kanban tree.
 */
import { useAuth } from "@/contexts/auth-context"
import { CompositionRenderer } from "@/lib/visual-editor/compositions/CompositionRenderer"
import { useResolvedComposition } from "@/lib/visual-editor/compositions/useResolvedComposition"

import { SchedulingKanbanCore } from "./SchedulingKanbanCore"

import type { FocusConfig } from "@/contexts/focus-registry"


export interface SchedulingFocusWithAccessoriesProps {
  focusId: string
  config: FocusConfig
}


export function SchedulingFocusWithAccessories({
  focusId,
  config,
}: SchedulingFocusWithAccessoriesProps) {
  const { company } = useAuth()
  const compositionFocusType = config.compositionFocusType ?? config.id

  const composition = useResolvedComposition({
    focusType: compositionFocusType,
    vertical: company?.vertical ?? null,
    tenantId: company?.id ?? null,
    enabled: true,
  })

  // Show accessory rail only when a composition resolved AND has
  // placements. Loading state intentionally renders kanban-only so
  // the rail doesn't appear-then-disappear if no composition resolves.
  const showAccessories =
    composition.hasComposition &&
    !!composition.composition &&
    composition.composition.placements.length > 0

  if (!showAccessories) {
    return (
      <div
        className="h-full w-full"
        data-slot="scheduling-focus-with-accessories"
        data-accessory-rail="absent"
      >
        <SchedulingKanbanCore focusId={focusId} config={config} />
      </div>
    )
  }

  return (
    <div
      className="flex h-full w-full gap-4"
      data-slot="scheduling-focus-with-accessories"
      data-accessory-rail="present"
    >
      <div className="flex-1 min-w-0">
        <SchedulingKanbanCore focusId={focusId} config={config} />
      </div>
      <aside
        className="w-72 flex-shrink-0 overflow-y-auto"
        data-slot="scheduling-focus-accessory-rail"
        aria-label="Scheduling Focus accessories"
      >
        <CompositionRenderer
          composition={composition.composition!}
          editorMode={false}
        />
      </aside>
    </div>
  )
}
