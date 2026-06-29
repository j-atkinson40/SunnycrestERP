/**
 * MoC-2c — Tasks table.
 *
 * Covers: rows + descriptive cells render; the orphan-tolerant DELIBERATE empty
 * state (em-dash, not blank) when a reference is absent; populated deep-link
 * pills when present; and the KEYSTONE — a focus pill's href is byte-identical
 * to the canonical mocDeepLink → adminPath the cards use (so a table pill and a
 * card entry open the same builder at the same artifact).
 */
import { describe, expect, it } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { mocDeepLink } from "@/bridgeable-admin/lib/moc-deep-link"
import { MoCTaskTable } from "./MoCTaskTable"
import type { MoCTask } from "@/bridgeable-admin/services/moc-service"

function artifact(over: Partial<MoCTask["focuses"][number]> = {}) {
  return {
    exists: true,
    available: true,
    label: "Artifact",
    routing: {},
    artifact_id: "art-1",
    ...over,
  }
}

const POPULATED: MoCTask = {
  id: "t-pop",
  name: "Funeral Home Billing",
  icon: "receipt",
  frequency: "End of Month",
  task_type: "Accounting",
  description: "End of month billing.",
  display_order: 0,
  workflow: artifact({
    label: "Invoice and Statement Run",
    artifact_id: "wf-1",
    routing: { workflow_type: "invoice_statement", scope: "vertical_default" },
  }),
  focuses: [
    artifact({ label: "Decision Triage", artifact_id: "foc-1", routing: { template_slug: "decision-triage", scope: "vertical_default" } }),
    artifact({ label: "Legacy Generation", artifact_id: "foc-2", routing: { template_slug: "legacy-gen", scope: "vertical_default" } }),
  ],
}

const EMPTY: MoCTask = {
  id: "t-empty",
  name: "New Legacy Order",
  icon: "sparkles",
  frequency: "On demand",
  task_type: "Funeral Service Operations",
  description: "Creates a legacy proof.",
  display_order: 1,
  workflow: null, // absent reference (option-3 not seeded)
  focuses: [],
}

function renderTable(tasks: MoCTask[]) {
  return render(
    <MemoryRouter>
      <MoCTaskTable tasks={tasks} data-testid="moc-task-table" />
    </MemoryRouter>,
  )
}

describe("MoCTaskTable", () => {
  it("renders a row per task with descriptive cells + the Type pill", () => {
    renderTable([POPULATED, EMPTY])
    expect(screen.getByTestId("moc-task-row-t-pop")).toBeTruthy()
    expect(screen.getByTestId("moc-task-row-t-empty")).toBeTruthy()
    expect(screen.getByText("End of Month")).toBeTruthy()
    expect(screen.getByText("Accounting")).toBeTruthy()
    expect(screen.getByText("Funeral Service Operations")).toBeTruthy()
  })

  it("renders the DELIBERATE empty state (em-dash) for absent workflow + focuses", () => {
    renderTable([EMPTY])
    const wf = screen.getByTestId("moc-task-workflow-t-empty")
    const foc = screen.getByTestId("moc-task-focuses-t-empty")
    // Not blank — a deliberate muted em-dash, and NOT a link.
    expect(wf.textContent).toBe("—")
    expect(foc.textContent).toBe("—")
    expect(within(wf).queryByRole("link")).toBeNull()
    expect(within(foc).queryByRole("link")).toBeNull()
  })

  it("renders populated workflow + focus pills as deep-links", () => {
    renderTable([POPULATED])
    const wf = within(screen.getByTestId("moc-task-workflow-t-pop")).getByRole("link")
    expect(wf.getAttribute("href")).toContain("workflow_type=invoice_statement")
    const foc = within(screen.getByTestId("moc-task-focuses-t-pop"))
    expect(foc.getByRole("link", { name: /Decision Triage/ })).toBeTruthy()
    expect(foc.getByRole("link", { name: /Legacy Generation/ })).toBeTruthy()
  })

  it("KEYSTONE: a focus pill's href is the canonical mocDeepLink (same as the cards)", () => {
    renderTable([POPULATED])
    const link = within(screen.getByTestId("moc-task-focuses-t-pop")).getByRole(
      "link",
      { name: /Decision Triage/ },
    )
    const expected = adminPath(
      mocDeepLink({
        builder: "focuses",
        artifact_id: "foc-1",
        routing: { template_slug: "decision-triage", scope: "vertical_default" },
      }) as string,
    )
    expect(link.getAttribute("href")).toBe(expected)
  })
})
