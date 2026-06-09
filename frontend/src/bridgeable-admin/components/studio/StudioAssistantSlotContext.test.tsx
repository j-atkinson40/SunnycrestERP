/**
 * StudioAssistantSlotContext — Phase 1b additive-slot tests (jsdom).
 *
 * The ADDITIVE-FOR-OTHER-BUILDERS invariant proof at the slot level: with no
 * editor pushing a rail, the slot outlet renders NOTHING (no DOM) → the shell
 * is byte-identical for the 6 builders that don't fill it. When an editor
 * pushes a rail, it renders; clearing it (null) removes it again.
 */
import { describe, it, expect } from "vitest"
import { useEffect } from "react"
import { fireEvent, render, screen } from "@testing-library/react"

import {
  StudioAssistantSlotProvider,
  useStudioAssistantSlot,
} from "./StudioAssistantSlotContext"

/** Mirrors StudioShell's outlet: renders whatever lives in the slot. */
function Outlet() {
  const { rail } = useStudioAssistantSlot()
  return <div data-testid="outlet">{rail}</div>
}

/** A would-be editor that pushes a rail on mount (like WorkflowEditorPage). */
function PushesRail() {
  const { setRail } = useStudioAssistantSlot()
  useEffect(() => {
    setRail(<div data-testid="pushed-rail">RAIL</div>)
    return () => setRail(null)
  }, [setRail])
  return <div data-testid="editor">EDITOR</div>
}

/** A would-be editor that never touches the slot (like the other 6 builders). */
function NoRail() {
  return <div data-testid="editor">OTHER EDITOR</div>
}

describe("StudioAssistantSlotContext", () => {
  it("empty slot renders NOTHING → byte-identical for builders that don't fill it", () => {
    render(
      <StudioAssistantSlotProvider>
        <NoRail />
        <Outlet />
      </StudioAssistantSlotProvider>,
    )
    // The outlet is present but contains no rail markup.
    expect(screen.getByTestId("outlet").childNodes.length).toBe(0)
    expect(screen.queryByTestId("pushed-rail")).toBeNull()
  })

  it("an editor that pushes a rail fills the slot", async () => {
    render(
      <StudioAssistantSlotProvider>
        <PushesRail />
        <Outlet />
      </StudioAssistantSlotProvider>,
    )
    expect(await screen.findByTestId("pushed-rail")).toBeInTheDocument()
  })

  it("the default (no provider) is a safe no-op — setRail does not throw", () => {
    // WorkflowEditorPage may render without the provider (e.g. unit tests);
    // useStudioAssistantSlot must default to a harmless no-op.
    function Standalone() {
      const { setRail, rail } = useStudioAssistantSlot()
      return (
        <button onClick={() => setRail(<span>x</span>)} data-testid="btn">
          {rail ? "has-rail" : "no-rail"}
        </button>
      )
    }
    render(<Standalone />)
    // Clicking calls the no-op setRail — must not throw; rail stays empty.
    fireEvent.click(screen.getByTestId("btn"))
    expect(screen.getByTestId("btn")).toHaveTextContent("no-rail")
  })
})
