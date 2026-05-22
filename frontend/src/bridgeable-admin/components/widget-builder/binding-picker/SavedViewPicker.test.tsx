/**
 * SavedViewPicker tests — WB-6 filtered combobox.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { SavedViewPicker } from "./SavedViewPicker"
import type { SavedView } from "@/types/saved-views"


function mkView(over: Partial<SavedView> & { id: string; title: string }): SavedView {
  return {
    id: over.id,
    company_id: "co1",
    title: over.title,
    description: null,
    created_by: null,
    created_at: "2026-05-21T00:00:00Z",
    updated_at: "2026-05-21T00:00:00Z",
    config: {
      query: {
        entity_type: "invoice",
        filters: [],
        sort: [],
      },
      presentation: { mode: "list" },
      permissions: {
        owner_user_id: "u1",
        visibility: "private",
      },
      ...(over.config ?? {}),
    },
  } as SavedView
}


describe("SavedViewPicker", () => {
  it("renders 'Pick a saved view' when value is null", () => {
    render(
      <SavedViewPicker
        savedViews={[]}
        value={null}
        onChange={() => {}}
        testId="sv-picker"
      />,
    )
    expect(screen.getByTestId("sv-picker")).toHaveTextContent("Pick a saved view")
  })

  it("displays the selected view title", () => {
    const views = [mkView({ id: "v1", title: "Outstanding invoices" })]
    render(
      <SavedViewPicker
        savedViews={views}
        value="v1"
        onChange={() => {}}
        testId="sv-picker"
      />,
    )
    expect(screen.getByTestId("sv-picker")).toHaveTextContent(
      "Outstanding invoices",
    )
  })

  it("opens popover + lists views on click", () => {
    const views = [
      mkView({ id: "v1", title: "Outstanding invoices" }),
      mkView({ id: "v2", title: "Open cases" }),
    ]
    render(
      <SavedViewPicker
        savedViews={views}
        value={null}
        onChange={() => {}}
        testId="sv-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("sv-picker"))
    expect(screen.getByTestId("sv-picker-option-v1")).toBeInTheDocument()
    expect(screen.getByTestId("sv-picker-option-v2")).toBeInTheDocument()
  })

  it("calls onChange with the picked view's id", () => {
    const views = [mkView({ id: "v1", title: "View one" })]
    const onChange = vi.fn()
    render(
      <SavedViewPicker
        savedViews={views}
        value={null}
        onChange={onChange}
        testId="sv-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("sv-picker"))
    fireEvent.click(screen.getByTestId("sv-picker-option-v1"))
    expect(onChange).toHaveBeenCalledWith("v1")
  })

  it("filters via search input", () => {
    const views = [
      mkView({ id: "v1", title: "Outstanding invoices" }),
      mkView({ id: "v2", title: "Open cases" }),
    ]
    render(
      <SavedViewPicker
        savedViews={views}
        value={null}
        onChange={() => {}}
        testId="sv-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("sv-picker"))
    const search = screen.getByTestId("sv-picker-search")
    fireEvent.change(search, { target: { value: "case" } })
    expect(screen.queryByTestId("sv-picker-option-v1")).toBeNull()
    expect(screen.getByTestId("sv-picker-option-v2")).toBeInTheDocument()
  })

  it("shape-filter excludes chart/stat views when requiresArrayShape", () => {
    const listView = mkView({ id: "v1", title: "List view" })
    const chartView = {
      ...mkView({ id: "v2", title: "Chart view" }),
      config: {
        ...mkView({ id: "v2", title: "Chart view" }).config,
        presentation: { mode: "chart" as const },
      },
    } as SavedView
    render(
      <SavedViewPicker
        savedViews={[listView, chartView]}
        value={null}
        onChange={() => {}}
        requiresArrayShape={true}
        testId="sv-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("sv-picker"))
    expect(screen.getByTestId("sv-picker-option-v1")).toBeInTheDocument()
    expect(screen.queryByTestId("sv-picker-option-v2")).toBeNull()
  })

  it("shows empty-state copy when no views in tenant", () => {
    render(
      <SavedViewPicker
        savedViews={[]}
        value={null}
        onChange={() => {}}
        testId="sv-picker"
      />,
    )
    fireEvent.click(screen.getByTestId("sv-picker"))
    expect(screen.getByTestId("sv-picker-results")).toHaveTextContent(
      "No saved views in this tenant yet.",
    )
  })
})
