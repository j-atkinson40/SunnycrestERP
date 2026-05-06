/**
 * Phase R-1 — SelectionOverlay tests.
 *
 * Two contracts to lock:
 *   1. Click-to-edit walks up to the nearest [data-component-name].
 *   2. Capture-phase handler blocks operational handlers — widget-
 *      level onClick MUST NOT fire when edit-mode is active.
 *
 * Test (2) is the operational-handler safety pass for R-1's 6 widgets:
 * none of them install capture-phase listeners, so document-level
 * capture + stopPropagation is sufficient to block their bubble-phase
 * onClick handlers.
 */
import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, cleanup, fireEvent } from "@testing-library/react"

import { EditModeProvider } from "./edit-mode-context"
import { SelectionOverlay } from "./SelectionOverlay"


afterEach(cleanup)


describe("SelectionOverlay", () => {
  it("selects the widget on click in edit mode", () => {
    render(
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user-1"
        initialMode="edit"
      >
        <SelectionOverlay />
        <div data-runtime-host-root="true">
          <div data-component-name="today" data-component-type="widget">
            <button data-testid="inner-button">Click me</button>
          </div>
        </div>
      </EditModeProvider>,
    )

    fireEvent.click(screen.getByTestId("inner-button"))

    // Selection overlay should now render with brass border.
    expect(
      screen.queryByTestId("runtime-editor-selection-overlay"),
    ).not.toBeNull()
  })

  it("blocks operational handlers via capture-phase preventDefault", () => {
    const operationalHandler = vi.fn()

    render(
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user-1"
        initialMode="edit"
      >
        <SelectionOverlay />
        <div data-runtime-host-root="true">
          <div data-component-name="today" data-component-type="widget">
            <button
              data-testid="operational-btn"
              onClick={operationalHandler}
            >
              Investigate
            </button>
          </div>
        </div>
      </EditModeProvider>,
    )

    fireEvent.click(screen.getByTestId("operational-btn"))

    // Capture phase fired stopPropagation; React's bubble-phase
    // onClick must not have invoked the operational handler.
    expect(operationalHandler).not.toHaveBeenCalled()
  })

  it("does NOT block operational handlers when edit mode is OFF", () => {
    const operationalHandler = vi.fn()

    render(
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user-1"
        initialMode="view"
      >
        <SelectionOverlay />
        <div data-runtime-host-root="true">
          <div data-component-name="today" data-component-type="widget">
            <button
              data-testid="operational-btn"
              onClick={operationalHandler}
            >
              Investigate
            </button>
          </div>
        </div>
      </EditModeProvider>,
    )

    fireEvent.click(screen.getByTestId("operational-btn"))

    // View mode — widget handlers should fire normally.
    expect(operationalHandler).toHaveBeenCalledTimes(1)
  })

  it("clicks on chrome (data-runtime-editor-chrome) are not hijacked", () => {
    const chromeHandler = vi.fn()
    const widgetHandler = vi.fn()

    render(
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user-1"
        initialMode="edit"
      >
        <SelectionOverlay />
        <div data-runtime-editor-chrome="true">
          <button data-testid="chrome-btn" onClick={chromeHandler}>
            Chrome
          </button>
        </div>
        <div data-runtime-host-root="true">
          <div data-component-name="today" data-component-type="widget">
            <button data-testid="widget-btn" onClick={widgetHandler}>
              Investigate
            </button>
          </div>
        </div>
      </EditModeProvider>,
    )

    fireEvent.click(screen.getByTestId("chrome-btn"))
    // Chrome click is allowed through (early return in handler).
    expect(chromeHandler).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("widget-btn"))
    // Widget click is blocked.
    expect(widgetHandler).not.toHaveBeenCalled()
  })
})
