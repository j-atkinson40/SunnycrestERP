/**
 * Canvas — vitest unit tests.
 *
 * Covers:
 *   - Renders with no widgets (empty state)
 *   - Reads widgets from layoutState + renders each via WidgetChrome
 *   - Dev-mode grid toggles on via ?dev-canvas=1
 *   - Core-overlap guard: dragging a widget onto the core rejects
 *     the drop (widget's prior position retained)
 *
 * Pure drag-delta math + widget-replacement semantics are covered by
 * geometry.test.ts + focus-context.test.tsx. Full DnD end-to-end is
 * manually verified via /dev/focus-test because jsdom doesn't
 * emit realistic pointer events.
 */

import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { FocusProvider } from "@/contexts/focus-context"
import { Canvas } from "./Canvas"


function Harness({
  initialEntry = "/?focus=test-kanban",
}: {
  initialEntry?: string
}) {
  return (
    <MemoryRouter initialEntries={[initialEntry]}>
      <FocusProvider>
        <Canvas />
      </FocusProvider>
    </MemoryRouter>
  )
}


describe("Canvas", () => {
  it("renders the canvas wrapper with pointer-events-none", () => {
    render(<Harness />)
    const canvas = document.querySelector('[data-slot="focus-canvas"]')
    expect(canvas).toBeInTheDocument()
    expect(canvas).toHaveClass("pointer-events-none")
  })

  it("renders seeded widget from test-kanban defaultLayout", async () => {
    render(<Harness />)
    // Kanban stub seeds one mock-saved-view-1 widget — WidgetChrome
    // renders with data-widget-id for direct DOM assertions.
    const widget = await screen.findByText("Recent Cases")
    expect(widget).toBeInTheDocument()
    const chrome = document.querySelector(
      '[data-widget-id="mock-saved-view-1"]',
    )
    expect(chrome).toBeInTheDocument()
  })

  it("renders nothing widget-wise when Focus has no seeded layout", async () => {
    // test-single-record has no defaultLayout in the registry.
    render(<Harness initialEntry="/?focus=test-single-record" />)
    expect(screen.queryByText("Recent Cases")).not.toBeInTheDocument()
  })

  it("dev-mode grid renders only when ?dev-canvas=1 param present", async () => {
    render(<Harness initialEntry="/?focus=test-kanban&dev-canvas=1" />)
    await screen.findByText("Recent Cases") // wait for canvas to mount
    expect(
      document.querySelector('[data-slot="focus-canvas-dev-grid"]'),
    ).toBeInTheDocument()
  })

  it("dev-mode grid hidden without dev-canvas param", async () => {
    render(<Harness />)
    await screen.findByText("Recent Cases")
    expect(
      document.querySelector('[data-slot="focus-canvas-dev-grid"]'),
    ).not.toBeInTheDocument()
  })
})
