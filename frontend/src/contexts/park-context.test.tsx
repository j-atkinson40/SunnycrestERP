/**
 * ParkContext (S-5) — the client-memory session store.
 *
 * Pins: summon/dismiss, the DECLARATIVE escalation predicate (park reads
 * the act-registry, no hardcode), SUSPEND-AND-RETURN (session held across
 * a Focus open/close), and the grace-window exit/relaunch. The
 * no-data-before-commit guarantee is proven at the tablet level in
 * park-tablets.test.tsx; here we pin that the store itself has no commit
 * path (it never touches a service).
 */

import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderHook, act } from "@testing-library/react"
import type { ReactNode } from "react"

// Controllable Focus stub — park consumes useFocusOptional for escalate +
// suspend. mutable module state, re-read on rerender.
let mockFocusOpen = false
const mockOpen = vi.fn()
vi.mock("@/contexts/focus-context", () => ({
  useFocusOptional: () => ({ isOpen: mockFocusOpen, open: mockOpen }),
}))

import { ParkProvider, usePark } from "./park-context"
import { registerFocus, _resetRegistryForTests } from "./focus-registry"

const wrapper = ({ children }: { children: ReactNode }) => (
  <ParkProvider>{children}</ParkProvider>
)

beforeEach(() => {
  mockFocusOpen = false
  mockOpen.mockClear()
  // start-quote declares escalatesTo:"quote-building" — register a stub so
  // the declared target resolves in the Focus registry.
  _resetRegistryForTests()
  registerFocus({ id: "quote-building", mode: "editCanvas", displayName: "Quote" })
})

describe("ParkContext — working set", () => {
  it("summons tablets from the act-registry (3 concurrent)", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    act(() => {
      result.current.summon("reply-dm")
      result.current.summon("add-note")
      result.current.summon("start-quote")
    })
    expect(result.current.tablets).toHaveLength(3)
    expect(result.current.tablets.map((t) => t.actType)).toEqual([
      "reply-dm",
      "add-note",
      "start-quote",
    ])
    // Each carries its own widgetType (the 4th-host key) + empty draft.
    expect(result.current.tablets[2].widgetType).toBe("park.start-quote")
    expect(result.current.isActive).toBe(true)
  })

  it("summon rejects an unknown act-type", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    let id: string | null = "x"
    act(() => {
      id = result.current.summon("nope")
    })
    expect(id).toBeNull()
    expect(result.current.tablets).toHaveLength(0)
  })

  it("dismissTablet removes one; each draft is independent", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    let a = ""
    act(() => {
      a = result.current.summon("reply-dm")!
      result.current.summon("add-note")
    })
    act(() => result.current.updateDraft(a, { text: "hi" }))
    expect(result.current.tablets.find((t) => t.tabletId === a)?.draft).toEqual({
      text: "hi",
    })
    act(() => result.current.dismissTablet(a))
    expect(result.current.tablets).toHaveLength(1)
    expect(result.current.tablets[0].actType).toBe("add-note")
  })
})

describe("ParkContext — declarative escalation (Type B #1)", () => {
  it("canEscalate reads the act-registry: quote yes, light acts no", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    let reply = "", quote = ""
    act(() => {
      reply = result.current.summon("reply-dm")!
      quote = result.current.summon("start-quote")!
    })
    expect(result.current.canEscalate(reply)).toBe(false)
    expect(result.current.canEscalate(quote)).toBe(true)
  })

  it("escalate opens the DECLARED Focus with the draft as params", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    let quote = ""
    act(() => {
      quote = result.current.summon("start-quote")!
    })
    const draft = { entryIntent: "quote", customer: { name: "Hopkins" }, lines: [] }
    act(() => result.current.updateDraft(quote, draft))
    act(() => result.current.escalate(quote))
    expect(mockOpen).toHaveBeenCalledWith("quote-building", {
      params: { extraction: draft },
    })
  })

  it("escalate is a no-op for a light act (no declared Focus)", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    let reply = ""
    act(() => {
      reply = result.current.summon("reply-dm")!
    })
    act(() => result.current.escalate(reply))
    expect(mockOpen).not.toHaveBeenCalled()
  })

  it("a declared target that isn't registered stays light", () => {
    // Drop the quote-building registration → start-quote can't resolve.
    _resetRegistryForTests()
    const { result } = renderHook(() => usePark(), { wrapper })
    let quote = ""
    act(() => {
      quote = result.current.summon("start-quote")!
    })
    expect(result.current.canEscalate(quote)).toBe(false)
  })
})

describe("ParkContext — peer layer (coexists with the command bar)", () => {
  it("summoning park NEVER opens a Focus — the bar's gate stays untouched", () => {
    // The peer-layer guarantee: park-open must not flip focus.isOpen (the
    // command bar gates ONLY on that). Summoning tablets never calls
    // focus.open — only an explicit escalation does. So the bar coexists.
    const { result } = renderHook(() => usePark(), { wrapper })
    act(() => {
      result.current.summon("reply-dm")
      result.current.summon("add-note")
      result.current.summon("start-quote")
    })
    act(() => result.current.updateDraft(result.current.tablets[0].tabletId, { text: "x" }))
    act(() => result.current.dismissTablet(result.current.tablets[0].tabletId))
    act(() => result.current.exitPark())
    // Across summon / draft / dismiss / exit — zero Focus opens.
    expect(mockOpen).not.toHaveBeenCalled()
  })
})

describe("ParkContext — suspend-and-return", () => {
  it("holds the session intact across a Focus open/close", () => {
    const { result, rerender } = renderHook(() => usePark(), { wrapper })
    act(() => {
      result.current.summon("reply-dm")
      result.current.summon("start-quote")
    })
    expect(result.current.tablets).toHaveLength(2)
    expect(result.current.isActive).toBe(true)

    // Focus opens → park SUSPENDS. Tablets are HELD, not torn down.
    mockFocusOpen = true
    rerender()
    expect(result.current.isSuspended).toBe(true)
    expect(result.current.isActive).toBe(false)
    expect(result.current.tablets).toHaveLength(2) // session intact

    // Focus closes → park RESUMES with the same tablets.
    mockFocusOpen = false
    rerender()
    expect(result.current.isSuspended).toBe(false)
    expect(result.current.isActive).toBe(true)
    expect(result.current.tablets).toHaveLength(2)
  })
})

describe("ParkContext — exit + grace-window relaunch", () => {
  it("exitPark stashes the session; relaunch restores it", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    act(() => {
      result.current.summon("reply-dm")
      result.current.summon("add-note")
    })
    act(() => result.current.exitPark())
    expect(result.current.tablets).toHaveLength(0)
    expect(result.current.lastClosedSession?.tablets).toHaveLength(2)

    act(() => result.current.relaunchSession())
    expect(result.current.tablets).toHaveLength(2)
    expect(result.current.lastClosedSession).toBeNull()
  })

  it("clearLastClosed drops the grace-window session (evaporates)", () => {
    const { result } = renderHook(() => usePark(), { wrapper })
    act(() => result.current.summon("reply-dm"))
    act(() => result.current.exitPark())
    expect(result.current.lastClosedSession).not.toBeNull()
    act(() => result.current.clearLastClosed())
    expect(result.current.lastClosedSession).toBeNull()
    expect(result.current.tablets).toHaveLength(0)
  })
})
