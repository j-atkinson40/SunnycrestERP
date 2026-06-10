/**
 * Toolbar — Builder Craft Arc Phase 1a primitive tests.
 * role="toolbar" AT semantics; groups; separator; wrap opt-in.
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

import { Toolbar, ToolbarGroup, ToolbarSeparator } from "./toolbar"

describe("Toolbar", () => {
  it("renders role=toolbar with grouped controls + separator", () => {
    render(
      <Toolbar aria-label="Editor actions">
        <ToolbarGroup>
          <button>Save</button>
          <button>Discard</button>
        </ToolbarGroup>
        <ToolbarSeparator />
        <ToolbarGroup>
          <button>History</button>
        </ToolbarGroup>
      </Toolbar>,
    )
    const bar = screen.getByRole("toolbar", { name: "Editor actions" })
    expect(bar.querySelectorAll('[data-slot="toolbar-group"]').length).toBe(2)
    expect(bar.querySelector('[data-slot="toolbar-separator"]')).toBeTruthy()
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument()
  })

  it("is single-row by default; wrap opts into flex-wrap", () => {
    const { rerender } = render(<Toolbar data-testid="t">x</Toolbar>)
    expect(screen.getByTestId("t").className).toContain("flex-nowrap")
    rerender(
      <Toolbar data-testid="t" wrap>
        x
      </Toolbar>,
    )
    expect(screen.getByTestId("t").className).toContain("flex-wrap")
  })

  it("controls inside remain keyboard-reachable (no focus hijacking)", () => {
    render(
      <Toolbar>
        <ToolbarGroup>
          <button>One</button>
        </ToolbarGroup>
      </Toolbar>,
    )
    const btn = screen.getByRole("button", { name: "One" })
    btn.focus()
    expect(document.activeElement).toBe(btn)
  })
})
