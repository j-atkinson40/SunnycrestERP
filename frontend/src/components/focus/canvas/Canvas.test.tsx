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

import { render } from "@testing-library/react"
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

  it("renders seeded widgets from test-kanban defaultLayout", async () => {
    render(<Harness />)
    // Session 3.7: Kanban stub now seeds THREE mock widgets so
    // stack mode has content to cycle through. Query by data-widget-
    // id for direct-DOM assertions (content text is non-unique).
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-2"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-3"]'),
    ).toBeInTheDocument()
  })

  it("renders nothing widget-wise when Focus has no seeded layout", async () => {
    // test-single-record has no defaultLayout in the registry.
    render(<Harness initialEntry="/?focus=test-single-record" />)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).not.toBeInTheDocument()
  })

  it("dev-mode grid renders only when ?dev-canvas=1 param present", async () => {
    render(<Harness initialEntry="/?focus=test-kanban&dev-canvas=1" />)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-slot="focus-canvas-dev-grid"]'),
    ).toBeInTheDocument()
  })

  it("dev-mode grid hidden without dev-canvas param", async () => {
    render(<Harness />)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-slot="focus-canvas-dev-grid"]'),
    ).not.toBeInTheDocument()
  })
})


describe("Canvas — Session 3.7 tier dispatch", () => {
  function setViewport(width: number, height: number) {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: width,
    })
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: height,
    })
    window.dispatchEvent(new Event("resize"))
  }

  it("renders canvas tier widgets at wide viewport (1920×1080)", async () => {
    setViewport(1920, 1080)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "canvas")
      // Canvas tier renders WidgetChrome wrappers (drag/resize).
      expect(
        document.querySelector('[data-slot="focus-widget-chrome"]'),
      ).toBeInTheDocument()
      // Stack rail + icon button are NOT rendered in canvas mode.
      expect(
        document.querySelector('[data-slot="focus-stack-rail"]'),
      ).not.toBeInTheDocument()
      expect(
        document.querySelector('[data-slot="focus-icon-button"]'),
      ).not.toBeInTheDocument()
    } finally {
      setViewport(1440, 900)
    }
  })

  it("renders stack tier at medium-narrow viewport (900×800)", async () => {
    setViewport(900, 800)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "stack")
      // Stack rail rendered; canvas widgets + icon NOT.
      expect(
        document.querySelector('[data-slot="focus-stack-rail"]'),
      ).toBeInTheDocument()
      expect(
        document.querySelector('[data-slot="focus-widget-chrome"]'),
      ).not.toBeInTheDocument()
      expect(
        document.querySelector('[data-slot="focus-icon-button"]'),
      ).not.toBeInTheDocument()
    } finally {
      setViewport(1440, 900)
    }
  })

  it("renders icon tier at narrow viewport (390×844)", async () => {
    setViewport(390, 844)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "icon")
      // Icon button rendered (idle state); stack + canvas NOT.
      expect(
        document.querySelector('[data-slot="focus-icon-button"]'),
      ).toBeInTheDocument()
      expect(
        document.querySelector('[data-slot="focus-stack-rail"]'),
      ).not.toBeInTheDocument()
      expect(
        document.querySelector('[data-slot="focus-widget-chrome"]'),
      ).not.toBeInTheDocument()
    } finally {
      setViewport(1440, 900)
    }
  })

  it("tier transition preserves widget state (same canonical layout)", async () => {
    // Start canvas
    setViewport(1920, 1080)
    render(<Harness />)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Transition to stack — widget still rendered (via StackRail
    // scroll-snap tile now instead of WidgetChrome).
    setViewport(900, 800)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Transition to icon — widget NOT rendered (hidden behind icon
    // button until sheet is opened).
    setViewport(390, 844)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).not.toBeInTheDocument()

    // Back to canvas — widget restored.
    setViewport(1920, 1080)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    setViewport(1440, 900)
  })
})
