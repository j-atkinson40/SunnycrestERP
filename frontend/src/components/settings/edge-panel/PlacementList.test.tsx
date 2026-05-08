/**
 * R-5.1 — PlacementList vitest coverage.
 *
 * Asserts hide/show, delete personal, add affordance, ownership
 * badges, reorder via drag, and disambiguates tenant vs personal
 * row treatment.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"

import type { Placement } from "@/lib/visual-editor/compositions/types"

import { PlacementList } from "./PlacementList"


function makePlacement(id: string, name = "navigate-to-pulse"): Placement {
  return {
    placement_id: id,
    component_kind: "button",
    component_name: name,
    starting_column: 0,
    column_span: 1,
    prop_overrides: {},
    display_config: {},
    nested_rows: null,
  }
}


describe("PlacementList", () => {
  it("renders both tenant + personal placements with correct badges", () => {
    render(
      <PlacementList
        rowIndex={0}
        tenantPlacements={[makePlacement("tenant-1")]}
        additionalPlacements={[makePlacement("personal-1")]}
        hiddenIds={[]}
        placementOrder={null}
        onToggleHide={vi.fn()}
        onDeletePersonal={vi.fn()}
        onAddPlacement={vi.fn()}
        onReorder={vi.fn()}
      />,
    )
    const tenant = screen.getByTestId("edge-panel-settings-placement-tenant-1")
    expect(tenant.getAttribute("data-ownership")).toBe("tenant")
    const personal = screen.getByTestId(
      "edge-panel-settings-placement-personal-1",
    )
    expect(personal.getAttribute("data-ownership")).toBe("personal")
  })

  it("hidden tenant placement renders with data-hidden=true", () => {
    render(
      <PlacementList
        rowIndex={0}
        tenantPlacements={[makePlacement("tenant-1")]}
        additionalPlacements={[]}
        hiddenIds={["tenant-1"]}
        placementOrder={null}
        onToggleHide={vi.fn()}
        onDeletePersonal={vi.fn()}
        onAddPlacement={vi.fn()}
        onReorder={vi.fn()}
      />,
    )
    const li = screen.getByTestId("edge-panel-settings-placement-tenant-1")
    expect(li.getAttribute("data-hidden")).toBe("true")
  })

  it("clicking hide button on tenant fires onToggleHide", () => {
    const onToggle = vi.fn()
    render(
      <PlacementList
        rowIndex={0}
        tenantPlacements={[makePlacement("t1")]}
        additionalPlacements={[]}
        hiddenIds={[]}
        placementOrder={null}
        onToggleHide={onToggle}
        onDeletePersonal={vi.fn()}
        onAddPlacement={vi.fn()}
        onReorder={vi.fn()}
      />,
    )
    fireEvent.click(
      screen.getByTestId("edge-panel-settings-placement-toggle-hide-t1"),
    )
    expect(onToggle).toHaveBeenCalledWith("t1")
  })

  it("clicking delete on personal fires onDeletePersonal", () => {
    const onDelete = vi.fn()
    render(
      <PlacementList
        rowIndex={0}
        tenantPlacements={[]}
        additionalPlacements={[makePlacement("p1")]}
        hiddenIds={[]}
        placementOrder={null}
        onToggleHide={vi.fn()}
        onDeletePersonal={onDelete}
        onAddPlacement={vi.fn()}
        onReorder={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("edge-panel-settings-placement-delete-p1"))
    expect(onDelete).toHaveBeenCalledWith("p1")
  })

  it("clicking add fires onAddPlacement", () => {
    const onAdd = vi.fn()
    render(
      <PlacementList
        rowIndex={2}
        tenantPlacements={[]}
        additionalPlacements={[]}
        hiddenIds={[]}
        placementOrder={null}
        onToggleHide={vi.fn()}
        onDeletePersonal={vi.fn()}
        onAddPlacement={onAdd}
        onReorder={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId("edge-panel-settings-placement-add-row-2"))
    expect(onAdd).toHaveBeenCalledTimes(1)
  })

  it("placement_order reorders the merged set", () => {
    render(
      <PlacementList
        rowIndex={0}
        tenantPlacements={[makePlacement("t1"), makePlacement("t2")]}
        additionalPlacements={[]}
        hiddenIds={[]}
        placementOrder={["t2", "t1"]}
        onToggleHide={vi.fn()}
        onDeletePersonal={vi.fn()}
        onAddPlacement={vi.fn()}
        onReorder={vi.fn()}
      />,
    )
    const items = screen.getAllByTestId(
      /^edge-panel-settings-placement-(t|p)\d+$/,
    )
    // First item should be t2 per the ordering.
    expect(items[0].getAttribute("data-testid")).toBe(
      "edge-panel-settings-placement-t2",
    )
  })

  it("drag-drop onReorder emits new id sequence", () => {
    const onReorder = vi.fn()
    render(
      <PlacementList
        rowIndex={0}
        tenantPlacements={[makePlacement("t1"), makePlacement("t2")]}
        additionalPlacements={[]}
        hiddenIds={[]}
        placementOrder={null}
        onToggleHide={vi.fn()}
        onDeletePersonal={vi.fn()}
        onAddPlacement={vi.fn()}
        onReorder={onReorder}
      />,
    )
    const t1 = screen.getByTestId("edge-panel-settings-placement-t1")
    const t2 = screen.getByTestId("edge-panel-settings-placement-t2")
    fireEvent.dragStart(t1)
    fireEvent.dragOver(t2)
    fireEvent.drop(t2)
    expect(onReorder).toHaveBeenCalledWith(["t2", "t1"])
  })
})
