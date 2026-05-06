/**
 * FocusContextBridge tests — operational props threading through the
 * composition runtime layer.
 */
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import {
  FocusContextBridge,
  buildOperationalProps,
  useOperationalProps,
} from "./FocusContextBridge"


function Inspector({
  componentKind,
  componentName,
}: {
  componentKind: string
  componentName: string
}) {
  const props = useOperationalProps(componentKind, componentName)
  return (
    <div data-testid="inspector">{JSON.stringify(props)}</div>
  )
}


describe("FocusContextBridge", () => {
  it("threads operational props by component-kind + name", () => {
    const operational = buildOperationalProps([
      {
        componentKind: "widget",
        componentName: "vault-schedule",
        props: { cases: [{ id: "c1" }] },
      },
    ])
    render(
      <FocusContextBridge operational={operational}>
        <Inspector componentKind="widget" componentName="vault-schedule" />
      </FocusContextBridge>,
    )
    expect(screen.getByTestId("inspector").textContent).toContain("c1")
  })

  it("returns empty object when no bridge is mounted", () => {
    render(
      <Inspector componentKind="widget" componentName="vault-schedule" />,
    )
    expect(screen.getByTestId("inspector").textContent).toBe("{}")
  })

  it("returns empty object when bridge is mounted but key not registered", () => {
    render(
      <FocusContextBridge operational={{}}>
        <Inspector componentKind="widget" componentName="missing" />
      </FocusContextBridge>,
    )
    expect(screen.getByTestId("inspector").textContent).toBe("{}")
  })

  it("buildOperationalProps formats the key consistently", () => {
    const map = buildOperationalProps([
      {
        componentKind: "widget",
        componentName: "today",
        props: { date: "2026-05-28" },
      },
      {
        componentKind: "focus",
        componentName: "decision",
        props: { queueId: "q1" },
      },
    ])
    expect(Object.keys(map).sort()).toEqual([
      "focus:decision",
      "widget:today",
    ])
  })
})
