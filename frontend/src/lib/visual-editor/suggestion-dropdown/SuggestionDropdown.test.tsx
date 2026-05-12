/**
 * Arc 4b.1b — SuggestionDropdown shared component tests.
 *
 * Verifies:
 *   - Renders suggestion list with active row highlighting.
 *   - handleSuggestionKeyDown ArrowDown / ArrowUp navigates with
 *     wrap-around semantics.
 *   - handleSuggestionKeyDown Enter selects active or first.
 *   - handleSuggestionKeyDown Escape cancels.
 *   - Document-level Escape cancels even without trigger focus.
 *   - Click-outside cancels.
 *   - Mouse hover changes active.
 *   - Click row selects suggestion via mousedown (prevents
 *     click-outside race).
 *   - Empty-state renders renderEmpty body.
 *   - data-active="true" on the highlighted row carries source-badge
 *     semantics for tests.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent, cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

import {
  SuggestionDropdown,
  handleSuggestionKeyDown,
} from "./SuggestionDropdown"


afterEach(() => {
  cleanup()
})


interface Item {
  id: string
  label: string
  detail: string
}


function makeItems(): Item[] {
  return [
    { id: "alpha", label: "Alpha", detail: "First item" },
    { id: "beta", label: "Beta", detail: "Second item" },
    { id: "gamma", label: "Gamma", detail: "Third item" },
  ]
}


function renderDropdown(opts: {
  suggestions?: Item[]
  activeId?: string | null
  onActiveChange?: (next: string | null) => void
  onSelect?: (s: Item) => void
  onCancel?: () => void
}) {
  const suggestions = opts.suggestions ?? makeItems()
  const activeId = "activeId" in opts ? opts.activeId! : "alpha"
  const onActiveChange = opts.onActiveChange ?? vi.fn()
  const onSelect = opts.onSelect ?? vi.fn()
  const onCancel = opts.onCancel ?? vi.fn()

  const utils = render(
    <SuggestionDropdown<Item>
      suggestions={suggestions}
      activeId={activeId}
      onActiveChange={onActiveChange}
      onSelect={onSelect}
      onCancel={onCancel}
      getKey={(s) => s.id}
      renderSuggestion={(s, active) => (
        <div data-row-id={s.id}>
          <div>{s.label}</div>
          <div data-testid={`detail-${s.id}`}>{s.detail}</div>
          <span>{active ? "[active]" : ""}</span>
        </div>
      )}
      position={{ top: 100, left: 100 }}
    />,
  )

  return { ...utils, onActiveChange, onSelect, onCancel, suggestions }
}


describe("SuggestionDropdown", () => {
  it("renders suggestion list", () => {
    renderDropdown({})
    expect(screen.getByTestId("suggestion-dropdown")).toBeInTheDocument()
    expect(screen.getByTestId("suggestion-dropdown-option-alpha")).toBeInTheDocument()
    expect(screen.getByTestId("suggestion-dropdown-option-beta")).toBeInTheDocument()
    expect(screen.getByTestId("suggestion-dropdown-option-gamma")).toBeInTheDocument()
  })

  it("highlights active row via data-active=true", () => {
    renderDropdown({ activeId: "beta" })
    const alphaRow = screen.getByTestId("suggestion-dropdown-option-alpha")
    const betaRow = screen.getByTestId("suggestion-dropdown-option-beta")
    expect(alphaRow.getAttribute("data-active")).toBe("false")
    expect(betaRow.getAttribute("data-active")).toBe("true")
  })

  it("renders keyboard hint footer when non-empty", () => {
    renderDropdown({})
    expect(screen.getByTestId("suggestion-dropdown-hint")).toBeInTheDocument()
  })

  it("renders empty state when no suggestions", () => {
    renderDropdown({ suggestions: [] })
    expect(screen.getByTestId("suggestion-dropdown-empty")).toBeInTheDocument()
    // Hint footer hidden when empty
    expect(screen.queryByTestId("suggestion-dropdown-hint")).toBeNull()
  })

  it("mouse hover changes active via onActiveChange", () => {
    const onActiveChange = vi.fn()
    renderDropdown({ activeId: "alpha", onActiveChange })
    fireEvent.mouseEnter(screen.getByTestId("suggestion-dropdown-option-beta"))
    expect(onActiveChange).toHaveBeenCalledWith("beta")
  })

  it("mousedown selects suggestion (prevents click-outside race)", () => {
    const onSelect = vi.fn()
    const items = makeItems()
    renderDropdown({ activeId: "alpha", onSelect, suggestions: items })
    fireEvent.mouseDown(screen.getByTestId("suggestion-dropdown-option-beta"))
    expect(onSelect).toHaveBeenCalledWith(items[1])
  })

  it("click outside cancels", () => {
    const onCancel = vi.fn()
    // Render the dropdown alongside an outside button
    render(
      <>
        <button data-testid="outside-button">Outside</button>
        <SuggestionDropdown<Item>
          suggestions={makeItems()}
          activeId="alpha"
          onActiveChange={vi.fn()}
          onSelect={vi.fn()}
          onCancel={onCancel}
          getKey={(s) => s.id}
          renderSuggestion={(s) => <span>{s.label}</span>}
          position={{ top: 0, left: 0 }}
        />
      </>,
    )
    fireEvent.mouseDown(screen.getByTestId("outside-button"))
    expect(onCancel).toHaveBeenCalled()
  })

  it("document Escape cancels", () => {
    const onCancel = vi.fn()
    renderDropdown({ onCancel })
    fireEvent.keyDown(document, { key: "Escape" })
    expect(onCancel).toHaveBeenCalled()
  })
})


describe("handleSuggestionKeyDown", () => {
  const items = makeItems()

  function makeOpts(overrides: {
    activeId?: string | null
    onActiveChange?: (next: string | null) => void
    onSelect?: (s: Item) => void
    onCancel?: () => void
    suggestions?: Item[]
  } = {}) {
    return {
      suggestions: overrides.suggestions ?? items,
      activeId: "activeId" in overrides ? overrides.activeId! : "alpha",
      onActiveChange: overrides.onActiveChange ?? vi.fn(),
      onSelect: overrides.onSelect ?? vi.fn(),
      onCancel: overrides.onCancel ?? vi.fn(),
      getKey: (s: Item) => s.id,
    }
  }

  function makeEvent(key: string): KeyboardEvent {
    const ev = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true })
    return ev
  }

  it("ArrowDown advances to next suggestion", () => {
    const onActiveChange = vi.fn()
    const opts = makeOpts({ activeId: "alpha", onActiveChange })
    const handled = handleSuggestionKeyDown(makeEvent("ArrowDown"), opts)
    expect(handled).toBe(true)
    expect(onActiveChange).toHaveBeenCalledWith("beta")
  })

  it("ArrowDown wraps from last to first", () => {
    const onActiveChange = vi.fn()
    const opts = makeOpts({ activeId: "gamma", onActiveChange })
    handleSuggestionKeyDown(makeEvent("ArrowDown"), opts)
    expect(onActiveChange).toHaveBeenCalledWith("alpha")
  })

  it("ArrowUp wraps from first to last", () => {
    const onActiveChange = vi.fn()
    const opts = makeOpts({ activeId: "alpha", onActiveChange })
    handleSuggestionKeyDown(makeEvent("ArrowUp"), opts)
    expect(onActiveChange).toHaveBeenCalledWith("gamma")
  })

  it("ArrowDown on null active picks first", () => {
    const onActiveChange = vi.fn()
    const opts = makeOpts({ activeId: null, onActiveChange })
    handleSuggestionKeyDown(makeEvent("ArrowDown"), opts)
    expect(onActiveChange).toHaveBeenCalledWith("alpha")
  })

  it("Enter selects the active suggestion", () => {
    const onSelect = vi.fn()
    const opts = makeOpts({ activeId: "beta", onSelect })
    handleSuggestionKeyDown(makeEvent("Enter"), opts)
    expect(onSelect).toHaveBeenCalledWith(items[1])
  })

  it("Enter without active picks first when list non-empty", () => {
    const onSelect = vi.fn()
    const opts = makeOpts({ activeId: null, onSelect })
    handleSuggestionKeyDown(makeEvent("Enter"), opts)
    expect(onSelect).toHaveBeenCalledWith(items[0])
  })

  it("Enter on empty list cancels", () => {
    const onSelect = vi.fn()
    const onCancel = vi.fn()
    const opts = makeOpts({
      activeId: null,
      onSelect,
      onCancel,
      suggestions: [],
    })
    handleSuggestionKeyDown(makeEvent("Enter"), opts)
    expect(onSelect).not.toHaveBeenCalled()
    expect(onCancel).toHaveBeenCalled()
  })

  it("Escape cancels", () => {
    const onCancel = vi.fn()
    const opts = makeOpts({ onCancel })
    handleSuggestionKeyDown(makeEvent("Escape"), opts)
    expect(onCancel).toHaveBeenCalled()
  })

  it("returns false for unhandled keys", () => {
    const opts = makeOpts()
    expect(handleSuggestionKeyDown(makeEvent("a"), opts)).toBe(false)
    expect(handleSuggestionKeyDown(makeEvent("Tab"), opts)).toBe(false)
  })

  it("ArrowDown on empty list returns true without crashing", () => {
    const onActiveChange = vi.fn()
    const opts = makeOpts({ activeId: null, onActiveChange, suggestions: [] })
    expect(handleSuggestionKeyDown(makeEvent("ArrowDown"), opts)).toBe(true)
    expect(onActiveChange).not.toHaveBeenCalled()
  })
})
