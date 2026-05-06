/**
 * ComposedFocus — runtime wrapper for Focus components that opt into
 * composition rendering.
 *
 * Usage pattern (canonical wiring for production Focus components):
 *
 *   function SchedulingFocus() {
 *     const { vertical } = useTenant()
 *     const { user } = useAuth()
 *     const operational = buildOperationalProps([
 *       { componentKind: "widget", componentName: "vault-schedule", props: {
 *           cases: kanbanCases,
 *           onDragEnd: handleDragEnd,
 *           ...
 *       }},
 *       { componentKind: "widget", componentName: "today", props: { ... }},
 *       // ...
 *     ])
 *     return (
 *       <ComposedFocus
 *         focusType="scheduling"
 *         vertical={vertical}
 *         tenantId={user.company_id}
 *         operational={operational}
 *         fallback={<HardCodedSchedulingLayout />}
 *       />
 *     )
 *   }
 *
 * Behavior:
 *   - On mount, resolves the composition for (focusType, vertical, tenantId)
 *   - If a composition exists at any scope: renders via CompositionRenderer
 *     wrapped in FocusContextBridge so placements can consume operational
 *     props
 *   - If no composition exists: renders `fallback` (the Focus's existing
 *     hard-coded layout)
 *   - During the loading window: renders `loadingFallback` (defaults to
 *     `fallback` so the user never sees a flash of empty state — same
 *     content shows whether composition resolves or fallback fires)
 *
 * The wrapper is intentionally narrow: it only handles the
 * resolve-and-dispatch decision. Production Focus components keep
 * their existing data fetching, drag handlers, callbacks — they
 * just expose those as operational props instead of passing them
 * directly to children.
 *
 * Production refactor of the existing scheduling / arrangement-scribe /
 * triage-decision Focus components is a separate focused phase per
 * §14 entry — touches 1700+ lines of production code that needs
 * careful operational-props mapping. This wrapper is the
 * architecture; the production wiring is incremental.
 */
import type { ReactNode } from "react"
import { CompositionRenderer } from "./CompositionRenderer"
import {
  FocusContextBridge,
  type OperationalPropMap,
  useOperationalProps,
} from "./FocusContextBridge"
import { useResolvedComposition } from "./useResolvedComposition"


export interface ComposedFocusProps {
  focusType: string
  vertical?: string | null
  tenantId?: string | null
  operational: OperationalPropMap
  fallback: ReactNode
  /** Optional custom loading state. Defaults to `fallback` so there's
   * no flash of empty content while composition resolution is in
   * flight. */
  loadingFallback?: ReactNode
  /** When true, skip composition resolution and render `fallback`
   * directly. Useful for tenants opting out of composition-rendered
   * Focuses, or for emergency rollback if composition rendering
   * causes a regression. */
  forceFallback?: boolean
}


export function ComposedFocus({
  focusType,
  vertical,
  tenantId,
  operational,
  fallback,
  loadingFallback,
  forceFallback = false,
}: ComposedFocusProps) {
  const result = useResolvedComposition({
    focusType,
    vertical,
    tenantId,
    enabled: !forceFallback,
  })

  if (forceFallback) return <>{fallback}</>
  if (result.isLoading) return <>{loadingFallback ?? fallback}</>
  if (!result.hasComposition || !result.composition) return <>{fallback}</>

  return (
    <FocusContextBridge operational={operational}>
      <CompositionRenderer
        composition={result.composition}
        editorMode={false}
      />
    </FocusContextBridge>
  )
}


/** Convenience helper for placement components that want to
 * declare their dependence on operational props. Returns the merged
 * { ...placement.prop_overrides, ...operationalProps } so the
 * component sees a single prop bag. */
export function useMergedPlacementProps(
  componentKind: string,
  componentName: string,
  configuredProps: Record<string, unknown>,
): Record<string, unknown> {
  const operational = useOperationalProps(componentKind, componentName)
  // Operational wins on key conflict — operational data is the
  // dynamic state; configured is the static design.
  return { ...configuredProps, ...operational }
}
