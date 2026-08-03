import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import { RankedRows } from "./RankedRows"

afterEach(cleanup)

function setup(count: number, opts: { escape?: boolean } = {}) {
  const onSelect = vi.fn()
  const onEscape = vi.fn()
  const items = Array.from({ length: count }, (_, i) => `item${i + 1}`)
  render(
    <RankedRows
      items={items}
      getKey={(x) => x}
      renderItem={(x) => <span>{x}</span>}
      onSelect={onSelect}
      escape={opts.escape ? { label: "None of these", onSelect: onEscape } : undefined}
      ariaLabel="rows"
    />,
  )
  return { onSelect, onEscape, items }
}

describe("RankedRows — numbered selection", () => {
  it("selects the right row across the full 1..9 range, including the 9 boundary", () => {
    const { onSelect } = setup(9)
    fireEvent.keyDown(document.body, { key: "1", code: "Digit1" })
    fireEvent.keyDown(document.body, { key: "5", code: "Digit5" })
    fireEvent.keyDown(document.body, { key: "9", code: "Digit9" })
    expect(onSelect.mock.calls.map((c) => c[1])).toEqual([0, 4, 8])
  })

  it("a digit past the item count does nothing (no surprise at the edge)", () => {
    const { onSelect } = setup(3)
    fireEvent.keyDown(document.body, { key: "9", code: "Digit9" })
    fireEvent.keyDown(document.body, { key: "4", code: "Digit4" })
    expect(onSelect).not.toHaveBeenCalled()
  })
})

describe("RankedRows — Mac Option layer via e.code", () => {
  // Option+digit rewrites e.key to a symbol (Option+9 → "¡", Option+5 → "∞");
  // e.code stays "DigitN". The mapping must behave the SAME at 9 as at 5.
  it("Option+9 selects row 9 by e.code even though e.key is a symbol", () => {
    const { onSelect } = setup(9)
    fireEvent.keyDown(document.body, { key: "¡", code: "Digit9", altKey: true })
    expect(onSelect).toHaveBeenCalledWith("item9", 8)
  })

  it("Option+5 selects row 5 the same way — parity across the widened range", () => {
    const { onSelect } = setup(9)
    fireEvent.keyDown(document.body, { key: "∞", code: "Digit5", altKey: true })
    expect(onSelect).toHaveBeenCalledWith("item5", 4)
  })
})

describe("RankedRows — the escape row (key 0) is a distinct affordance", () => {
  it("0 fires escape, never a numbered selection", () => {
    const { onSelect, onEscape } = setup(5, { escape: true })
    fireEvent.keyDown(document.body, { key: "0", code: "Digit0" })
    expect(onEscape).toHaveBeenCalledTimes(1)
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("0 with no escape row does nothing (no crash, no surprise)", () => {
    const { onSelect } = setup(5)
    fireEvent.keyDown(document.body, { key: "0", code: "Digit0" })
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("the escape row renders below a divider and is not numbered as row 6", () => {
    setup(5, { escape: true })
    // five numbered badges (1..5) + the escape badge "0" — never a "6".
    expect(screen.getByText("None of these")).toBeInTheDocument()
    expect(screen.queryByText("6")).not.toBeInTheDocument()
    expect(screen.getByRole("separator")).toBeInTheDocument()
  })
})

describe("RankedRows — input-focus guard", () => {
  function setupWithInput(count: number) {
    const onSelect = vi.fn()
    const items = Array.from({ length: count }, (_, i) => `item${i + 1}`)
    render(
      <div>
        <input data-testid="search" />
        <RankedRows items={items} getKey={(x) => x} renderItem={(x) => <span>{x}</span>} onSelect={onSelect} />
      </div>,
    )
    const input = screen.getByTestId("search") as HTMLInputElement
    input.focus()
    return { onSelect, input }
  }

  it("a bare digit while an input is focused types (does not select)", () => {
    const { onSelect, input } = setupWithInput(5)
    fireEvent.keyDown(input, { key: "2", code: "Digit2" })
    expect(onSelect).not.toHaveBeenCalled()
  })

  it("a modifier chord selects even while the input is focused", () => {
    const { onSelect, input } = setupWithInput(5)
    fireEvent.keyDown(input, { key: "2", code: "Digit2", altKey: true })
    expect(onSelect).toHaveBeenCalledWith("item2", 1)
  })

  it("Enter selects the active row even from the input", () => {
    const { onSelect, input } = setupWithInput(5)
    fireEvent.keyDown(input, { key: "ArrowDown" })
    fireEvent.keyDown(input, { key: "Enter" })
    expect(onSelect).toHaveBeenCalledWith("item2", 1)
  })
})

describe("RankedRows — accessibility", () => {
  it("is a focusable listbox of options, active row tracked via aria-activedescendant", () => {
    setup(3)
    const listbox = screen.getByRole("listbox")
    expect(listbox).toHaveAttribute("tabindex", "0")
    const options = screen.getAllByRole("option")
    expect(options).toHaveLength(3)
    // active starts at row 0; activedescendant points at its id
    expect(options[0]).toHaveAttribute("aria-selected", "true")
    expect(listbox).toHaveAttribute("aria-activedescendant", options[0].id)

    fireEvent.keyDown(document.body, { key: "ArrowDown" })
    // arrow moves the active row AND the announced descendant, without moving focus
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true")
    expect(screen.getByRole("listbox")).toHaveAttribute(
      "aria-activedescendant",
      screen.getAllByRole("option")[1].id,
    )
  })

  it("the escape row is NOT a listbox option (it sits outside the listbox)", () => {
    setup(3, { escape: true })
    // only the three real rows are options; the escape button is not one
    expect(screen.getAllByRole("option")).toHaveLength(3)
    const escapeBtn = screen.getByText("None of these").closest("button")!
    expect(escapeBtn).not.toHaveAttribute("role", "option")
    expect(escapeBtn.closest('[role="listbox"]')).toBeNull()
  })
})

describe("RankedRows — arrow nav + click + empty", () => {
  it("ArrowDown moves the active row and Enter selects it", () => {
    const { onSelect } = setup(3)
    fireEvent.keyDown(document.body, { key: "ArrowDown" })
    fireEvent.keyDown(document.body, { key: "ArrowDown" })
    fireEvent.keyDown(document.body, { key: "Enter" })
    expect(onSelect).toHaveBeenCalledWith("item3", 2)
  })

  it("clicking a row selects it", () => {
    const { onSelect } = setup(3)
    fireEvent.click(screen.getByText("item2"))
    expect(onSelect).toHaveBeenCalledWith("item2", 1)
  })

  it("an empty item array renders nothing and never breaks on key/enter", () => {
    const { onSelect, onEscape } = setup(0, { escape: true })
    fireEvent.keyDown(document.body, { key: "1", code: "Digit1" })
    fireEvent.keyDown(document.body, { key: "Enter" })
    fireEvent.keyDown(document.body, { key: "ArrowDown" })
    expect(onSelect).not.toHaveBeenCalled()
    // the escape row still works with zero items
    fireEvent.keyDown(document.body, { key: "0", code: "Digit0" })
    expect(onEscape).toHaveBeenCalledTimes(1)
  })
})
