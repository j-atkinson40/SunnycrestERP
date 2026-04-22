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
    // Use test-single-record (no seeded widgets) so tier detection
    // resolves to canvas at the default jsdom viewport; dev-grid
    // only renders in canvas tier. test-kanban's 3 seeded widgets
    // would force stack at jsdom's default 1024×768 viewport per
    // Session 3.7 content-aware detection.
    render(<Harness initialEntry="/?focus=test-single-record&dev-canvas=1" />)
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

  it("renders canvas tier widgets at ultra-wide viewport (3840×2160)", async () => {
    // Session 3.7 post-verification fix — tier detection is now
    // content-aware. Seeded Kanban fixture has 3 widgets at 320/280
    // pixel widths, which don't fit in canvas reserved space until
    // the viewport is generous enough (reserved ≥ widget+16 per side).
    // 3840×2160 (4K) gives reservedLeft/Right=1220 + reservedTop/
    // Bottom=630 — seeded widgets fit comfortably → canvas tier.
    setViewport(3840, 2160)
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

  it("seeded widgets force stack at 1920×1080 (content-aware transition)", async () => {
    // Regression guard for the Session 3.7 verification bug — the old
    // viewport-only `vw < 1000 OR vh < 700` heuristic would have
    // returned canvas at 1920×1080, which caused the 3 seeded widgets
    // to render clipped at viewport edges. Content-aware detection
    // catches reserved-space overflow and picks stack instead.
    setViewport(1920, 1080)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "stack")
      expect(
        document.querySelector('[data-slot="focus-stack-rail"]'),
      ).toBeInTheDocument()
      expect(
        document.querySelector('[data-slot="focus-widget-chrome"]'),
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
    // Start ultra-wide — seeded widgets fit canvas reserved space.
    setViewport(3840, 2160)
    render(<Harness />)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Transition to stack-forcing viewport — widget still rendered
    // (via StackRail scroll-snap tile now instead of WidgetChrome).
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

    // Transition to 1920×1080 (still stack per content-aware detection
    // with seeded widgets) — widget rendered via StackRail again.
    setViewport(1920, 1080)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Back to ultra-wide — canvas tier restored, widget in WidgetChrome.
    setViewport(3840, 2160)
    await new Promise((r) => setTimeout(r, 50))
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    setViewport(1440, 900)
  })
})
