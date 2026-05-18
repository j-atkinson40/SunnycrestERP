/**
 * FocusBuilderSelectionContext — selection state for the canvas.
 *
 * Sub-arc F-1 ships the provider + hook + shape. F-1's canvas keeps
 * selection at `{ kind: 'none' }` throughout — editing wires arrive
 * in F-2 (background-click → 'background', core-click → 'core',
 * widget-click → 'widget' with id).
 *
 * Single-select per investigation Q-15 (deferred multi-select).
 */
import * as React from "react"


export type Selection =
  | { kind: "none" }
  | { kind: "background" }
  | { kind: "core" }
  | { kind: "widget"; id: string }


export interface FocusBuilderSelectionContextValue {
  selection: Selection
  setSelection: (s: Selection) => void
}


const FocusBuilderSelectionContext =
  React.createContext<FocusBuilderSelectionContextValue | null>(null)


export function FocusBuilderSelectionProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [selection, setSelection] = React.useState<Selection>({ kind: "none" })
  const value = React.useMemo(() => ({ selection, setSelection }), [selection])
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
