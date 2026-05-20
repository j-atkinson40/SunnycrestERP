/**
 * FocusBuilderSelectionContext — selection state for the canvas.
 *
 * Sub-arc F-1 ships the provider + hook + shape. F-1's canvas keeps
 * selection at `{ kind: 'none' }` throughout — editing wires arrive
 * in F-2 (background-click → 'background', core-click → 'core',
 * widget-click → 'widget' with id).
 *
 * Sub-arc FF-7 extends with `widgets-multi` for canvas-level multi-
 * select per Q-16 (a) + Q-17 (b) + Q-18 (a). Multi-select drives:
 *   - Move-together drag (all selected widgets move by the same delta)
 *   - Align affordances in the inspector (left/center/right/top/middle/
 *     bottom) — no multi-edit
 *   - Marquee drag on empty canvas captures widgets whose bounding
 *     boxes intersect the rectangle
 *
 * The single-select model from F-2 is preserved unchanged. Multi-
 * select is additive — callers that only know about `widget` /
 * `core` / `background` / `none` continue working.
 */
import * as React from "react"


export type Selection =
  | { kind: "none" }
  | { kind: "background" }
  | { kind: "core" }
  | { kind: "widget"; id: string }
  | { kind: "widgets-multi"; ids: string[] }


export interface FocusBuilderSelectionContextValue {
  selection: Selection
  setSelection: (s: Selection) => void
  /**
   * FF-7 — multi-select helpers. Each transitions the selection state
   * idempotently across single / multi / none cases. The helpers
   * never throw; defensive against background / core selections by
   * collapsing to widget-or-multi state when a widget id is added.
   */
  addToSelection: (id: string) => void
  removeFromSelection: (id: string) => void
  clearSelection: () => void
  setMultiSelection: (ids: string[]) => void
  isInSelection: (id: string) => boolean
}


const FocusBuilderSelectionContext =
  React.createContext<FocusBuilderSelectionContextValue | null>(null)


export function FocusBuilderSelectionProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [selection, setSelection] = React.useState<Selection>({ kind: "none" })

  const addToSelection = React.useCallback((id: string) => {
    setSelection((prev) => {
      // none / background / core → start a single selection on this id.
      if (prev.kind === "none" || prev.kind === "background" || prev.kind === "core") {
        return { kind: "widget", id }
      }
      // widget → promote to multi (or stay single if same id).
      if (prev.kind === "widget") {
        if (prev.id === id) return prev
        return { kind: "widgets-multi", ids: [prev.id, id] }
      }
      // widgets-multi → add if not present.
      if (prev.ids.includes(id)) return prev
      return { kind: "widgets-multi", ids: [...prev.ids, id] }
    })
  }, [])

  const removeFromSelection = React.useCallback((id: string) => {
    setSelection((prev) => {
      if (prev.kind === "widget" && prev.id === id) {
        return { kind: "none" }
      }
      if (prev.kind === "widgets-multi") {
        const remaining = prev.ids.filter((i) => i !== id)
        if (remaining.length === 0) return { kind: "none" }
        if (remaining.length === 1) return { kind: "widget", id: remaining[0] }
        return { kind: "widgets-multi", ids: remaining }
      }
      return prev
    })
  }, [])

  const clearSelection = React.useCallback(() => {
    setSelection({ kind: "none" })
  }, [])

  const setMultiSelection = React.useCallback((ids: string[]) => {
    if (ids.length === 0) {
      setSelection({ kind: "none" })
      return
    }
    if (ids.length === 1) {
      setSelection({ kind: "widget", id: ids[0] })
      return
    }
    setSelection({ kind: "widgets-multi", ids })
  }, [])

  const isInSelection = React.useCallback(
    (id: string): boolean => {
      if (selection.kind === "widget") return selection.id === id
      if (selection.kind === "widgets-multi") return selection.ids.includes(id)
      return false
    },
    [selection],
  )

  const value = React.useMemo(
    () => ({
      selection,
      setSelection,
      addToSelection,
      removeFromSelection,
      clearSelection,
      setMultiSelection,
      isInSelection,
    }),
    [
      selection,
      addToSelection,
      removeFromSelection,
      clearSelection,
      setMultiSelection,
      isInSelection,
    ],
  )
  return (
    <FocusBuilderSelectionContext.Provider value={value}>
      {children}
    </FocusBuilderSelectionContext.Provider>
  )
}


export function useFocusBuilderSelection(): FocusBuilderSelectionContextValue {
  const ctx = React.useContext(FocusBuilderSelectionContext)
  if (!ctx) {
    throw new Error(
      "useFocusBuilderSelection must be called inside <FocusBuilderSelectionProvider>",
    )
  }
  return ctx
}
