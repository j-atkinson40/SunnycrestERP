/**
 * R-5.2 — PageList vitest coverage.
 *
 * Pure presentational component — verifies render shape + handler
 * wiring + default-page badge + ↑/↓ disabled-at-bounds discipline.
 */
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { PageList } from "./PageList"
import type { EdgePanelPage } from "@/lib/edge-panel/types"


function makePage(id: string, name: string): EdgePanelPage {
  return {
    page_id: id,
    name,
    rows: [],
    canvas_config: {},
  }
}


describe("PageList (R-5.2)", () => {
  it("renders one row per page with a DEFAULT badge on the default page", () => {
    const pages = [makePage("a", "Quick Actions"), makePage("b", "Dispatch")]
    render(
      <PageList
        pages={pages}
        activePageIndex={0}
        defaultPageIndex={1}
        onSelectPage={vi.fn()}
        onAddPage={vi.fn()}
        onMovePageUp={vi.fn()}
        onMovePageDown={vi.fn()}
      />,
    )
    expect(screen.getByTestId("edge-panel-editor-page-list")).toBeTruthy()
    expect(screen.getByTestId("edge-panel-editor-page-0")).toBeTruthy()
    expect(screen.getByTestId("edge-panel-editor-page-1")).toBeTruthy()
    // The default-index page renders the DEFAULT label.
    expect(
      screen
        .getByTestId("edge-panel-editor-page-1")
        .textContent?.includes("DEFAULT"),
    ).toBe(true)
    expect(
      screen
        .getByTestId("edge-panel-editor-page-0")
        .textContent?.includes("DEFAULT"),
    ).toBe(false)
    // Add-page button visible.
    expect(screen.getByTestId("edge-panel-editor-add-page")).toBeTruthy()
  })

  it("disables move-up at index 0 and move-down at last index", () => {
    const pages = [makePage("a", "A"), makePage("b", "B"), makePage("c", "C")]
    render(
      <PageList
        pages={pages}
        activePageIndex={0}
        defaultPageIndex={0}
        onSelectPage={vi.fn()}
        onAddPage={vi.fn()}
        onMovePageUp={vi.fn()}
        onMovePageDown={vi.fn()}
      />,
    )
    const upFirst = screen.getByTestId(
      "edge-panel-editor-page-0-move-up",
    ) as HTMLButtonElement
    const downLast = screen.getByTestId(
      "edge-panel-editor-page-2-move-down",
    ) as HTMLButtonElement
    const upMiddle = screen.getByTestId(
      "edge-panel-editor-page-1-move-up",
    ) as HTMLButtonElement
    expect(upFirst.disabled).toBe(true)
    expect(downLast.disabled).toBe(true)
    expect(upMiddle.disabled).toBe(false)
  })

  it("fires onSelectPage / onAddPage / onMovePageUp / onMovePageDown when clicked", () => {
    const pages = [makePage("a", "A"), makePage("b", "B")]
    const onSelectPage = vi.fn()
    const onAddPage = vi.fn()
    const onMovePageUp = vi.fn()
    const onMovePageDown = vi.fn()
    render(
      <PageList
        pages={pages}
        activePageIndex={0}
        defaultPageIndex={0}
        onSelectPage={onSelectPage}
        onAddPage={onAddPage}
        onMovePageUp={onMovePageUp}
        onMovePageDown={onMovePageDown}
      />,
    )
    fireEvent.click(screen.getByTestId("edge-panel-editor-page-1"))
    expect(onSelectPage).toHaveBeenCalledWith(1)
    fireEvent.click(screen.getByTestId("edge-panel-editor-add-page"))
    expect(onAddPage).toHaveBeenCalled()
    fireEvent.click(screen.getByTestId("edge-panel-editor-page-1-move-up"))
    expect(onMovePageUp).toHaveBeenCalledWith(1)
    fireEvent.click(screen.getByTestId("edge-panel-editor-page-0-move-down"))
    expect(onMovePageDown).toHaveBeenCalledWith(0)
  })
})
