/** Ponder Polish trio pins — group tabs, hold-to-ponder, motif dispatch. */
import { describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { MoCTaskTable } from "./MoCTaskTable"
import { MotifScene } from "./ponder-motifs"
import type { MoCTask } from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async (orig) => ({
  ...(await orig()),
  getPonderScript: vi.fn().mockResolvedValue({
    task_id: "t", task_name: "T", workflow_name: "W",
    beats: [{ key: "when", kind: "when", text: "x", derived_text: "x", authored: false }],
    orphaned_captions: {}, mirror_drift: [],
  }),
}))

function task(id: string, name: string, type: string | null, withWorkflow = true): MoCTask {
  return {
    id, name, task_type: type, display_order: 0,
    workflow: withWorkflow
      ? { builder: "workflows", label: name, available: true, artifact_id: id } as never
      : null,
    focuses: [],
  } as MoCTask
}

const TASKS = [
  task("a", "Monthly Statement Run", "Accounting"),
  task("b", "Month-End Close", "Accounting"),
  task("c", "Log Production Pour", null),
  task("d", "Bare Task", null, false), // non-ponderable
]

function mount(url = "/maps/manufacturing") {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <MoCTaskTable tasks={TASKS} vertical="manufacturing" onChanged={() => {}} />
    </MemoryRouter>,
  )
}

describe("group tabs (Set 1)", () => {
  it("derives tabs from types-with-tasks; All default is non-regressive", () => {
    mount()
    expect(screen.getByTestId("moc-task-group-all").textContent).toContain("4")
    expect(screen.getByTestId("moc-task-group-accounting").textContent).toContain("2")
    // untyped tasks appear under All only; no phantom tab for null.
    expect(screen.getAllByTestId(/^moc-task-row-/)).toHaveLength(4)
  })

  it("filters on tab click and deep-links from ?group=", () => {
    mount("/maps/manufacturing?group=accounting")
    expect(screen.getAllByTestId(/^moc-task-row-/)).toHaveLength(2)
    fireEvent.click(screen.getByTestId("moc-task-group-all"))
    expect(screen.getAllByTestId(/^moc-task-row-/)).toHaveLength(4)
  })

  it("renders no rail when nothing is typed", () => {
    render(
      <MemoryRouter>
        <MoCTaskTable tasks={[task("x", "X", null)]} vertical="manufacturing" onChanged={() => {}} />
      </MemoryRouter>,
    )
    expect(screen.queryByTestId("moc-task-group-rail")).toBeNull()
  })
})

describe("hold-to-ponder (Set 2)", () => {
  it("teaches on hover of a ponderable row; opens after a held P; releases cancel", async () => {
    vi.useFakeTimers()
    try {
      mount()
      const nameCell = screen.getByTestId("moc-task-row-a").querySelector("td span")!
      fireEvent.mouseEnter(nameCell)
      expect(screen.getByTestId("moc-task-hold-hint-a")).toBeTruthy()

      // early release cancels clean
      fireEvent.keyDown(window, { key: "p" })
      fireEvent.keyUp(window, { key: "p" })
      act(() => { vi.advanceTimersByTime(1000) })
      expect(screen.queryByTestId("ponder-overlay")).toBeNull()

      // a completed hold opens the ponder
      fireEvent.keyDown(window, { key: "p" })
      act(() => { vi.advanceTimersByTime(700) })
      expect(screen.getByTestId("ponder-overlay")).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })

  it("non-ponderable rows: no hint, no dead hotkey", () => {
    mount()
    const bare = screen.getByTestId("moc-task-row-d").querySelector("td span")!
    fireEvent.mouseEnter(bare)
    expect(screen.queryByTestId("moc-task-hold-hint-d")).toBeNull()
    fireEvent.keyDown(window, { key: "p" })
    expect(screen.queryByTestId("ponder-overlay")).toBeNull()
  })

  it("key is scoped to hover — P elsewhere does nothing", () => {
    mount()
    fireEvent.keyDown(window, { key: "p" })
    expect(screen.queryByTestId("ponder-overlay")).toBeNull()
  })
})

describe("motif dispatch (Set 3)", () => {
  it("known kinds render their scene; unknown/absent render NOTHING (never a wrong scene)", () => {
    const { rerender } = render(<MotifScene motif={{ kind: "transform", from: "order", to: "invoice" }} reduced={false} />)
    expect(screen.getByTestId("ponder-motif-transform")).toBeTruthy()
    expect(screen.getByText("orders")).toBeTruthy()
    expect(screen.getByText("invoices")).toBeTruthy()

    rerender(<MotifScene motif={{ kind: "queue", label: "Month-End Close review" }} reduced={false} />)
    expect(screen.getByText("Month-End Close review")).toBeTruthy()

    rerender(<MotifScene motif={{ kind: "some-future-kind" }} reduced={false} />)
    expect(screen.queryByTestId(/^ponder-motif-/)).toBeNull()

    rerender(<MotifScene motif={null} reduced={false} />)
    expect(screen.queryByTestId(/^ponder-motif-/)).toBeNull()
  })

  it("reduced motion renders the static class", () => {
    render(<MotifScene motif={{ kind: "create", entity: "statement" }} reduced={true} />)
    expect(screen.getByTestId("ponder-motif-create").className).toContain("motif-static")
  })
})

describe("artifact previews + audience (Enrichment)", () => {
  it("focus miniature: lineage label without core-core duplication; audience line honest", async () => {
    const { ArtifactPreview, AudienceLine } = await import("./PonderArtifacts")
    const { render: r2, screen: s2 } = await import("@testing-library/react")

    r2(<ArtifactPreview artifact={{
      type: "focus", template_slug: "decision-triage", display_name: "Decision Triage",
      core_slug: "decision-triage-core", core_version: 4, template_version: 1,
      chrome_title: "Decision Triage", icon: "kanban",
      rows: [{ placements: [{ label: "TriageQueueCore" }] }],
    }} />)
    expect(s2.getByTestId("ponder-focus-lineage").textContent).toBe(
      "Decision Triage · from decision triage core v4",
    )
    expect(s2.getByText("TriageQueueCore")).toBeTruthy()

    r2(<AudienceLine audience={{ text: "anyone with the invoice.approve permission", count: 4 }} />)
    expect(s2.getByTestId("ponder-audience").textContent).toContain("4 users today")

    // not derivable → NO line; unknown artifact type → NOTHING
    const { container } = r2(<AudienceLine audience={null} />)
    expect(container.querySelector('[data-testid="ponder-audience"]')).toBeNull()
    const { container: c2 } = r2(<ArtifactPreview artifact={{ type: "widget-of-the-future" }} />)
    expect(c2.querySelector('[data-testid^="ponder-artifact-"]')).toBeNull()
  })
})
