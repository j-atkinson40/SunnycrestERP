/**
 * R-5.1 — ButtonPicker vitest coverage.
 *
 * Asserts vertical-filter discipline + onSelect-and-close flow.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"

import { ButtonPicker } from "./ButtonPicker"

// The visual editor button registry auto-registers via the App.tsx
// barrel. For the ButtonPicker tests we need the registry populated;
// import the barrel as a side-effect.
import "@/lib/visual-editor/registry/auto-register"


describe("ButtonPicker", () => {
  it("does not render when open=false", () => {
    render(
      <ButtonPicker
        open={false}
        onClose={vi.fn()}
        onSelect={vi.fn()}
        tenantVertical="manufacturing"
      />,
    )
    expect(screen.queryByTestId("edge-panel-settings-button-picker")).toBeNull()
  })

  it("renders the manufacturer-applicable buttons for mfg vertical", () => {
    render(
      <ButtonPicker
        open
        onClose={vi.fn()}
        onSelect={vi.fn()}
        tenantVertical="manufacturing"
      />,
    )
    // navigate-to-pulse is universal (declares all 4 verticals) — visible.
    expect(
      screen.getByTestId(
        "edge-panel-settings-button-picker-row-navigate-to-pulse",
      ),
    ).toBeTruthy()
    // trigger-cement-order-workflow is mfg-only — visible for mfg.
    expect(
      screen.getByTestId(
        "edge-panel-settings-button-picker-row-trigger-cement-order-workflow",
      ),
    ).toBeTruthy()
  })

  it("filters out mfg-only buttons for cemetery vertical", () => {
    render(
      <ButtonPicker
        open
        onClose={vi.fn()}
        onSelect={vi.fn()}
        tenantVertical="cemetery"
      />,
    )
    // navigate-to-pulse universal — visible.
    expect(
      screen.getByTestId(
        "edge-panel-settings-button-picker-row-navigate-to-pulse",
      ),
    ).toBeTruthy()
    // trigger-cement-order-workflow is mfg-only — NOT visible.
    expect(
      screen.queryByTestId(
        "edge-panel-settings-button-picker-row-trigger-cement-order-workflow",
      ),
    ).toBeNull()
  })

  it("clicking Add fires onSelect with slug + defaults and closes", () => {
    const onSelect = vi.fn()
    const onClose = vi.fn()
    render(
      <ButtonPicker
        open
        onClose={onClose}
        onSelect={onSelect}
        tenantVertical="manufacturing"
      />,
    )
    fireEvent.click(
      screen.getByTestId(
        "edge-panel-settings-button-picker-add-navigate-to-pulse",
      ),
    )
    expect(onSelect).toHaveBeenCalledTimes(1)
    const [slug, defaults] = onSelect.mock.calls[0]
    expect(slug).toBe("navigate-to-pulse")
    expect(defaults).toMatchObject({ label: "Pulse" })
    expect(onClose).toHaveBeenCalled()
  })
})
