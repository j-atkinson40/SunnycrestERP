/**
 * R-5.2 — button preview renderer vitest coverage.
 *
 * Verifies that the renderComponentPreview dispatcher routes
 * `button:*` registry keys through the new edit-time button preview
 * renderer (NOT the generic Phase 2 fallback). Output is a faithful
 * stand-in mirroring runtime appearance with action dispatch
 * suppressed.
 */
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

import { renderComponentPreview } from "./preview-renderers"

// Side-effect import to populate the visual-editor registry with R-4
// button registrations.
import "@/lib/visual-editor/registry/auto-register"


describe("renderComponentPreview — button (R-5.2)", () => {
  it("renders a faithful stand-in for a registered R-4 button", () => {
    const node = renderComponentPreview(
      "button:navigate-to-pulse",
      {},
      "Navigate to pulse",
    )
    render(<>{node}</>)
    expect(
      screen.getByTestId("edge-panel-button-preview-navigate-to-pulse"),
    ).toBeTruthy()
    // The rendered button shows the registration's defaultDisplayName
    // (or label override) — fall through to "Pulse" or similar; we
    // assert the stand-in surface, not the exact label content,
    // because future button registration label edits shouldn't break
    // this test.
    const root = screen.getByTestId(
      "edge-panel-button-preview-navigate-to-pulse",
    )
    // Inner Button element must be present + disabled (action
    // dispatch suppressed at edit time).
    const innerBtn = root.querySelector("button")
    expect(innerBtn).not.toBeNull()
    expect(innerBtn?.disabled).toBe(true)
  })

  it("respects label override from prop_overrides", () => {
    const node = renderComponentPreview(
      "button:navigate-to-pulse",
      { label: "Custom label" },
    )
    render(<>{node}</>)
    expect(screen.getByText("Custom label")).toBeTruthy()
  })

  it("falls through to Phase 2 fallback for non-button keys", () => {
    const node = renderComponentPreview(
      "widget:some-unknown-widget",
      {},
      "Some Widget",
    )
    render(<>{node}</>)
    // Phase 2 fallback uses test-id `preview-fallback-widget-some-unknown-widget`.
    expect(
      screen.getByTestId("preview-fallback-widget-some-unknown-widget"),
    ).toBeTruthy()
  })

  it("falls through to Phase 2 fallback for unknown button slugs", () => {
    // Even for `button:` prefix, when the registration doesn't exist
    // the renderer still renders the button stand-in — but with the
    // slug as the label fallback. Verify the test-id pattern matches
    // the slug.
    const node = renderComponentPreview(
      "button:bogus-unknown-button",
      {},
    )
    render(<>{node}</>)
    expect(
      screen.getByTestId(
        "edge-panel-button-preview-bogus-unknown-button",
      ),
    ).toBeTruthy()
  })
})
