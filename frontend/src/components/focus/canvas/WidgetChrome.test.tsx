/**
 * WidgetChrome — vitest unit tests.
 *
 * Tests the chrome-visibility contract + dismiss behavior + required
 * ARIA affordances. Drag integration tested in Canvas.test.tsx
 * (where DndContext is mounted); resize is covered by geometry.test
 * for the pure-function math + manual verification for the
 * interaction (pointer events are awkward to unit-test in jsdom).
 */

import { DndContext } from "@dnd-kit/core"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { WidgetChrome } from "./WidgetChrome"
import { MemoryRouter } from "react-router-dom"
import { FocusProvider } from "@/contexts/focus-context"


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
            position={{ x: 100, y: 100, width: 320, height: 240 }}
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


describe("WidgetChrome", () => {
  it("renders children inside the chrome wrapper", () => {
    render(<Harness />)
    expect(screen.getByTestId("widget-content")).toBeInTheDocument()
  })

  it("renders drag handle + resize corner + dismiss button", () => {
    render(<Harness onDismiss={() => {}} />)
    expect(
      screen.getByRole("button", { name: /drag widget/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /resize widget/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /dismiss widget/i }),
    ).toBeInTheDocument()
  })

  it("omits the dismiss button when no onDismiss prop provided", () => {
    render(<Harness />)
    expect(
      screen.queryByRole("button", { name: /dismiss widget/i }),
    ).not.toBeInTheDocument()
  })

  it("chrome affordances are ghosted by default via opacity-0 class", () => {
    render(<Harness onDismiss={() => {}} />)
    const dragHandle = screen.getByRole("button", { name: /drag widget/i })
    // Visibility is CSS-driven via group-hover; assert the opacity-0
    // class is present so jsdom at least sees the rule in
    // className. Real browsers fade-in on hover per DESIGN_LANGUAGE
    // §6 restraint principle.
    expect(dragHandle.className).toMatch(/opacity-0/)
    expect(dragHandle.className).toMatch(/group-hover:opacity-100/)
  })

  it("chrome stays visible during active drag/resize via data-chrome-active", () => {
    render(<Harness onDismiss={() => {}} />)
    const wrapper = document.querySelector(
      '[data-slot="focus-widget-chrome"]',
    )
    expect(wrapper).toHaveAttribute("data-chrome-active", "false")
  })

  it("onDismiss fires when dismiss button clicked", async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<Harness onDismiss={onDismiss} />)

    await user.click(screen.getByRole("button", { name: /dismiss widget/i }))

    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it("exposes widget id via data attribute for DOM tooling", () => {
    render(<Harness />)
    const wrapper = document.querySelector(
      '[data-slot="focus-widget-chrome"]',
    )
    expect(wrapper).toHaveAttribute("data-widget-id", "w1")
  })
})
