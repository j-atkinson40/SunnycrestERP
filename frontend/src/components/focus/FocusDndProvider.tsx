/**
 * FocusDndProvider — Phase B Session 4.3b D-1 elevation.
 *
 * Owns the single `DndContext` that spans every Focus subtree —
 * `focus-core-positioner` (Popup → ModeDispatcher → core mode like
 * SchedulingKanbanCore) AND `<Canvas />` (free-form widgets, including
 * future pin widgets like the AncillaryPoolPin).
 *
 * Why elevate
 * ───────────
 * Pre-4.3b each region owned its own `DndContext` (Canvas had one
 * mounted at the canvas wrapper; SchedulingKanbanCore had its own
 * inside ModeDispatcher). Two parallel contexts meant a draggable in
 * the canvas tree could not target droppables in the kanban tree —
 * cross-context drag was structurally impossible. Phase 4.3b ships the
 * Ancillary Pool Pin (a Canvas widget whose draggable items must drop
 * onto kanban lanes), so the contexts must merge.
 *
 * Why a Provider component instead of inlining DndContext into Focus
 * ──────────────────────────────────────────────────────────────────
 * Three reasons:
 *  1. **Test harness reuse.** `Canvas.test.tsx` and
 *     `SchedulingKanbanCore.test.tsx` mount their components without
 *     `Focus.tsx` (it's an integration shell). Both consumers now call
 *     `useDndMonitor`, which throws unless wrapped in a `DndContext`.
 *     Wrapping each test harness with `<FocusDndProvider>` is one line.
 *  2. **Future Focus modes that don't need drag.** `single-record`,
 *     `edit-canvas`, `triage-queue` modes don't have draggables but
 *     still mount inside the same Focus shell. A no-op DndContext is
 *     harmless; centralizing it here keeps Focus.tsx mode-agnostic.
 *  3. **Optional `activeId` context for non-monitor consumers.** Some
 *     UI code wants to know "is something dragging right now?" without
 *     subscribing via `useDndMonitor`. The Provider exposes
 *     `useFocusDndActiveId()` so simple read-only consumers don't need
 *     monitor plumbing.
 *
 * Consumer pattern (id-prefix discriminator)
 * ──────────────────────────────────────────
 * Each subtree's consumer registers a `useDndMonitor` listener that
 * gates on the id prefix:
 *
 *   widget:<widget_id>      — Canvas widget repositioning
 *   delivery:<delivery_id>  — primary kanban DeliveryCard +
 *                             standalone AncillaryCard reassignment
 *   ancillary:<ancillary_id> — Phase 4.3b pool pin items + drawer
 *                              detach drags (state-machine routing)
 *
 * Listeners early-return on non-matching prefixes. Multiple listeners
 * coexist; @dnd-kit fires them all on each event.
 *
 * What this provider does NOT do
 * ──────────────────────────────
 * - **Does not render `DragOverlay`.** Each consumer renders its own,
 *   portaled to `document.body` to escape the Focus positioner's
 *   `transform: translate3d` containing block (Phase 4.2.3). The
 *   kanban core renders the DeliveryCard / AncillaryCard preview;
 *   Canvas widgets transform in place (no overlay needed).
 * - **Does not own routing logic.** The provider's onDrag* handlers
 *   only manage `activeId` for read-only consumers. Per-consumer
 *   state machines + API calls live with the consumer.
 *
 * Sensor configuration
 * ────────────────────
 * Single PointerSensor with `activationConstraint: { distance: 8 }` —
 * identical to both pre-4.3b configs (Canvas + kanban already used
 * this exact value, so no consolidation pain). 8px distinguishes
 * click from drag and is the convention across the canvas + card
 * affordances. Future sensor needs (KeyboardSensor for accessibility)
 * land here.
 */

import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  type DragCancelEvent,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core"
import { createContext, useCallback, useContext, useState } from "react"
import type { ReactNode } from "react"


interface FocusDndContextValue {
  /** The id of the currently-dragging item, including its prefix
   *  (e.g. "delivery:abc-123" or "widget:mock-saved-view-1"). Null
   *  when no drag is active. Read by UI code that wants to gate
   *  visual state on drag presence without subscribing to monitor
   *  events. */
  activeId: string | null
}


const FocusDndStateContext = createContext<FocusDndContextValue>({
  activeId: null,
})


/** Hook for read-only consumers — return the current `activeId` (with
 *  its prefix) or null. Equivalent to subscribing via `useDndMonitor`
 *  but without the per-event listener cost when all the consumer
 *  needs is "is something dragging right now?" / "what is dragging?".
 *
 *  When called outside a `<FocusDndProvider>` returns `null` (the
 *  default value), so call-sites are render-safe in non-Focus
 *  surfaces. */
export function useFocusDndActiveId(): string | null {
  return useContext(FocusDndStateContext).activeId
}


export interface FocusDndProviderProps {
  children: ReactNode
}


export function FocusDndProvider({ children }: FocusDndProviderProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  const [activeId, setActiveId] = useState<string | null>(null)

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(String(event.active.id))
  }, [])

  const handleDragEnd = useCallback((_event: DragEndEvent) => {
    setActiveId(null)
  }, [])

  const handleDragCancel = useCallback((_event: DragCancelEvent) => {
    setActiveId(null)
  }, [])

  return (
    <FocusDndStateContext.Provider value={{ activeId }}>
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        {children}
      </DndContext>
    </FocusDndStateContext.Provider>
  )
}
