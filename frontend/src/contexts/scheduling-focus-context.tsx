/**
 * SchedulingFocusContext — Phase B Session 4.3b.3.
 *
 * Lightweight read-only state surface for consumers spanning the
 * funeral-scheduling Focus subtree (kanban core + ancillary pool pin
 * + future scheduling-related Canvas widgets like drive-time matrix
 * or staff availability).
 *
 * Why a context instead of prop-drilling
 * ──────────────────────────────────────
 * AncillaryPoolPin is rendered by the canvas framework (Canvas →
 * getWidgetRenderer → AncillaryPoolPin). The framework doesn't know
 * about scheduling-domain data; it can't pass pool ancillaries down
 * as a prop. The pin reads from this context instead, decoupled
 * from the framework's per-widget plumbing. Future scheduling
 * widgets read from the same context.
 *
 * Provider mount point
 * ────────────────────
 * The provider is INTENTIONALLY VALUE-ONLY — `<SchedulingFocus
 * Context.Provider value={...}>`. It does NOT own the data fetch
 * (Phase 4.3b.3 considered a self-fetching provider but rejected
 * it: the kanban core already fetches deliveries + drivers + the
 * day's schedule, and routing the pool fetch through the same
 * effect keeps refresh logic in one place; making the pin's
 * provider self-fetch would create a second source of truth +
 * race conditions during cross-context drag refreshes).
 *
 * The kanban core (`SchedulingKanbanCore.tsx`) owns the data + the
 * provider. Both kanban tree AND canvas tree (where the pin lives)
 * need to read from the same provider — but they're SIBLINGS in
 * the Focus tree, not ancestor/descendant. Phase 4.3b.3 solves
 * this by having the kanban core render the provider via React's
 * `createPortal` to a stable mount node so both subtrees become
 * descendants.
 *
 * Wait — that doesn't work cleanly either. React context
 * propagation does NOT cross portal boundaries by default in the
 * standard mental model, but @dnd-kit uses portals + still gets
 * context propagation. Let me re-check: React context DOES
 * propagate through portals (the React docs explicitly call this
 * out — "context propagates from the React tree perspective, not
 * the DOM tree").
 *
 * SO the actual solution: SchedulingKanbanCore wraps its render
 * AND (via portal) the canvas widget mount point with the
 * provider. But Canvas isn't mounted by the kanban core; it's
 * mounted by Focus.tsx as a sibling. Even with a portal,
 * SchedulingKanbanCore can't reach Canvas's subtree.
 *
 * Pragmatic solution: lift the provider to Focus.tsx level. Focus
 * mounts a thin `<SchedulingFocusDataProvider>` (defined here)
 * that owns the pool fetch + reload, and exposes everything via
 * this context. SchedulingKanbanCore consumes the same context
 * for pool ancillaries when it needs them in cross-context drag
 * routing. The kanban core continues to own its own
 * deliveries/drivers/schedule state (different lifecycle —
 * targetDate-scoped, not the focus type). Two halves; clean
 * separation.
 *
 * Provider scope: ONLY mounted when active Focus is funeral-
 * scheduling. Other Focus types skip the provider; consumers
 * outside the funeral-scheduling subtree get null from
 * useSchedulingFocusOptional.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react"
import type { ReactNode } from "react"

import type { DeliveryDTO } from "@/services/dispatch-service"
import { fetchPoolAncillaries } from "@/services/dispatch-service"


export interface SchedulingFocusContextValue {
  /** Pool ancillaries — `attached_to_delivery_id IS NULL` AND
   *  `primary_assignee_id IS NULL` AND `ancillary_is_floating IS TRUE`.
   *  Date-less (pool items have no `requested_date`). The
   *  AncillaryPoolPin renders these as draggable rows with
   *  `id="ancillary:<id>"` so the elevated DndContext can route them
   *  to lane drops (assign-standalone), parent-card drops (attach),
   *  or unassigned-lane drops (return-to-pool / no-op). */
  poolAncillaries: DeliveryDTO[]
  /** True while the pool fetch is in flight. The pin renders a
   *  subdued state during refresh; widgets that don't depend on
   *  pool data can ignore this. */
  poolLoading: boolean
  /** Refresh just the pool list. Called after cross-context drag
   *  completes — pool item dropped on a lane fires
   *  assign-standalone → pool decrements server-side → reload
   *  pulls authoritative state.
   *
   *  Note: this does NOT reload the kanban core's deliveries.
   *  Kanban-core has its own `reload()` mechanism (refreshTick)
   *  for that. Cross-context drag handlers call BOTH after a
   *  successful drop. */
  reloadPool: () => void
  /** Optimistic-update helper. Called by drag handlers when a pool
   *  item is moved out of the pool (assigned standalone OR
   *  attached). Removes the item from `poolAncillaries`
   *  immediately so the pin updates without waiting for the
   *  server roundtrip. The next reload pulls authoritative state.
   *
   *  Inverse — adding to pool when something is returned-to-pool —
   *  is NOT exposed; the kanban core handles that via reloadPool
   *  after the API call. Keeping just the remove-side optimistic
   *  matches the more common drag direction (out-of-pool). */
  removeFromPoolOptimistic: (deliveryId: string) => void
}


export const SchedulingFocusContext =
  createContext<SchedulingFocusContextValue | null>(null)


export interface SchedulingFocusDataProviderProps {
  children: ReactNode
}


/** Provider that fetches pool ancillaries on mount + exposes the
 *  reload/optimistic helpers. Mount once at Focus.tsx level when
 *  the active focus is `funeral-scheduling`. */
export function SchedulingFocusDataProvider({
  children,
}: SchedulingFocusDataProviderProps) {
  const [poolAncillaries, setPoolAncillaries] = useState<DeliveryDTO[]>([])
  const [poolLoading, setPoolLoading] = useState<boolean>(true)
  const [refreshTick, setRefreshTick] = useState<number>(0)

  useEffect(() => {
    let cancelled = false
    setPoolLoading(true)
    fetchPoolAncillaries()
      .then((rows) => {
        if (cancelled) return
        setPoolAncillaries(rows)
      })
      .catch((e) => {
        if (cancelled) return
        console.error("pool ancillaries fetch failed:", e)
        // Keep prior list on error — better than wiping it.
      })
      .finally(() => {
        if (!cancelled) setPoolLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [refreshTick])

  const reloadPool = useCallback(() => {
    setRefreshTick((n) => n + 1)
  }, [])

  const removeFromPoolOptimistic = useCallback((deliveryId: string) => {
    setPoolAncillaries((prev) => prev.filter((d) => d.id !== deliveryId))
  }, [])

  return (
    <SchedulingFocusContext.Provider
      value={{
        poolAncillaries,
        poolLoading,
        reloadPool,
        removeFromPoolOptimistic,
      }}
    >
      {children}
    </SchedulingFocusContext.Provider>
  )
}


/** Hook for consumers inside a SchedulingFocusContext.Provider.
 *  Throws when called outside the provider — that's the contract:
 *  AncillaryPoolPin + future scheduling widgets MUST be mounted
 *  inside the funeral-scheduling Focus's provider subtree. */
export function useSchedulingFocus(): SchedulingFocusContextValue {
  const ctx = useContext(SchedulingFocusContext)
  if (ctx === null) {
    throw new Error(
      "useSchedulingFocus must be used inside <SchedulingFocusDataProvider>",
    )
  }
  return ctx
}


/** Null-safe variant for components that may render in non-Focus
 *  contexts (e.g. SchedulingKanbanCore reads pool data when
 *  routing cross-context drag, but tests + non-funeral-scheduling
 *  Focus mounts won't have the provider). Returns null when no
 *  provider is mounted; callers gracefully degrade.
 *
 *  SchedulingKanbanCore uses this so its existing tests (which
 *  don't wrap with the data provider) continue to render — drag
 *  handlers that need pool data check for null and skip pool-
 *  routing branches when the context is absent. */
export function useSchedulingFocusOptional():
  | SchedulingFocusContextValue
  | null {
  return useContext(SchedulingFocusContext)
}
