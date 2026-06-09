/**
 * StudioAssistantSlotContext — the additive docked assistant-rail slot
 * (Builder AI Assistant Phase 1b).
 *
 * StudioShell hosts a single slot: a `ReactNode` rendered as a flex sibling
 * after `<main>`. An editor that wants a docked assistant rail pushes its rail
 * element via `setRail(...)` (and clears it on unmount). For 1b, ONLY the
 * Workflow editor fills the slot; every other editor leaves it null.
 *
 * Why this is byte-identical for the other 6 builders:
 *   - The Provider renders NO DOM of its own.
 *   - StudioShell renders `{rail}`; when null, React renders nothing → the
 *     shell DOM is identical to pre-1b.
 *
 * Why live editor state survives prop updates (no remount of the rail):
 *   - The rail is always the SAME component type rendered at the SAME JSX
 *     position (`{rail}`). When the editor re-pushes a fresh element with new
 *     props, React reconciles at that position (prop update), it does NOT
 *     unmount/remount — so the rail's internal state (input text, generating,
 *     error) persists across editor re-renders.
 *
 * EXTRACTION SEAM (do NOT generalize here per 1b scope): the slot is a thin
 * ReactNode portal, not an assistant abstraction. The {grounding, emit,
 * validate, applyProposal} contract lives in the editor + rail. Consumer #2
 * hoists/parameterizes if/when a second builder needs a rail.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

interface StudioAssistantSlotValue {
  /** The rail element to render in the shell slot (null = no rail). */
  rail: ReactNode
  /** Push (or clear, with null) the rail element. */
  setRail: (rail: ReactNode) => void
}

const StudioAssistantSlotContext = createContext<StudioAssistantSlotValue>({
  rail: null,
  setRail: () => {},
})

export function StudioAssistantSlotProvider({
  children,
}: {
  children: ReactNode
}) {
  const [rail, setRailState] = useState<ReactNode>(null)
  const setRail = useCallback((next: ReactNode) => setRailState(next), [])
  const value = useMemo(() => ({ rail, setRail }), [rail, setRail])
  return (
    <StudioAssistantSlotContext.Provider value={value}>
      {children}
    </StudioAssistantSlotContext.Provider>
  )
}

/** Read the slot (the editor uses `.setRail`; the shell reads `.rail`). */
export function useStudioAssistantSlot(): StudioAssistantSlotValue {
  return useContext(StudioAssistantSlotContext)
}
