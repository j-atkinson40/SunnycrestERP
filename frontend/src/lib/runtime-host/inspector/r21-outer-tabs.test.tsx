/**
 * R-2.1 — InspectorPanel outer tabs tests.
 *
 * The outer tab strip [Card][Header][Body][Actions][...] renders ABOVE
 * the inner triad (Theme/Class/Props) when the selected component
 * (or its parent) has registered sub-sections. The active outer tab
 * scopes the inner triad to the parent OR to the selected sub-section.
 *
 * Tests rely on the auto-register barrel populating the registry —
 * 4 delivery-card sub-sections + 3 ancillary-card sub-sections + 3
 * order-card sub-sections must be registered for the outer tabs to
 * surface.
 */

import { beforeAll, describe, expect, it } from "vitest"
import { fireEvent, render } from "@testing-library/react"
import { useEffect, useRef } from "react"

// R-2.1 — auto-register barrel side-effect-imported so the registry
// is populated before any test touches the inspector.
import "@/lib/visual-editor/registry/auto-register"

import { EditModeProvider, useEditMode } from "../edit-mode-context"
import { InspectorPanel } from "./InspectorPanel"


/** Driver — calls selectComponent OR selectSection inside an effect
 *  guarded by a useRef sentinel so it only fires once on mount. */
function SelectionDriver({
  mode,
}: {
  mode: "delivery-card" | "section:delivery-card.header"
}) {
  const ctx = useEditMode()
  const inited = useRef(false)
  useEffect(() => {
    if (inited.current) return
    inited.current = true
    if (mode === "delivery-card") {
      ctx.selectComponent("delivery-card")
    } else {
      ctx.selectSection(
        "entity-card",
        "delivery-card",
        "delivery-card.header",
      )
    }
  }, [ctx, mode])
  return null
}


function MountWith({
  selectionFn,
}: {
  selectionFn: "delivery-card" | "section:delivery-card.header"
}) {
  return (
    <EditModeProvider
      tenantSlug="t1"
      impersonatedUserId="u1"
      initialMode="edit"
    >
      <SelectionDriver mode={selectionFn} />
      <InspectorPanel
        vertical="manufacturing"
        tenantId={null}
        themeMode="light"
      />
    </EditModeProvider>
  )
}


describe("R-2.1 — InspectorPanel outer tabs", () => {
  beforeAll(() => {
    // No-op — auto-register imported at file head.
  })

  it("renders outer tabs strip when parent has sub-sections", () => {
    const { getByTestId } = render(
      <MountWith selectionFn="delivery-card" />,
    )
    expect(getByTestId("runtime-inspector-outer-tabs")).toBeTruthy()
    expect(getByTestId("runtime-inspector-outer-tab-card")).toBeTruthy()
    expect(
      getByTestId("runtime-inspector-outer-tab-delivery-card.header"),
    ).toBeTruthy()
    expect(
      getByTestId("runtime-inspector-outer-tab-delivery-card.body"),
    ).toBeTruthy()
    expect(
      getByTestId("runtime-inspector-outer-tab-delivery-card.actions"),
    ).toBeTruthy()
    expect(
      getByTestId(
        "runtime-inspector-outer-tab-delivery-card.hole-dug-badge",
      ),
    ).toBeTruthy()
  })

  it("when parent selected, Card tab is active by default", () => {
    const { getByTestId } = render(
      <MountWith selectionFn="delivery-card" />,
    )
    const cardTab = getByTestId("runtime-inspector-outer-tab-card")
    expect(cardTab.getAttribute("data-active")).toBe("true")
    const headerTab = getByTestId(
      "runtime-inspector-outer-tab-delivery-card.header",
    )
    expect(headerTab.getAttribute("data-active")).toBe("false")
  })

  it("when sub-section selected, that section's tab is active by default", () => {
    const { getByTestId } = render(
      <MountWith selectionFn="section:delivery-card.header" />,
    )
    const headerTab = getByTestId(
      "runtime-inspector-outer-tab-delivery-card.header",
    )
    expect(headerTab.getAttribute("data-active")).toBe("true")
    const cardTab = getByTestId("runtime-inspector-outer-tab-card")
    expect(cardTab.getAttribute("data-active")).toBe("false")
  })

  it("clicking an outer tab sets it active", () => {
    const { getByTestId } = render(
      <MountWith selectionFn="delivery-card" />,
    )
    const bodyTab = getByTestId(
      "runtime-inspector-outer-tab-delivery-card.body",
    )
    expect(bodyTab.getAttribute("data-active")).toBe("false")
    fireEvent.click(bodyTab)
    expect(bodyTab.getAttribute("data-active")).toBe("true")
    const cardTab = getByTestId("runtime-inspector-outer-tab-card")
    expect(cardTab.getAttribute("data-active")).toBe("false")
  })
})
