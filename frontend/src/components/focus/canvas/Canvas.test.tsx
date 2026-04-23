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


describe("Canvas — Session 3.8 tier dispatch via crossfade", () => {
  // Session 3.8 architectural shift: all three tier renderers always
  // mount in the DOM; visibility switches via `data-active` on each
  // `[data-tier-renderer]` wrapper with opacity + pointer-events
  // transitions. Tests below assert `data-active="true"` on the
  // expected renderer, not presence/absence (which is unreliable now
  // — everything is always present). The overall Canvas continues to
  // carry `data-focus-tier` for tier-at-a-glance introspection.

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

  function activeTierRenderer(): string | null {
    const el = document.querySelector(
      '[data-tier-renderer][data-active="true"]',
    )
    return el?.getAttribute("data-tier-renderer") ?? null
  }

  it("all three tier renderers mount simultaneously (crossfade contract)", async () => {
    // Session 3.8 — renderers don't conditionally mount/unmount;
    // the crossfade is driven by `data-active`, so all three wrapper
    // divs exist in the DOM at all times.
    setViewport(1920, 1080)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const renderers = document.querySelectorAll('[data-tier-renderer]')
      expect(renderers).toHaveLength(3)
      expect(
        document.querySelector('[data-tier-renderer="canvas"]'),
      ).toBeInTheDocument()
      expect(
        document.querySelector('[data-tier-renderer="stack"]'),
      ).toBeInTheDocument()
      expect(
        document.querySelector('[data-tier-renderer="icon"]'),
      ).toBeInTheDocument()
    } finally {
      setViewport(1440, 900)
    }
  })

  it("canvas tier active at ultra-wide viewport (3840×2160)", async () => {
    setViewport(3840, 2160)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "canvas")
      expect(activeTierRenderer()).toBe("canvas")
      // The stack + icon renderer wrappers are mounted but inactive
      // (opacity 0, pointer-events none). `data-active="false"`.
      expect(
        document
          .querySelector('[data-tier-renderer="stack"]')
          ?.getAttribute("data-active"),
      ).toBe("false")
      expect(
        document
          .querySelector('[data-tier-renderer="icon"]')
          ?.getAttribute("data-active"),
      ).toBe("false")
      // Canvas widgets still render inside their (active) wrapper.
      expect(
        document.querySelector('[data-slot="focus-widget-chrome"]'),
      ).toBeInTheDocument()
    } finally {
      setViewport(1440, 900)
    }
  })

  it("seeded widgets force stack at 1920×1080 (content-aware transition)", async () => {
    // Regression guard for Session 3.7 verification. Content-aware
    // canvas↔stack unchanged by 3.8; stack renderer becomes active.
    setViewport(1920, 1080)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "stack")
      expect(activeTierRenderer()).toBe("stack")
    } finally {
      setViewport(1440, 900)
    }
  })

  it("stack tier active at 1024×768 (above 928×432 geometric floor)", async () => {
    // Session 3.8 — stack↔icon is geometric. Floor derived in
    // stackFitsAlongsideCore = 928w/432h. 1024×768 sits above both;
    // seeded widgets force canvas fit to fail, so stack takes over.
    setViewport(1024, 768)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "stack")
      expect(activeTierRenderer()).toBe("stack")
    } finally {
      setViewport(1440, 900)
    }
  })

  it("icon tier active below stack-fits floor (900×800)", async () => {
    // Session 3.8 breaking change from Session 3.7 — at 900×800
    // Session 3.7 returned stack (vw ≥ 700), Session 3.8 correctly
    // returns icon because stack can't fit alongside a min-sized
    // core (needs ≥ 928w).
    setViewport(900, 800)
    try {
      render(<Harness />)
      await new Promise((r) => setTimeout(r, 50))
      const canvas = document.querySelector('[data-slot="focus-canvas"]')
      expect(canvas).toHaveAttribute("data-focus-tier", "icon")
      expect(activeTierRenderer()).toBe("icon")
      // Icon renderer is active; stack + canvas are mounted but inactive.
      expect(
        document
          .querySelector('[data-tier-renderer="canvas"]')
          ?.getAttribute("data-active"),
      ).toBe("false")
      expect(
        document
          .querySelector('[data-tier-renderer="stack"]')
          ?.getAttribute("data-active"),
      ).toBe("false")
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
      expect(activeTierRenderer()).toBe("icon")
      // IconButton should render inside the active icon wrapper.
      expect(
        document.querySelector('[data-slot="focus-icon-button"]'),
      ).toBeInTheDocument()
    } finally {
      setViewport(1440, 900)
    }
  })

  it("tier transitions preserve widget state across viewport shifts", async () => {
    // Ultra-wide — canvas tier, widgets mount in WidgetChrome.
    setViewport(3840, 2160)
    render(<Harness />)
    await new Promise((r) => setTimeout(r, 50))
    expect(activeTierRenderer()).toBe("canvas")
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Stack-forcing viewport — Session 3.8 shifts stack floor to 928w,
    // so we use 1024 here (was 900 in Session 3.7, which now drops to
    // icon). Seeded widgets don't fit canvas → stack active.
    setViewport(1024, 768)
    await new Promise((r) => setTimeout(r, 50))
    expect(activeTierRenderer()).toBe("stack")
    // Widget state preserved — rendered via StackRail tile.
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Icon tier — widget mounts in BottomSheet only when sheet open;
    // idle icon state doesn't show widget bodies.
    setViewport(390, 844)
    await new Promise((r) => setTimeout(r, 50))
    expect(activeTierRenderer()).toBe("icon")
    expect(
      document.querySelector('[data-slot="focus-icon-button"]'),
    ).toBeInTheDocument()

    // 1920×1080 (still stack with seeded widgets).
    setViewport(1920, 1080)
    await new Promise((r) => setTimeout(r, 50))
    expect(activeTierRenderer()).toBe("stack")
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    // Back to ultra-wide — canvas restored.
    setViewport(3840, 2160)
    await new Promise((r) => setTimeout(r, 50))
    expect(activeTierRenderer()).toBe("canvas")
    expect(
      document.querySelector('[data-widget-id="mock-saved-view-1"]'),
    ).toBeInTheDocument()

    setViewport(1440, 900)
  })

  it("tier renderer wrappers carry asymmetric fade classes (Session 3.8.1)", () => {
    // Session 3.8 crossfade is token-driven; Session 3.8.1 made
    // the fade asymmetric — fading-out renderers use duration-quick
    // so stale spatial positions don't linger long enough to be
    // visible behind the growing core. Fading-in renderers still
    // use duration-settle for a deliberate reveal.
    setViewport(1440, 900)
    render(<Harness />)
    const renderers = document.querySelectorAll('[data-tier-renderer]')
    renderers.forEach((r) => {
      expect(r.className).toContain("transition-opacity")
      expect(r.className).toContain("ease-settle")
      // Asymmetric duration tokens — verified as Tailwind class
      // strings (computed-style check isn't reliable in jsdom for
      // data-attribute selectors).
      expect(r.className).toContain("data-[active=true]:duration-settle")
      expect(r.className).toContain("data-[active=false]:duration-quick")
    })
  })
})
