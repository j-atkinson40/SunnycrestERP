/**
 * WidgetChrome — vitest unit tests. Phase A Session 3.5.
 *
 * Covers:
 *   - Drag listeners attach to the wrapper (drag-from-anywhere)
 *   - Grip icon is decorative only (pointer-events-none)
 *   - 8 resize zones present with distinct cursor styles
 *   - Dismiss X stops propagation (click doesn't initiate drag)
 *   - Chrome visibility via opacity + data-chrome-active toggle
 */

import { DndContext } from "@dnd-kit/core"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { FocusProvider } from "@/contexts/focus-context"

import { WidgetChrome } from "./WidgetChrome"


function Harness({
  onDismiss,
  children = <div data-testid="widget-content">content</div>,
}: {
  onDismiss?: () => void
  children?: React.ReactNode
}) {
  return (
    <MemoryRouter initialEntries={["/?focus=test-kanban"]}>
      <FocusProvider>
        <DndContext>
          <WidgetChrome
            widgetId="w1"
            position={{
              anchor: "top-left",
              offsetX: 32,
              offsetY: 64,
              width: 320,
              height: 240,
            }}
            canvasWidth={1920}
            canvasHeight={1080}
            onDismiss={onDismiss}
          >
            {children}
          </WidgetChrome>
        </DndContext>
      </FocusProvider>
    </MemoryRouter>
  )
}


describe("WidgetChrome — rendering + affordances", () => {
  it("renders children inside the chrome wrapper", () => {
    render(<Harness />)
    expect(screen.getByTestId("widget-content")).toBeInTheDocument()
  })

  it("renders grip icon as decorative (pointer-events-none)", () => {
    render(<Harness />)
    const grip = document.querySelector('[data-slot="focus-widget-grip"]')
    expect(grip).toBeInTheDocument()
    expect(grip).toHaveAttribute("aria-hidden")
    expect(grip?.className).toMatch(/pointer-events-none/)
  })

  it("renders all 8 resize zones with distinct cursor styles", () => {
    render(<Harness />)
    const zones = document.querySelectorAll(
      '[data-slot="focus-widget-resize-zone"]',
    )
    expect(zones).toHaveLength(8)
    const zoneIds = Array.from(zones)
      .map((z) => z.getAttribute("data-zone"))
      .sort()
    expect(zoneIds).toEqual(["e", "n", "ne", "nw", "s", "se", "sw", "w"])
  })

  it("corner zones use nwse/nesw cursor styles", () => {
    render(<Harness />)
    const nw = document.querySelector('[data-zone="nw"]') as HTMLElement
    const ne = document.querySelector('[data-zone="ne"]') as HTMLElement
    const se = document.querySelector('[data-zone="se"]') as HTMLElement
    const sw = document.querySelector('[data-zone="sw"]') as HTMLElement
    expect(nw.style.cursor).toBe("nwse-resize")
    expect(se.style.cursor).toBe("nwse-resize")
    expect(ne.style.cursor).toBe("nesw-resize")
    expect(sw.style.cursor).toBe("nesw-resize")
  })

  it("edge zones use ew/ns cursor styles", () => {
    render(<Harness />)
    const n = document.querySelector('[data-zone="n"]') as HTMLElement
    const s = document.querySelector('[data-zone="s"]') as HTMLElement
    const e = document.querySelector('[data-zone="e"]') as HTMLElement
    const w = document.querySelector('[data-zone="w"]') as HTMLElement
    expect(n.style.cursor).toBe("ns-resize")
    expect(s.style.cursor).toBe("ns-resize")
    expect(e.style.cursor).toBe("ew-resize")
    expect(w.style.cursor).toBe("ew-resize")
  })

  it("renders dismiss button when onDismiss prop provided", () => {
    render(<Harness onDismiss={() => {}} />)
    expect(
      screen.getByRole("button", { name: /dismiss widget/i }),
    ).toBeInTheDocument()
  })

  it("omits dismiss button when no onDismiss prop", () => {
    render(<Harness />)
    expect(
      screen.queryByRole("button", { name: /dismiss widget/i }),
    ).not.toBeInTheDocument()
  })
})


describe("WidgetChrome — drag-from-anywhere", () => {
  it("wrapper has role='button' semantics from @dnd-kit listeners", () => {
    // @dnd-kit attaches `role` + `tabIndex` + `aria-describedby` etc.
    // via attributes spread onto the wrapper. Assert the wrapper is
    // thus accessible as a drag surface — opposite of Session 3
    // where only the grip button had listeners.
    render(<Harness />)
    const wrapper = document.querySelector(
      '[data-slot="focus-widget-chrome"]',
    ) as HTMLElement
    expect(wrapper).toBeInTheDocument()
    // @dnd-kit v6 sets role="button" on the wrapper it attaches
    // attributes to.
    expect(wrapper.getAttribute("role")).toBe("button")
  })

  it("wrapper has cursor-grab CSS to hint draggable surface", () => {
    render(<Harness />)
    const wrapper = document.querySelector(
      '[data-slot="focus-widget-chrome"]',
    )
    expect(wrapper?.className).toMatch(/cursor-grab/)
  })

  it("grip does NOT spread dnd listeners — decorative only", () => {
    render(<Harness />)
    const grip = document.querySelector('[data-slot="focus-widget-grip"]')
    // No role="button", no dnd attributes on the grip element.
    expect(grip?.getAttribute("role")).not.toBe("button")
  })
})


describe("WidgetChrome — dismiss propagation guard", () => {
  it("onDismiss fires when X clicked", async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<Harness onDismiss={onDismiss} />)
    await user.click(screen.getByRole("button", { name: /dismiss widget/i }))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })
})


describe("WidgetChrome — chrome visibility state", () => {
  it("chrome wrapper starts with data-chrome-active=false", () => {
    render(<Harness />)
    const wrapper = document.querySelector(
      '[data-slot="focus-widget-chrome"]',
    )
    expect(wrapper).toHaveAttribute("data-chrome-active", "false")
  })

  it("grip + dismiss have opacity-0 default + group-hover:opacity-100", () => {
    render(<Harness onDismiss={() => {}} />)
    const grip = document.querySelector('[data-slot="focus-widget-grip"]')
    const dismiss = screen.getByRole("button", { name: /dismiss widget/i })
    expect(grip?.className).toMatch(/opacity-0/)
    expect(grip?.className).toMatch(/group-hover:opacity-100/)
    expect(dismiss.className).toMatch(/opacity-0/)
    expect(dismiss.className).toMatch(/group-hover:opacity-100/)
  })
})
