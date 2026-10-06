/**
 * The three surfaces cannot be open in conflicting combinations.
 *
 * ⚠️ THIS IS PART 2.1's PROOF, AND THE STOP CONDITION IT CLEARS. The dispatch said: if
 * satisfying the gate requires changing Focus's or the command bar's existing behaviour,
 * stop and report. It does not. `CommandBarProvider` is not modified — Opas watches
 * `commandBar.isOpen` and calls the bar's own exported `close()`, so every existing rule
 * (Cmd+K toggles, Escape closes, Focus wins, `{!focusIsOpen && <CommandBar/>}`) is intact.
 *
 * The matrix below is over the THREE pairs that can conflict. The fourth combination —
 * nothing open — needs no assertion.
 */
import { act, render } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { OpasProvider, useOpas } from "./opas-context"

// ─── doubles ────────────────────────────────────────────────────────────────
// ⚠️ The command-bar double exposes the SAME surface the real provider does —
// { isOpen, open, close } — so a rename there breaks this test rather than silently
// passing. `close` is a spy, because "Opas closes the bar via the bar's own close()" is
// the claim that keeps the change additive, and asserting it is how that claim is held.

const barClose = vi.fn()
let barIsOpen = false
let focusIsOpen = false

vi.mock("@/core/CommandBarProvider", () => ({
  useCommandBar: () => ({ isOpen: barIsOpen, open: vi.fn(), close: barClose }),
}))
vi.mock("@/contexts/focus-context", () => ({
  useFocus: () => ({ isOpen: focusIsOpen }),
}))

let api: ReturnType<typeof useOpas>

function Probe() {
  api = useOpas()
  return null
}

function mount() {
  return render(
    <OpasProvider>
      <Probe />
    </OpasProvider>,
  )
}

beforeEach(() => {
  barClose.mockReset()
  barIsOpen = false
  focusIsOpen = false
})

describe("Opas gate — combination matrix", () => {
  it("sphere alone opens", () => {
    mount()
    act(() => api.open())
    expect(api.isOpen).toBe(true)
    expect(api.canRender).toBe(true)
  })

  it("a Focus open REFUSES the sphere", () => {
    focusIsOpen = true
    mount()
    act(() => api.open())
    expect(api.isOpen).toBe(false)
    expect(api.canRender).toBe(false)
  })

  it("a Focus opening OVER an open sphere closes it", () => {
    mount()
    act(() => api.open())
    expect(api.isOpen).toBe(true)
    focusIsOpen = true
    mount()
    expect(api.isOpen).toBe(false)
  })

  it("opening the sphere closes the command bar — via the bar's OWN close()", () => {
    barIsOpen = true
    mount()
    act(() => api.open())
    expect(barClose).toHaveBeenCalledTimes(1)
  })

  it("the command bar opening closes the sphere", () => {
    mount()
    act(() => api.open())
    expect(api.isOpen).toBe(true)
    barIsOpen = true
    mount()
    expect(api.isOpen).toBe(false)
  })

  it("⚠️ CONTROL — the sphere does NOT call the bar's close when the bar is shut", () => {
    // Without this, an implementation that called close() unconditionally would satisfy
    // the assertion above while fighting the bar on every open.
    mount()
    act(() => api.open())
    expect(barClose).not.toHaveBeenCalled()
  })

  it("Esc TUCKS: the session closes but panes survive", () => {
    mount()
    act(() => api.open())
    act(() => api.openPane({ kind: "product-list", label: "Catalog" }))
    expect(api.panes).toHaveLength(1)
    act(() => api.close())
    expect(api.isOpen).toBe(false)
    expect(api.panes, "a tuck must not clear the session").toHaveLength(1)
  })

  it("a pane can be closed individually", () => {
    mount()
    act(() => api.open())
    act(() => api.openPane({ kind: "product-list", label: "Catalog" }))
    const id = api.panes[0].id
    act(() => api.closePane(id))
    expect(api.panes).toHaveLength(0)
  })

  it("useOpas outside the provider throws rather than degrading to an ungated sphere", () => {
    const quiet = vi.spyOn(console, "error").mockImplementation(() => {})
    expect(() => render(<Probe />)).toThrow(/useOpas must be used inside/)
    quiet.mockRestore()
  })

  describe("Escape, in the prototype's three branches", () => {
    it("1 — a pending pick is CANCELLED and the session is NOT tucked", () => {
      mount()
      act(() => api.open())
      act(() => api.openPane({ kind: "product-list", label: "Catalog" }))
      act(() => api.setPendingPick(["v1", "v2"]))
      let outcome: string | undefined
      act(() => {
        outcome = api.onEscape()
      })
      expect(outcome).toBe("cancelled-pick")
      expect(api.pendingPick).toBeNull()
      expect(api.isOpen, "cancelling a pick must not tuck the session").toBe(true)
      expect(api.panes).toHaveLength(1)
    })

    it("2 — Escape inside a TEXTAREA refocuses and does NOT tuck", () => {
      mount()
      act(() => api.open())
      let outcome: string | undefined
      act(() => {
        outcome = api.onEscape("TEXTAREA")
      })
      expect(outcome).toBe("refocused-input")
      expect(api.isOpen, "Escape while typing must not tuck the pane away").toBe(true)
    })

    it("3 — otherwise it tucks, and the panes survive", () => {
      mount()
      act(() => api.open())
      act(() => api.openPane({ kind: "product", label: "Product", variantTemplateId: "v1" }))
      let outcome: string | undefined
      act(() => {
        outcome = api.onEscape("DIV")
      })
      expect(outcome).toBe("tucked")
      expect(api.isOpen).toBe(false)
      expect(api.panes).toHaveLength(1)
    })

    it("⚠️ ORDER MATTERS: a pending pick wins over the textarea branch", () => {
      // The prototype checks `pending` FIRST. Reversing the two would lose a pick
      // whenever the caret happened to be in a textarea.
      mount()
      act(() => api.open())
      act(() => api.setPendingPick(["v1"]))
      let outcome: string | undefined
      act(() => {
        outcome = api.onEscape("TEXTAREA")
      })
      expect(outcome).toBe("cancelled-pick")
    })
  })

  describe("the session is the set of panes", () => {
    it("no panes means no session", () => {
      mount()
      act(() => api.open())
      expect(api.hasSession).toBe(false)
    })

    it("a pane means a session, and it survives the tuck", () => {
      mount()
      act(() => api.open())
      act(() => api.openPane({ kind: "product-list", label: "Catalog" }))
      expect(api.hasSession).toBe(true)
      act(() => api.tuck())
      expect(api.hasSession, "the sphere must still show a held session").toBe(true)
    })

    it("closing the last pane ends the session — the only control there is", () => {
      // ⚠️ VERIFIED ABSENCE: the prototype has NO clear-all. The session indicator is
      // `orb.classList.toggle('session', wins.length > 0)`, so a session ends only when
      // the last pane is closed.
      mount()
      act(() => api.open())
      act(() => api.openPane({ kind: "product-list", label: "Catalog" }))
      act(() => api.closePane(api.panes[0].id))
      expect(api.hasSession).toBe(false)
    })
  })
})
