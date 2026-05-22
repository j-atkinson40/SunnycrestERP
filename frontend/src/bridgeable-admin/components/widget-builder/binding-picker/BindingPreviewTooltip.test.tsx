/**
 * BindingPreviewTooltip tests — display-only render states.
 *
 * Tests drive `BindingPreviewTooltipDisplay` directly so we don't
 * have to mock the saved-views service. The hook itself is tested
 * separately at useBindingPreview.test.ts.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { BindingPreviewTooltipDisplay } from "./BindingPreviewTooltip"


describe("BindingPreviewTooltipDisplay", () => {
  it("renders null for idle state", () => {
    const { container } = render(
      <BindingPreviewTooltipDisplay state={{ kind: "idle" }} testId="bpt" />,
    )
    expect(container.firstChild).toBeNull()
  })

  it("renders loading state", () => {
    render(
      <BindingPreviewTooltipDisplay state={{ kind: "loading" }} testId="bpt" />,
    )
    expect(screen.getByTestId("bpt")).toHaveAttribute(
      "data-preview-state",
      "loading",
    )
    expect(screen.getByTestId("bpt")).toHaveTextContent("Resolving preview")
  })

  it("renders empty state with reason", () => {
    render(
      <BindingPreviewTooltipDisplay
        state={{ kind: "empty", reason: "Saved view returned no rows" }}
        testId="bpt"
      />,
    )
    expect(screen.getByTestId("bpt")).toHaveAttribute(
      "data-preview-state",
      "empty",
    )
    expect(screen.getByTestId("bpt")).toHaveTextContent(
      "Saved view returned no rows",
    )
  })

  it("renders error state with message", () => {
    render(
      <BindingPreviewTooltipDisplay
        state={{ kind: "error", message: "Network failure" }}
        testId="bpt"
      />,
    )
    expect(screen.getByTestId("bpt")).toHaveAttribute(
      "data-preview-state",
      "error",
    )
    expect(screen.getByTestId("bpt")).toHaveTextContent("Network failure")
  })

  it("renders value state with preview + description", () => {
    render(
      <BindingPreviewTooltipDisplay
        state={{
          kind: "value",
          preview: "Smith",
          description: "First row preview; 3 total rows",
        }}
        testId="bpt"
      />,
    )
    expect(screen.getByTestId("bpt")).toHaveAttribute(
      "data-preview-state",
      "value",
    )
    expect(screen.getByTestId("bpt")).toHaveTextContent("Smith")
    expect(screen.getByTestId("bpt")).toHaveTextContent(
      "First row preview; 3 total rows",
    )
  })
})
