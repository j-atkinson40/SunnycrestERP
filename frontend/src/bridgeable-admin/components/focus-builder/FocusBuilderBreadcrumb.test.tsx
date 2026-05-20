/**
 * FocusBuilderBreadcrumb unit tests (sub-arc F-5).
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { FocusBuilderBreadcrumb } from "./FocusBuilderBreadcrumb"


describe("FocusBuilderBreadcrumb", () => {
  it("renders null when segments is empty", () => {
    const { container } = render(<FocusBuilderBreadcrumb segments={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it("renders a single current segment without separators", () => {
    render(<FocusBuilderBreadcrumb segments={["Manufacturing"]} />)
    const bc = screen.getByTestId("focus-builder-breadcrumb")
    expect(bc).toBeInTheDocument()
    expect(bc.textContent).toBe("Manufacturing")
    expect(
      screen.queryByTestId("focus-builder-breadcrumb-separator"),
    ).not.toBeInTheDocument()
    expect(
      screen.getByTestId("focus-builder-breadcrumb-current"),
    ).toHaveTextContent("Manufacturing")
  })

  it("renders multiple segments separated by ›", () => {
    render(
      <FocusBuilderBreadcrumb
        segments={["Manufacturing", "Decision", "Kanban"]}
      />,
    )
    const bc = screen.getByTestId("focus-builder-breadcrumb")
    // textContent concatenates child text — collapse whitespace for
    // assertion since flex children render with no inter-text spacing
    // but separators are themselves text nodes.
    expect(bc.textContent).toBe("Manufacturing›Decision›Kanban")
    const seps = screen.getAllByTestId("focus-builder-breadcrumb-separator")
    expect(seps).toHaveLength(2)
  })

  it("marks the last segment as current", () => {
    render(
      <FocusBuilderBreadcrumb
        segments={["Manufacturing", "Decision", "Kanban", "Funeral Scheduling"]}
      />,
    )
    const current = screen.getByTestId("focus-builder-breadcrumb-current")
    expect(current).toHaveTextContent("Funeral Scheduling")
    // Earlier segments rendered too.
    expect(
      screen.getByTestId("focus-builder-breadcrumb-segment-0"),
    ).toHaveTextContent("Manufacturing")
    expect(
      screen.getByTestId("focus-builder-breadcrumb-segment-1"),
    ).toHaveTextContent("Decision")
    expect(
      screen.getByTestId("focus-builder-breadcrumb-segment-2"),
    ).toHaveTextContent("Kanban")
  })

  it("current segment carries weighted styling class", () => {
    render(
      <FocusBuilderBreadcrumb
        segments={["Manufacturing", "Funeral Scheduling"]}
      />,
    )
    const current = screen.getByTestId("focus-builder-breadcrumb-current")
    expect(current.className).toMatch(/font-medium/)
    const first = screen.getByTestId("focus-builder-breadcrumb-segment-0")
    expect(first.className).not.toMatch(/font-medium/)
  })

  it("aria-label exposes breadcrumb intent", () => {
    render(<FocusBuilderBreadcrumb segments={["Manufacturing"]} />)
    const bc = screen.getByTestId("focus-builder-breadcrumb")
    expect(bc).toHaveAttribute("aria-label", "Focus subject breadcrumb")
  })
})
