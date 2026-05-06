/**
 * FocusContextBridge — runtime infrastructure for threading
 * operational props through the composition layer.
 *
 * The split:
 *   - Composition specifies WHAT'S ON THE CANVAS + WHERE
 *     (placements + grid coords + per-placement prop_overrides)
 *   - Focus context provides OPERATIONAL DATA + CALLBACKS
 *     (case data, drag handlers, save callbacks, current date,
 *     anomaly list, etc.)
 *   - The bridge is how operational data flows into placements
 *     when a Focus renders via CompositionRenderer
 *
 * Pattern:
 *   1. The Focus React component populates the bridge with the
 *      operational data its components need, keyed by component
 *      identifier (e.g., "vault-schedule" → { cases, drag handlers })
 *   2. CompositionRenderer renders placements via a custom
 *      `renderPlacement` callback that pulls operational props from
 *      the bridge by component_kind+component_name
 *   3. The component receives both: configured props (from the
 *      composition's placement.prop_overrides + normal config
 *      inheritance) AND operational props (from the bridge)
 *
 * Decoupling rationale: the kanban implementation doesn't know it's
 * being rendered via composition. It receives the same prop shape
 * it always has. The composition layer is invisible to the
 * underlying components — they just see normal React props.
 */
import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react"


/**
 * Operational props are component-keyed. The key is
 * `${component_kind}:${component_name}`. Value is whatever
 * operational data + callbacks that component needs.
 */
export type OperationalPropMap = Record<string, Record<string, unknown>>


interface FocusBridgeValue {
  /** Map of component-key → operational props. */
  operational: OperationalPropMap
}


const FocusBridgeContext = createContext<FocusBridgeValue | null>(null)


export interface FocusContextBridgeProps {
  /** Component-keyed operational props (case data, callbacks, etc.). */
  operational: OperationalPropMap
  children: ReactNode
}


/**
 * Wrap CompositionRenderer in this provider when rendering a Focus
 * via composition. The provider exposes operational props that
 * placements consume by component identifier.
 */
export function FocusContextBridge({
  operational,
  children,
}: FocusContextBridgeProps) {
  const value = useMemo<FocusBridgeValue>(
    () => ({ operational }),
    [operational],
  )
  return (
    <FocusBridgeContext.Provider value={value}>
      {children}
    </FocusBridgeContext.Provider>
  )
}


/**
 * Look up operational props for a placement. Returns an empty
 * object when no bridge is mounted (i.e., the renderer is being
 * used in editor preview mode, not Focus runtime mode) — components
 * gracefully degrade to their normal prop set.
 */
export function useOperationalProps(
  componentKind: string,
  componentName: string,
): Record<string, unknown> {
  const ctx = useContext(FocusBridgeContext)
  if (!ctx) return {}
  const key = `${componentKind}:${componentName}`
  return ctx.operational[key] ?? {}
}


/**
 * Convenience: Focus implementations call this to build the
 * operational map without typos in the key format.
 */
export function buildOperationalProps(
  entries: Array<{
    componentKind: string
    componentName: string
    props: Record<string, unknown>
  }>,
): OperationalPropMap {
  const out: OperationalPropMap = {}
  for (const e of entries) {
    out[`${e.componentKind}:${e.componentName}`] = e.props
  }
  return out
}
